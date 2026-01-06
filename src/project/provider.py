# -*- coding: utf-8 -*-
from utils.logger import logger
from project.project import Project
from models.data import LabelGroup

from PyQt6.QtCore import pyqtSignal, QObject, Qt
from PyQt6.QtGui import QFont, QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QTableView, QHeaderView

import datetime
from enum import Enum
from typing import Dict, List


class LabelingDataItem:
    def __init__(self, filekey: str, project: Project):
        self.filekey = filekey
        self.project = project
        self.create = None  # 创建时间
        self.modify = None  # 修改时间
        self.group = None  # 标注结果
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
        self.group = None
        self.modify = None

    def ignore(self, ignored: bool):
        if self.group is None:
            return
        self.group.ignored = ignored
        self._save_label_group()

    def ignored(self) -> bool:
        return False if self.group is None else self.group.ignored

    def labeled(self) -> bool:
        return self.group is not None

    def _save_label_group(self):
        if self.group is None:
            return
        file = self.project.label_path(self.filekey)
        with open(str(file), 'w', encoding='utf-8') as f:
            f.write(self.group.model_dump_json(indent=4))

    def _load_label_group(self):
        self.create = self.project.storage.get_create_time(self.filekey)

        file = self.project.label_path(self.filekey)
        if file.exists() is False:
            self.group = None
            return

        timestamp = file.stat().st_mtime
        self.modify = datetime.datetime.fromtimestamp(timestamp)

        with open(file, 'r', encoding='utf-8') as f:
            self.group = LabelGroup.model_validate_json(f.read())


class TimeFilterMode(Enum):
    MODIFY_TIME = 1
    CREATE_TIME = 2


class Provider(QObject):
    activate_dataitem = pyqtSignal(LabelingDataItem)

    def __init__(self, ui, parent=None):
        super().__init__(parent)

        self.ui = ui
        self.project = None

        self._begin = None
        self._end = None
        self._mode = TimeFilterMode.MODIFY_TIME

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
        self._make_original()
        self._show_pictures_table()

    def get_items(self) -> List[LabelingDataItem]:
        self._do_filter()
        return self.filtered

    def set_time_filter(self, begin, end, mode: TimeFilterMode):
        pass

    def set_index_filter(self, enable, indices=None):
        pass

    def set_label_num_fiter(self, enable, indices=None):
        pass

    def set_label_type_filter(self, enable, indices=None):
        pass

    def show_ignored_images(self, enable):
        pass

    def show_labeled_images(self, enable):
        pass

    def _init_images_ui(self):
        """初始化UI"""

        # 勾选 项目名称 项目位置 业务类型 任务类型 创建时间 总帧数 标注进度 备注信息 导入数据 删除项目

        font = QFont()
        font.setPointSize(9)  # 设置字体大小
        self.ui.pictures.setFont(font)
        self.ui.pictures.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        # self.ui.pictures.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ui.pictures.verticalHeader().setDefaultSectionSize(20)

        title = [
            # {'name': '创建时间', 'size': 20, 'mode': QHeaderView.ResizeMode.ResizeToContents},
            {'name': '修改时间', 'size': 80, 'mode': QHeaderView.ResizeMode.ResizeToContents},
            {'name': '标签数量', 'size': 200, 'mode': QHeaderView.ResizeMode.Stretch},
            # {'name': '标签类别', 'size': 200, 'mode': QHeaderView.ResizeMode.Stretch},
            {'name': '忽略', 'size': 35, 'mode': QHeaderView.ResizeMode.Fixed},
            {'name': '删除', 'size': 35, 'mode': QHeaderView.ResizeMode.Fixed},
        ]

        self.model = QStandardItemModel()

        self.model.setHorizontalHeaderLabels([col['name'] for col in title])
        self.ui.pictures.setModel(self.model)

        # 表头宽度设置
        header = self.ui.pictures.horizontalHeader()
        for i in range(len(title)):
            header.setSectionResizeMode(i, title[i]['mode'])  # 第 0 列根据内容调整宽度
            header.resizeSection(i, title[i]['size'])  # 设置初始宽度为100

        self.ui.pictures.selectionModel().selectionChanged.connect(self._on_picture_selection_changed)

        self._show_pictures_table()

    def _on_picture_selection_changed(self, selected, deselected):
        selected_rows = selected.indexes()
        if not selected_rows:
            return

        key = list(self.filtered.keys())[selected_rows[0].row()]
        self.activate_dataitem.emit(self.filtered[key])
        # self.ui.pictures.scrollTo(selected_rows[0], QAbstractItemView.ScrollHint.PositionAtCenter)

    def _show_pictures_table(self):
        self._do_filter()

        for _, value in self.filtered.items():
            row = self.model.rowCount()
            col = 0

            item = QStandardItem(value.modify.strftime('%Y-%m-%d %H:%M:%S') if value.modify else 'N/A')
            item.setEditable(False)
            self.model.setItem(row, col, item)
            col += 1

            item = QStandardItem(str(len(value.group.labels)) if value.group else '0')
            item.setEditable(False)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.model.setItem(row, col, item)
            col += 1

            # label_types = set()
            # if value.record:
            #     for label in value.record.labels:
            #         label_types.add(label.label)
            # item = QStandardItem(str(len(label_types)))
            # item.setEditable(False)
            # self.model.setItem(row, col, item)
            # col += 1

            # # 忽略按钮
            # button = QPushButton()
            # button.setIcon(qta.icon('mdi6.database-import'))
            # # button.clicked.connect(lambda checked, r=row: self._import_data(r))
            # self.ui.pictures.setIndexWidget(self.model.index(row, col), button)
            # col += 1

            # # 删除按钮
            # button = QPushButton()
            # button.setIcon(qta.icon('mdi6.database-import'))
            # # button.clicked.connect(lambda checked, r=row: self._import_data(r))
            # self.ui.pictures.setIndexWidget(self.model.index(row, col), button)
            # col += 1

    def _make_original(self):
        self.original = {}
        for filekey in self.project.filekeys():
            self.original[filekey] = LabelingDataItem(filekey, self.project)

    def _do_filter(self):
        self.filtered = self.original.copy()
