from project.project import Project
from models.data import LabelGroup, LabelInstance

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont, QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QTableView, QHeaderView, QComboBox, QPushButton
from PyQt6.QtCore import QObject, pyqtSignal, QItemSelection, QItemSelectionModel

import qtawesome as qta


class LabelGroupTable(QObject):
    on_label_instance_selected = pyqtSignal(set)
    on_label_group_changed = pyqtSignal(LabelGroup)

    def __init__(self, ui, parent=None):
        super().__init__(parent)
        self.ui = ui
        self.project = None
        self.group = None
        self._init_label_group_ui()

    def set_project(self, project: Project):
        self.project = project

    def set_label_group(self, group: LabelGroup):
        self.group = group
        self._show_label_group_table()

    def set_selected_label_instance(self, ids: set):
        selection = QItemSelection()
        for row in range(self.model.rowCount()):
            id = int(self.model.data(self.model.index(row, 0), Qt.ItemDataRole.DisplayRole))
            if id not in ids:
                continue
            left = self.ui.label_group.model().index(row, 0)
            right = self.ui.label_group.model().index(row, self.ui.label_group.model().columnCount() - 1)
            selection.select(left, right)
        self.ui.label_group.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    def _init_label_group_ui(self):
        """初始化UI"""
        font = QFont()
        font.setPointSize(9)  # 设置字体大小

        self.ui.label_group.setFont(font)
        self.ui.label_group.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.ui.label_group.verticalHeader().setDefaultSectionSize(20)
        self.ui.label_group.setStyleSheet(
            """
            QTableView::item:selected {
                background-color: #2196F3;      /* 选中单元格背景色 */
                color: white;                   /* 选中单元格文字颜色 */
            }
            """
        )

        headers = [
            {'name': '序号', 'size': 30, 'mode': QHeaderView.ResizeMode.Fixed},
            {'name': '标签类型', 'size': 60, 'mode': QHeaderView.ResizeMode.Stretch},
            {'name': '几何类型', 'size': 60, 'mode': QHeaderView.ResizeMode.ResizeToContents},
            {'name': '隐藏', 'size': 35, 'mode': QHeaderView.ResizeMode.Fixed},
            {'name': '删除', 'size': 35, 'mode': QHeaderView.ResizeMode.Fixed},
        ]

        self.model = QStandardItemModel()

        self.model.setHorizontalHeaderLabels([col['name'] for col in headers])
        self.ui.label_group.setModel(self.model)

        # 表头宽度设置
        header = self.ui.label_group.horizontalHeader()
        for i in range(len(headers)):
            header.setSectionResizeMode(i, headers[i]['mode'])  # 第 0 列根据内容调整宽度
            header.resizeSection(i, headers[i]['size'])  # 设置初始宽度为100

        self.ui.label_group.selectionModel().selectionChanged.connect(self._on_label_instance_selection_changed)

    def _on_label_instance_selection_changed(self, selected, deselected):
        label_ids = set()

        for index in self.ui.label_group.selectedIndexes():
            text = self.model.data(self.model.index(index.row(), 0), Qt.ItemDataRole.DisplayRole)
            label_ids.add(int(text))
        self.on_label_instance_selected.emit(label_ids)

    def _show_label_group_table(self):
        self.model.removeRows(0, self.model.rowCount())

        if self.group is None:
            return

        for index, label in enumerate(sorted(self.group.labels, key=lambda label: label.id)):
            row = [str(label.id), label.type, label.graphics.type.value]
            row = [QStandardItem(item) for item in row]
            for item in row:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setEditable(False)
            self.model.appendRow(row)

            # 业务类型下拉框
            types = [category.label for category in self.project.schema.categories]
            type = [category.label for category in self.project.schema.categories if category.type == label.type]
            combo = QComboBox()
            combo.addItems(types)
            combo.setCurrentIndex(0 if len(type) == 0 else types.index(type[0]))
            combo.currentIndexChanged.connect(self._modify_label_instance_type)
            self.ui.label_group.setIndexWidget(self.model.index(index, 1), combo)

            # 隐藏标签按钮
            visible_button = QPushButton()
            visible_button.setIcon(qta.icon('ph.eye' if label.visible else 'ph.eye-closed'))
            visible_button.clicked.connect(self._set_label_instance_visible)
            self.ui.label_group.setIndexWidget(self.model.index(index, 3), visible_button)

            # 删除标签按钮
            delete_button = QPushButton()
            delete_button.setIcon(qta.icon('ri.delete-bin-3-line'))
            delete_button.clicked.connect(self._delete_label_instance)
            self.ui.label_group.setIndexWidget(self.model.index(index, 4), delete_button)

    def _modify_label_instance_type(self):
        combox = self.sender()
        table = self.ui.label_group
        model = self.model
        rows = [row for row in range(model.rowCount()) if table.indexWidget(model.index(row, 1)) is combox]
        ids = [int(model.data(model.index(row, 0), Qt.ItemDataRole.DisplayRole)) for row in rows]
        types = [category.type for category in self.project.schema.categories if category.label == combox.currentText()]
        if len(types) == 0:
            return

        for label in self.group.labels:
            if label.id in ids:
                label.type = types[0]
        self.on_label_group_changed.emit(self.group)

    def _set_label_instance_visible(self):
        visible_button = self.sender()
        table = self.ui.label_group
        model = self.model
        rows = [row for row in range(model.rowCount()) if table.indexWidget(model.index(row, 3)) is visible_button]
        ids = [int(model.data(model.index(row, 0), Qt.ItemDataRole.DisplayRole)) for row in rows]

        for label in self.group.labels:
            if label.id in ids:
                label.visible = not label.visible
                visible_button.setIcon(qta.icon('ph.eye' if label.visible else 'ph.eye-closed'))
        self.on_label_group_changed.emit(self.group)

    def _delete_label_instance(self):
        delete_button = self.sender()
        table = self.ui.label_group
        model = self.model
        rows = [row for row in range(model.rowCount()) if table.indexWidget(model.index(row, 4)) is delete_button]
        ids = [int(model.data(model.index(row, 0), Qt.ItemDataRole.DisplayRole)) for row in rows]

        self.group.labels = [label for label in self.group.labels if label.id not in ids]
        self.on_label_group_changed.emit(self.group)
        self._show_label_group_table()
