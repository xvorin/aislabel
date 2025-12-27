# -*- coding: utf-8 -*-
from utils.logger import logger
from utils.config import Global
from models.data import PaintCommand, Point, LabelGroup
from canvas.resizable_view import ResizableGraphicsView
from canvas.graphics.factory import GraphicsFactory
from canvas.graphics.anchor import Anchor
from canvas.operations import Operations

from project.provider import LabelingDataItem

from PyQt6.QtCore import QObject, QSize, QTimer, QEvent, QPointF
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem
from PyQt6.QtGui import QPixmap, QAction, QShortcut, QKeySequence, QTransform

import qtawesome as qta


class Canvas(QObject):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui

        self.ui.save.setIcon(qta.icon('mdi.content-save'))  # 保存 mdi.content-save-alert
        self.ui.save.setIconSize(QSize(21, 21))
        self.ui.save.clicked.connect(self.save)

        # 初始化绘图scene
        self.scene = QGraphicsScene()

        # 初始化绘图view
        self.view = ResizableGraphicsView(ui.canvas_group)
        self.view.setObjectName("view")
        self.view.setScene(self.scene)
        ui.canvas_grid_layout.addWidget(self.view, 1, 0, 1, 1)
        ui.centralwidget.window().installEventFilter(self)  # self包含eventFilter方法

        # 用于绘图的鼠标操作回调
        self.view.on_mouse_left_single_clicked = self._on_mouse_left_single_clicked
        self.view.on_mouse_left_double_clicked = self._on_mouse_left_double_clicked
        self.view.on_mouse_right_clicked = self._on_mouse_right_clicked
        self.view.on_mouse_move = self._on_mouse_move

        # 用于判断item移动
        self.view.on_mouse_left_press = self._on_mouse_left_press
        self.view.on_mouse_release = self._on_mouse_release
        self.moving_item_position = None

        # 设置工具栏
        self.toolbar = ui.tools
        self.__setup_toolbar()

        self.pixmap = None  # 保存底图
        self.editing = None  # 保存正在被编辑的item
        self.command = PaintCommand.PCMD_ARROR  # 当前编辑命令

        self.labeling = None  # 正在被标注的数据, 外部选定图片后注入

        logger.info("Canvas initialized")

    def load(self, labeling: LabelingDataItem):
        self.labeling = labeling

        self.pixmap = QGraphicsPixmapItem(QPixmap(str(self.labeling.image())))
        self.pixmap.setZValue(0)

        self.view.set_pixmap_item(self.pixmap)

        self.scene.clear()
        self.scene.addItem(self.pixmap)
        self.scene.setSceneRect(self.pixmap.boundingRect())

        Global["image_size"] = (self.scene.sceneRect().width(), self.scene.sceneRect().height())

        QTimer.singleShot(0, self.view.zoom_fit)

        if self.labeling.operations is None:
            self.labeling.operations = Operations(self.scene)
            labels = self.labeling.labels.model_copy(deep=True) if self.labeling.labeled() else LabelGroup()
            self.labeling.operations.record(labels)
            self.labeling.operations.dirty_state_changed.connect(self._on_dirty_state_changed)
            self.labeling.operations.set_dirty(False)

        curr = self.labeling.operations.labels(self.labeling.operations.index)
        self.labeling.operations.show_labels(curr)
        self.labeling.operations.set_dirty()

    def save(self):
        if self.labeling is None:
            return
        self.labeling.operations.set_dirty(False)
        self.labeling.update_labels(self._build_current_labels())

    def __setup_toolbar(self):
        self.toolbar.setIconSize(QSize(23, 23))

        # 绘图工具
        # fmt:off
        tools = [ #
            {'icon': 'fa6s.arrow-pointer', 'name': '选择', 'checkable': True, 'command': PaintCommand.PCMD_ARROR },
            {'icon': 'mdi6.vector-line', 'name': '线段', 'checkable': True, 'command': PaintCommand.PCMD_LINESEG },
            {'icon': 'mdi6.vector-polyline', 'name': '折线', 'checkable': True, 'command': PaintCommand.PCMD_POLYLINE },
            {'icon': 'mdi6.vector-rectangle', 'name': '矩形框', 'checkable': True, 'command': PaintCommand.PCMD_RECTANGLE },
            {'icon': 'mdi6.vector-polygon-variant', 'name': '多边形', 'checkable': True, 'command': PaintCommand.PCMD_POLYGON },
            {'icon': 'msc.debug-breakpoint-disabled','name': '关键点','checkable': True,  'command': PaintCommand.PCMD_KEYPOINT },
            {'icon': 'ri.delete-bin-3-line', 'name': '删除', 'checkable': False, 'command': PaintCommand.PCMD_DELETE }
        ]
        # fmt:on

        def on_action_triggered(acn: QAction, cmd: PaintCommand):
            if cmd == PaintCommand.PCMD_DELETE:
                self.set_paint_cmd(cmd)
                return
            for action in self.toolbar.actions():  # 实现互斥逻辑
                action.setChecked(False)
            acn.setChecked(True)
            self.set_paint_cmd(cmd)  # 设置绘图命令

        for tool in tools:
            action = QAction(qta.icon(tool['icon']), tool['name'], self.toolbar)
            action.setCheckable(tool['checkable'])  # 设置是否可选中
            action.triggered.connect(lambda checked, acn=action, cmd=tool['command']: on_action_triggered(acn, cmd))
            self.toolbar.addAction(action)
            if tool['name'] == '选择':
                action.setChecked(True)

        # 撤销/重做工具
        self.toolbar.addSeparator()
        tools = [
            {'icon': 'mdi6.undo-variant', 'name': '撤销', 'checkable': False, 'command': self._undo},
            {'icon': 'mdi6.redo-variant', 'name': '重做', 'checkable': False, 'command': self._redo},
        ]
        for tool in tools:
            action = QAction(qta.icon(tool['icon']), tool['name'], self.toolbar)
            action.setCheckable(tool['checkable'])  # 设置是否可选中
            action.triggered.connect(tool['command'])
            self.toolbar.addAction(action)
        QShortcut(QKeySequence("Ctrl+Z"), self.view).activated.connect(self._undo)  # Ctrl+Z 撤销
        QShortcut(QKeySequence("Ctrl+Y"), self.view).activated.connect(self._redo)  # Ctrl+Y 重做

        # 放大/缩小工具
        self.toolbar.addSeparator()
        tools = [
            {'icon': 'ri.fullscreen-line', 'name': '适应窗口', 'checkable': False, 'command': self.view.zoom_fit},
            {'icon': 'ph.arrows-out', 'name': '原始大小', 'checkable': False, 'command': self.view.zoom_100},
            {'icon': 'ri.zoom-in-line', 'name': '放大', 'checkable': False, 'command': self.view.zoom_in},
            {'icon': 'ri.zoom-out-line', 'name': '缩小', 'checkable': False, 'command': self.view.zoom_out},
        ]
        for tool in tools:
            action = QAction(qta.icon(tool['icon']), tool['name'], self.toolbar)
            action.setCheckable(tool['checkable'])  # 设置是否可选中
            action.triggered.connect(tool['command'])
            self.toolbar.addAction(action)

    def set_paint_cmd(self, cmd: PaintCommand):
        logger.info(f"Setting paint command: {cmd}")
        if cmd == PaintCommand.PCMD_DELETE:
            parents = [item.parent for item in self.scene.selectedItems() if isinstance(item, Anchor)]
            graphics = [item for item in self.scene.selectedItems() if not isinstance(item, Anchor)]
            for item in set(parents) | set(graphics):
                self.scene.removeItem(item)
            self._record_operation()
            return

        self.command = cmd
        if self.editing and self.editing in self.scene.items():
            self.scene.removeItem(self.editing)
            self.editing = None

    def _on_mouse_left_single_clicked(self, x, y):
        self._cancel_focus()
        if self.labeling is None:
            return
        if self.editing is None:
            if len(self.scene.selectedItems()) > 0:
                return
            if self.command == PaintCommand.PCMD_ARROR:
                return
            self.editing = GraphicsFactory.create(self.command)
            self.scene.addItem(self.editing)
        self.editing.commit_point(Point(x=x, y=y))
        self.scene.update()

    def _on_mouse_left_double_clicked(self, x, y):
        self._cancel_focus()
        if self.editing is None:
            if len(self.scene.selectedItems()) > 0:
                anchor = self.scene.selectedItems()[0]
                if not isinstance(anchor, Anchor) or not anchor.parent.could_redit:
                    return
                self.editing = anchor.parent
                self.editing.switch_edit_mode(anchor)  # 重新编辑
                self.scene.update()
            return
        self.editing.commit_point(Point(x=x, y=y))
        self.editing.switch_edit_mode()  # 编辑完成
        self.editing = None

        self._record_operation()

    def _on_mouse_right_clicked(self, x, y):
        self._cancel_focus()
        if self.editing is not None:
            self.editing.delete_point()
            if self.editing.empty() and self.editing in self.scene.items():
                self.scene.removeItem(self.editing)
                self.editing = None
            self.scene.update()

    def _on_mouse_move(self, x, y):
        if self.editing is not None:
            self.editing.draft_point(Point(x=x, y=y))
            self.scene.update()

    def _cancel_focus(self):
        items = self.scene.items()
        items = [item for item in items if not isinstance(item, Anchor) and not item.isSelected()]
        for item in items:
            item.itemChange(QGraphicsItem.GraphicsItemChange.ItemSelectedChange, 0)

    def eventFilter(self, object, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self.view.zoom_fit()
        return super().eventFilter(object, event)

    def _build_current_labels(self):
        items = self.scene.items()
        items = [item for item in items if not isinstance(item, Anchor) and not isinstance(item, QGraphicsPixmapItem)]
        labels = LabelGroup()
        for item in items:
            labels.labels.append(item.label())
        return labels

    def _record_operation(self):
        if self.labeling is None:
            return
        self.labeling.operations.record(self._build_current_labels())

    def _undo(self):
        if self.labeling is not None:
            self.labeling.operations.undo()

    def _redo(self):
        if self.labeling is not None:
            self.labeling.operations.redo()

    def _on_mouse_left_press(self, x, y):
        """鼠标按下时记录要移动的项目和起始位置"""
        item = self.scene.itemAt(QPointF(x, y), QTransform())
        self.moving_item_position = (item, item.pos()) if item and not isinstance(item, QGraphicsPixmapItem) else None

    def _on_mouse_release(self, x, y):
        if self.moving_item_position is None:
            return
        if self.moving_item_position[0].pos() != self.moving_item_position[1]:
            self._record_operation()  # 判断有item移动 则记录操作
        self.moving_item_position = None

    def _on_dirty_state_changed(self, dirty):
        # 更新保存按钮的图标
        self.ui.save.setIcon(qta.icon('mdi.content-save-alert' if dirty else 'mdi.content-save'))
