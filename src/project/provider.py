# -*- coding: utf-8 -*-
from utils.logger import logger
from project.project import Project
from models.data import LabelGroup, ProjectFilterConfig, TimeFilterMode, TimeLogicType

from PyQt6.QtCore import pyqtSignal, QObject, Qt, QTimer, QDateTime
from PyQt6.QtGui import QFont, QStandardItemModel, QStandardItem, QAction, QCursor
from PyQt6.QtWidgets import QTableView, QHeaderView, QMenu, QStyledItemDelegate

import qtawesome as qta

import datetime
import platform
from typing import Dict


class LabelingDataItem:
    def __init__(self, filekey: str, project: Project):
        self.filekey = filekey
        self.project = project
        self.create = None  # 创建时间
        self.modify = None  # 修改时间
        self.group = LabelGroup()  # 标注结果
        self.operations = None  # 用于undo/redo

        self._load_label_group()

    def image(self):
        return self.project.image_path(self.filekey)

    def update_label_group(self, group: LabelGroup):
        group.ignored = self.group.ignored
        self.group = group
        self._save_label_group()
        self.modify = datetime.datetime.now()

    def remove_label_group(self):
        file = self.project.label_path(self.filekey)
        file.unlink(missing_ok=True)
        self.group = LabelGroup()
        self.modify = None

    def ignore(self, ignored: bool):
        self.group.ignored = ignored
        self._save_label_group()

    def ignored(self) -> bool:
        return self.group.ignored

    def labeled(self) -> bool:
        return len(self.group.labels) != 0

    def _save_label_group(self):
        file = self.project.label_path(self.filekey)
        with open(str(file), 'w', encoding='utf-8') as f:
            f.write(self.group.model_dump_json(indent=4))

    def _load_label_group(self):
        self.create = self.project.storage.get_create_time(self.filekey)

        file = self.project.label_path(self.filekey)
        if file.exists() is False:
            self.group = LabelGroup()
            return

        timestamp = file.stat().st_mtime
        self.modify = datetime.datetime.fromtimestamp(timestamp)

        with open(file, 'r', encoding='utf-8') as f:
            self.group = LabelGroup.model_validate_json(f.read())


class IconDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # 获取图标
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if icon is not None:
            # 计算居中位置
            icon_size = option.rect.height() - 4
            x = option.rect.left() + (option.rect.width() - icon_size) / 2
            y = option.rect.top() + 2

            # 绘制图标
            icon.paint(painter, int(x), int(y), icon_size, icon_size, Qt.AlignmentFlag.AlignCenter)
        else:
            # 如果没有图标，使用默认绘制
            super().paint(painter, option, index)


class Provider(QObject):
    activate_dataitem = pyqtSignal(LabelingDataItem)

    def __init__(self, ui, parent=None):
        super().__init__(parent)

        self.ui = ui
        self.project = None

        self._begin = None
        self._end = None
        self._mode = TimeFilterMode.TIME_CREATE

        self._index_filter = None
        self._label_num_fiter = None
        self._label_type_filter = None
        self._show_ignored = False
        self._show_labeled = False

        self.original: Dict[str, LabelingDataItem] = {}
        self.filtered: Dict[str, LabelingDataItem] = {}

        self._init_images_ui()

    def set_project(self, project: Project):
        self.project = project
        self._init_filter_ui()
        self.refresh_pictures_table()
        if len(self.filtered) > 0:
            QTimer.singleShot(0, lambda: self.activate_dataitem.emit(list(self.filtered.values())[0]))

    def refresh_pictures_table(self):
        self._make_original()
        self._do_filter()

        self.model.removeRows(0, self.model.rowCount())
        for _, data in self.filtered.items():
            row, col = self.model.rowCount(), 0

            item = QStandardItem(data.modify.strftime('%Y-%m-%d %H:%M:%S') if data.modify else 'N/A')
            item.setEditable(False)
            ctime = data.create.strftime('%Y-%m-%d %H:%M:%S')
            # types = set([str(label.type) for label in data.group.labels])
            # labeltip = '包含标签' + ','.join(types) if types else '无标签'
            # item.setToolTip(f'创建时间:{ctime} {labeltip}')
            self.model.setItem(row, col, item)
            col += 1

            item = QStandardItem(str(len(data.group.labels)))
            item.setEditable(False)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.model.setItem(row, col, item)
            col += 1

            # 忽略按钮
            item = QStandardItem()
            item.setIcon(qta.icon('msc.circle-filled', color='#00FF00' if not data.ignored() else '#FF0000'))
            item.setEditable(False)
            self.model.setItem(row, col, item)
            col += 1

            item = QStandardItem()
            item.setIcon(qta.icon('mdi.delete-circle-outline', color='#808080'))
            item.setEditable(False)
            self.model.setItem(row, col, item)

        labeled = [key for key, value in self.original.items() if value.labeled()]
        ignored = [key for key, value in self.original.items() if value.ignored()]
        self.ui.progress.setMaximum(len(self.original))
        self.ui.progress.setValue(len(labeled) + len(ignored))
        self.ui.ratio.setText(f'({len(labeled) + len(ignored)}/{len(self.original)})')

        self._save_filter_config()

    def _init_images_ui(self):
        """初始化UI"""
        font = QFont()
        font.setPointSize(9)  # 设置字体大小
        self.ui.pictures.setFont(font)
        self.ui.pictures.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.ui.pictures.verticalHeader().setDefaultSectionSize(20)

        # 设置表头
        title = [
            # {'name': '创建时间', 'size': 20, 'mode': QHeaderView.ResizeMode.ResizeToContents},
            {'name': '修改时间', 'size': 200, 'mode': QHeaderView.ResizeMode.Stretch},
            {'name': '标签数', 'size': 80, 'mode': QHeaderView.ResizeMode.ResizeToContents},
            # {'name': '标签类别', 'size': 200, 'mode': QHeaderView.ResizeMode.Stretch},
            {'name': '忽略', 'size': 32, 'mode': QHeaderView.ResizeMode.Fixed},
            {'name': '删除', 'size': 32, 'mode': QHeaderView.ResizeMode.Fixed},
        ]
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels([col['name'] for col in title])
        self.ui.pictures.setModel(self.model)
        ## 表头宽度设置
        header = self.ui.pictures.horizontalHeader()
        for i in range(len(title)):
            header.setSectionResizeMode(i, title[i]['mode'])  # 第 0 列根据内容调整宽度
            header.resizeSection(i, title[i]['size'])  # 设置初始宽度为100

        # 支持数据添加(拖拽)
        self.ui.pictures.setDragDropMode(QTableView.DragDropMode.DropOnly)
        self.ui.pictures.setDragEnabled(False)  # 禁止内部拖动
        self.ui.pictures.setAcceptDrops(True)  # 确保接受拖放
        self.ui.pictures.setDropIndicatorShown(True)  # 设置放置指示器
        self.ui.pictures.dragEnterEvent = lambda event: event.acceptProposedAction()  # 处理拖拽进入事件
        self.ui.pictures.dragMoveEvent = lambda event: event.acceptProposedAction()  # 处理拖拽移动事件
        self.ui.pictures.dropEvent = self._create_labeling_items  # 处理放置事件

        # 支持删除数据
        self.menu = QMenu()
        action = QAction(self.menu)
        action.setText("删除")
        action.triggered.connect(self._remove_labeling_items)
        self.menu.addAction(action)
        self.ui.pictures.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # 打开右键菜单的策略
        self.ui.pictures.customContextMenuRequested.connect(self._on_context_menu_requested)  # 绑定事件(删除按钮)

        # 支持忽略数据
        action = QAction(self.menu)
        action.setText("忽略数据")
        action.triggered.connect(self._ignore_labeling_items)
        self.menu.addAction(action)
        self.ui.pictures.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # 打开右键菜单的策略
        self.ui.pictures.customContextMenuRequested.connect(self._on_context_menu_requested)  # 绑定事件(忽略按钮)

        # 支持忽略数据
        action = QAction(self.menu)
        action.setText("取消忽略")
        action.triggered.connect(self._unignore_labeling_items)
        self.menu.addAction(action)
        self.ui.pictures.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # 打开右键菜单的策略
        self.ui.pictures.customContextMenuRequested.connect(self._on_context_menu_requested)  # 绑定事件(取消忽略按钮)

        # 支持选定item
        self.ui.pictures.selectionModel().selectionChanged.connect(self._on_picture_selection_changed)
        # 点击设置是否忽略item
        self.ui.pictures.clicked.connect(self._on_table_cell_clicked)
        # 设置忽略item居中显示
        self.ui.pictures.setItemDelegate(IconDelegate())

    def _init_filter_ui(self):
        if self.project is None:
            return
        mfilter = ProjectFilterConfig.model_validate(self.project.config['mfilter'])

        self.ui.show_ignored_images.stateChanged.connect(self.refresh_pictures_table)
        self.ui.show_labeled_images.stateChanged.connect(self.refresh_pictures_table)

        self.ui.show_ignored_images.setChecked(mfilter.show_ignored_images)
        self.ui.show_labeled_images.setChecked(mfilter.show_labeled_images)

        self.ui.mode.addItems(TimeFilterMode.values())
        self.ui.mode.setCurrentIndex(TimeFilterMode.values().index(mfilter.time_filter.mode))
        self.ui.mode.currentIndexChanged.connect(self.refresh_pictures_table)

        self.ui.type.addItems(TimeLogicType.values())
        self.ui.type.setCurrentIndex(TimeLogicType.values().index(mfilter.time_filter.type))
        self.ui.type.currentIndexChanged.connect(self.refresh_pictures_table)

        self.ui.time.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.ui.time.setCalendarPopup(True)  # 启用日历弹出
        self.ui.time.setDateTime(QDateTime.fromString(mfilter.time_filter.time, 'yyyy-MM-dd HH:mm:ss'))
        self.ui.time.dateTimeChanged.connect(self.refresh_pictures_table)

        self.ui.image_index_filter.setText(','.join([str(i) for i in mfilter.image_index.indices]))
        self.ui.image_index_filter.textChanged.connect(self.refresh_pictures_table)
        self.ui.reverse_image_index_filter.setChecked(mfilter.image_index.reverse)
        self.ui.reverse_image_index_filter.stateChanged.connect(self.refresh_pictures_table)

        self.ui.label_num_fiter.setText(','.join([str(i) for i in mfilter.label_num.indices]))
        self.ui.label_num_fiter.textChanged.connect(self.refresh_pictures_table)
        self.ui.reverse_label_num_fiter.setChecked(mfilter.label_num.reverse)
        self.ui.reverse_label_num_fiter.stateChanged.connect(self.refresh_pictures_table)

        self.ui.label_category_filter.setText(','.join([str(i) for i in mfilter.label_category.indices]))
        self.ui.label_category_filter.textChanged.connect(self.refresh_pictures_table)
        self.ui.reverse_label_category_filter.setChecked(mfilter.label_category.reverse)
        self.ui.reverse_label_category_filter.stateChanged.connect(self.refresh_pictures_table)

    def _save_filter_config(self):
        if self.project is None:
            return
        mfilter = ProjectFilterConfig.model_validate(self.project.config['mfilter'])

        mfilter.show_ignored_images = self.ui.show_ignored_images.isChecked()
        mfilter.show_labeled_images = self.ui.show_labeled_images.isChecked()

        mfilter.time_filter.mode = self.ui.mode.currentText()
        mfilter.time_filter.type = self.ui.type.currentText()
        mfilter.time_filter.time = self.ui.time.dateTime().toPyDateTime().strftime('%Y-%m-%d %H:%M:%S')

        mfilter.image_index.indices = [int(i) for i in self.ui.image_index_filter.text().split(',') if i.isdigit()]
        mfilter.image_index.reverse = self.ui.reverse_image_index_filter.isChecked()

        mfilter.label_num.indices = [int(i) for i in self.ui.label_num_fiter.text().split(',') if i.isdigit()]
        mfilter.label_num.reverse = self.ui.reverse_label_num_fiter.isChecked()
        # fmt: off
        mfilter.label_category.indices = [int(i) for i in self.ui.label_category_filter.text().split(',') if i.isdigit()]
        mfilter.label_category.reverse = self.ui.reverse_label_category_filter.isChecked()
        # fmt: on

        self.project.config['mfilter'] = mfilter.model_dump()
        self.project.config.save()

    def _on_picture_selection_changed(self, selected, deselected):
        selected_rows = selected.indexes()
        if not selected_rows:
            return
        key = list(self.filtered.keys())[selected_rows[0].row()]
        self.activate_dataitem.emit(self.filtered[key])

    def _make_original(self):
        self.original = {}
        if self.project is None:
            return
        for filekey in self.project.filekeys():
            self.original[filekey] = LabelingDataItem(filekey, self.project)

    def _do_filter(self):
        self.filtered = self.original.copy()

        if not self.ui.show_ignored_images.isChecked():
            self.filtered = {key: value for key, value in self.filtered.items() if not value.ignored()}

        if not self.ui.show_labeled_images.isChecked():
            self.filtered = {key: value for key, value in self.filtered.items() if not value.labeled()}

        if self.ui.mode.currentText() != TimeFilterMode.TIME_NONE.value:
            mode = self.ui.mode.currentText()
            logic = self.ui.type.currentText()
            time = self.ui.time.dateTime().toPyDateTime()
            if mode == TimeFilterMode.TIME_CREATE.value:
                if logic == TimeLogicType.LOGIC_GT.value:
                    self.filtered = {
                        key: value for key, value in self.filtered.items() if value.create and value.create > time
                    }
                else:
                    self.filtered = {
                        key: value for key, value in self.filtered.items() if value.create and value.create < time
                    }
            else:
                if logic == TimeLogicType.LOGIC_GT.value:
                    self.filtered = {
                        key: value for key, value in self.filtered.items() if value.modify and value.modify > time
                    }
                else:
                    self.filtered = {
                        key: value for key, value in self.filtered.items() if value.modify and value.modify < time
                    }

        if self.ui.image_index_filter.text().strip() != '':
            indices = [int(i) for i in self.ui.image_index_filter.text().split(',') if i.isdigit()]
            if self.ui.reverse_image_index_filter.isChecked():
                self.filtered = {
                    key: value for idx, (key, value) in enumerate(self.filtered.items()) if idx not in indices
                }
            else:
                self.filtered = {key: value for idx, (key, value) in enumerate(self.filtered.items()) if idx in indices}

        if self.ui.label_num_fiter.text().strip() != '':
            nums = [int(i) for i in self.ui.label_num_fiter.text().split(',') if i.isdigit()]
            if self.ui.reverse_label_num_fiter.isChecked():
                self.filtered = {
                    key: value for key, value in self.filtered.items() if len(value.group.labels) not in nums
                }
            else:
                self.filtered = {key: value for key, value in self.filtered.items() if len(value.group.labels) in nums}

        if self.ui.label_category_filter.text().strip() != '':
            types = [int(i) for i in self.ui.label_category_filter.text().split(',') if i.isdigit()]
            if self.ui.reverse_label_category_filter.isChecked():
                self.filtered = {
                    key: value
                    for key, value in self.filtered.items()
                    if all(label.type not in types for label in value.group.labels)
                }
            else:
                self.filtered = {
                    key: value
                    for key, value in self.filtered.items()
                    if any(label.type in types for label in value.group.labels)
                }

    def _on_context_menu_requested(self):
        self.menu.move(QCursor.pos())
        self.menu.show()

    def _create_labeling_items(self, e):
        if self.project is None:
            return

        ostype = platform.system()
        if ostype != 'Windows' and ostype != 'Linux':
            raise RuntimeError('Do not support current os:', ostype)

        delimiter, subpos = ('\n', 8) if ostype == 'Windows' else ('\r\n', 7)
        files = [file[subpos:] for file in e.mimeData().text().split(delimiter)]
        self.project.import_media(files)
        self.refresh_pictures_table()

    def _remove_labeling_items(self):
        if self.project is None:
            return
        # 获取所有选中行的索引（避免重复删除同一行）
        selected_rows = set([index.row() for index in self.ui.pictures.selectionModel().selectedRows()])
        # 从大到小删除（避免行号变化导致错误）
        for row in sorted(selected_rows, reverse=True):
            values = list(self.filtered.values())
            if row >= len(values):
                continue
            self.project.remove(values[row].filekey)
        self.refresh_pictures_table()

    def _ignore_labeling_items(self):
        if self.project is None:
            return
        # 获取所有选中行的索引（避免重复删除同一行）
        selected_rows = set([index.row() for index in self.ui.pictures.selectionModel().selectedRows()])
        for index, data in enumerate(self.filtered.values()):
            if index in selected_rows:
                data.ignore(True)
        self.refresh_pictures_table()

    def _unignore_labeling_items(self):
        if self.project is None:
            return
        # 获取所有选中行的索引（避免重复删除同一行）
        selected_rows = set([index.row() for index in self.ui.pictures.selectionModel().selectedRows()])
        for index, data in enumerate(self.filtered.values()):
            if index in selected_rows:
                data.ignore(False)
        self.refresh_pictures_table()

    def _on_table_cell_clicked(self, index):
        """处理单元格点击事件"""
        if not index.isValid():
            return
        row, col = index.row(), index.column()
        if col != 2 and col != 3:
            return

        if row >= len(self.filtered):
            return

        data = list(self.filtered.values())[row]

        if col == 2:
            data.ignore(not data.ignored())
            item = self.model.item(row, col)
            item.setIcon(qta.icon('msc.circle-filled', color='#00FF00' if not data.ignored() else '#FF0000'))

        if col == 3:
            self.project.remove(data.filekey)

        self.refresh_pictures_table()
