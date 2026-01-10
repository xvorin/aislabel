# -*- coding: utf-8 -*-
from utils.logger import logger

from models.data import PaintCommand, Point, LabelGroup, LabelSchema

from canvas.resizable_view import ResizableGraphicsView
from canvas.graphics.factory import GraphicsFactory
from canvas.graphics.anchor import Anchor
from canvas.operations import Operations
from canvas.tables.schema import LabelSchemaTable
from canvas.tables.group import LabelGroupTable

from project.provider import LabelingDataItem

from aannotate.detect import Detect

from PyQt6.QtCore import QObject, QSize, QTimer, QEvent, QPointF, pyqtSignal
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem
from PyQt6.QtGui import QPixmap, QAction, QShortcut, QKeySequence, QTransform, QColor

import qtawesome as qta


class Canvas(QObject):
    on_label_group_saved = pyqtSignal()

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
        ui.centralwidget.window().installEventFilter(self)  # self包含eventFilter方法, 接收窗口放大缩小的通知

        # 用于绘图的鼠标操作回调
        self.view.on_mouse_left_single_clicked = self._on_mouse_left_single_clicked
        self.view.on_mouse_left_double_clicked = self._on_mouse_left_double_clicked
        self.view.on_mouse_right_clicked = self._on_mouse_right_clicked
        self.view.on_mouse_move = self._on_mouse_move
        self.view.on_type_specified.connect(self._on_type_specified)  # 接收数字键 设置item业务类别
        self.view.on_scale_changed.connect(self._on_scale_changed)  # 监听缩放 并修改item边线粗细

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

        self.project = None
        self.schema = LabelSchemaTable(self.ui)
        self.schema.on_label_schema_changed.connect(self._on_label_schema_changed)
        self.group = LabelGroupTable(self.ui)
        self.group.on_label_group_changed.connect(self._on_label_group_changed)
        self.group.on_label_instance_selected.connect(self._on_label_instance_selected)

        # 模型检测
        self.detect = Detect()

        logger.info("Canvas initialized")

    def eventFilter(self, object, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self.view.zoom_fit()
        return super().eventFilter(object, event)

    def set_project(self, project):
        self.project = project
        self.schema.set_project(project)
        self.group.set_project(project)
        self.detect.set_project(project)
        self.ui.enable_auto_annotate.setChecked(self.project.config['aannotate']['enable'])

    def get_color_by_type(self, type):
        categories = [category for category in self.project.schema.categories if category.type == type]
        if 0 == len(categories):
            categories = self.project.schema.categories
        if 0 != len(categories):
            return type, QColor(categories[0].color)
        return 0, QColor("#000000")

    def load(self, labeling: LabelingDataItem):
        self.labeling = labeling

        self.pixmap = QGraphicsPixmapItem(QPixmap(str(self.labeling.image())))
        self.pixmap.setZValue(0)

        self.view.set_pixmap_item(self.pixmap)

        self.scene.clear()
        self.scene.addItem(self.pixmap)
        self.scene.setSceneRect(self.pixmap.boundingRect())

        QTimer.singleShot(0, self.view.zoom_fit)

        if self.labeling.operations is None:
            self.labeling.operations = Operations(self)
            group = self.labeling.group.model_copy(deep=True) if self.labeling.labeled() else LabelGroup()
            self.labeling.operations.record(group)
            self.labeling.operations.dirty_state_changed.connect(self._on_dirty_state_changed)
            self.labeling.operations.set_dirty(False)

        self.labeling.operations.refresh()
        self.labeling.operations.set_dirty()

        if self.ui.enable_auto_annotate.isChecked() and len(self.labeling.group.labels) == 0:
            self.on_auto_annotate()

    def save(self):
        if self.labeling is None:
            return
        self.labeling.update_label_group(self._build_current_label_group())
        if self.labeling.operations.dirty:
            self.on_label_group_saved.emit()
        self.labeling.operations.set_dirty(False)

    def on_auto_annotate(self):
        if self.labeling is None:
            return
        group = self.detect.infer(str(self.labeling.image()))
        if group is not None:
            self.labeling.operations.record(group)
            self.labeling.operations.refresh()
            self.labeling.operations.set_dirty()

    def enable_auto_annotate(self):
        if self.project is None:
            return
        self.project.config["aannotate"]["enable"] = self.ui.enable_auto_annotate.isChecked()
        self.project.config.save()

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
        QShortcut(QKeySequence("Ctrl+S"), self.view).activated.connect(self.save)  # Ctrl+S 保存
        QShortcut(QKeySequence("Ctrl+]"), self.view).activated.connect(self.view.zoom_in)  # Delete 放大
        QShortcut(QKeySequence("Ctrl+["), self.view).activated.connect(self.view.zoom_out)  # Delete 缩小

        delete_func = lambda: self.set_paint_cmd(PaintCommand.PCMD_DELETE)
        QShortcut(QKeySequence("Delete"), self.view).activated.connect(delete_func)  # Delete 删除
        QShortcut(QKeySequence("Backspace"), self.view).activated.connect(delete_func)  # Delete 删除

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

        # 自动标注工具
        self.ui.auto_annotate_label.clicked.connect(self.on_auto_annotate)
        self.ui.enable_auto_annotate.stateChanged.connect(self.enable_auto_annotate)

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
        self._cancel_selection()
        if self.labeling is None:
            return
        if self.editing is None:
            if len(self.scene.selectedItems()) > 0:
                self._inform_selected_items()
                return
            if self.command == PaintCommand.PCMD_ARROR:
                return
            self.editing = GraphicsFactory.create(self.command, id=self._generate_label_instance_id())
            category = self.schema.focused_category()
            if category is not None:
                type, color = self.get_color_by_type(category.type)
                self.editing.set_type(type, color)
            self.scene.addItem(self.editing)
        self.editing.commit_point(Point(x=x, y=y))
        self.scene.update()

    def _on_mouse_left_double_clicked(self, x, y):
        self._cancel_selection()
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
        self._cancel_selection()
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

    def _cancel_selection(self):
        items = self.scene.items()
        items = [item for item in items if not isinstance(item, Anchor) and not item.isSelected()]
        for item in items:
            item.itemChange(QGraphicsItem.GraphicsItemChange.ItemSelectedChange, 0)

    def _build_current_label_group(self):
        items = self.scene.items()
        items = [item for item in items if not isinstance(item, Anchor) and not isinstance(item, QGraphicsPixmapItem)]
        group = LabelGroup()
        for item in items:
            group.labels.append(item.label())
        return group

    def _record_operation(self, inform=True):
        if self.labeling is None:
            return
        self.labeling.operations.record(self._build_current_label_group(), inform)

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
            self._record_operation(False)  # 判断有item移动 则记录操作
        self.moving_item_position = None

    def _on_dirty_state_changed(self, dirty):
        # 更新保存按钮的图标
        self.ui.save.setIcon(qta.icon('mdi.content-save-alert' if dirty else 'mdi.content-save'))

    def _on_label_schema_changed(self, schema: LabelSchema):
        if self.labeling is None:
            return
        self.labeling.operations.refresh()

    def _on_label_group_changed(self, changes: LabelGroup):
        if self.labeling is None:
            return
        ids = [label.id for label in changes.labels]
        group = self._build_current_label_group()
        group.labels = [label for label in group.labels if label.id in ids]  # 通过table删除item
        for label in group.labels:
            for change in changes.labels:
                if label.id == change.id:
                    label.type = change.type
                    label.visible = change.visible
        self.labeling.operations.show_label_group(group)
        self._record_operation()

    def _on_label_instance_selected(self, ids):
        items = self.scene.items()
        items = [item for item in items if not isinstance(item, Anchor) and not isinstance(item, QGraphicsPixmapItem)]
        for item in items:
            item.setSelected(item.label().id in ids)

    def _generate_label_instance_id(self):
        ids = set()
        maxid = 512
        for label in self._build_current_label_group().labels:
            ids.add(label.id)
        for id in range(maxid):
            if id not in ids:
                return id
        return maxid

    def _on_type_specified(self, type):
        if self.schema is None:
            return
        if not self.schema.focus_category_by_type(type):
            return
        type, color = self.get_color_by_type(type)
        for item in self.scene.selectedItems():
            if isinstance(item, Anchor):
                continue
            item.set_type(type, color)
        self._record_operation()

    def _on_scale_changed(self, scale):
        if self.labeling is None:
            return
        self.labeling.operations.refresh()

    def _inform_selected_items(self):
        if self.group is None:
            return
        selected = [item for item in self.scene.selectedItems() if not isinstance(item, Anchor)]
        self.group.set_selected_label_instance(set([item.label().id for item in set(selected)]))
        for item in self.scene.items():
            if isinstance(item, Anchor):
                continue
            item.setZValue(1 if item in selected else 0)
