from project.project import Project
from models.data import LabelSchema, LabelCategory

from PyQt6.QtGui import QFont, QStandardItemModel, QStandardItem, QColor
from PyQt6.QtWidgets import QTableView, QHeaderView, QPushButton, QColorDialog
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QTimer

import qtawesome as qta


class LabelSchemaTable(QObject):
    on_label_schema_changed = pyqtSignal(LabelSchema)

    def __init__(self, ui, parent=None):
        super().__init__(parent)
        self.ui = ui
        self.project = None
        self._init_label_schema_ui()

    def set_project(self, project: Project):
        self.project = project
        self._show_label_schema_table()

    def focused_category(self):
        if self.project is None or 0 == len(self.project.schema.categories):
            return None
        self.selected_row = max(0, min(self.selected_row, len(self.project.schema.categories) - 1))
        return self.project.schema.categories[self.selected_row]

    def focus_category_by_type(self, type):
        if self.project is None:
            return False
        for index, category in enumerate(self.project.schema.categories):
            if category.type == type:
                self.selected_row = index
                self.ui.label_schema.selectRow(self.selected_row)
                return True
        return False

    def _init_label_schema_ui(self):
        font = QFont()
        font.setPointSize(9)  # 设置字体大小

        self.ui.label_schema.setFont(font)
        self.ui.label_schema.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.ui.label_schema.verticalHeader().setDefaultSectionSize(20)
        self.ui.label_schema.setStyleSheet(
            """
            QTableView::item:selected {
                background-color: #2196F3;      /* 选中单元格背景色 */
                color: white;                   /* 选中单元格文字颜色 */
            }
            """
        )

        headers = [
            {'name': '类型编号', 'size': 56, 'mode': QHeaderView.ResizeMode.Fixed},
            {'name': '导出编号', 'size': 56, 'mode': QHeaderView.ResizeMode.Fixed},
            {'name': '类型名称', 'size': 60, 'mode': QHeaderView.ResizeMode.Stretch},
            {'name': '标签颜色', 'size': 60, 'mode': QHeaderView.ResizeMode.ResizeToContents},
        ]

        self.model = QStandardItemModel()

        self.model.setHorizontalHeaderLabels([col['name'] for col in headers])
        self.ui.label_schema.setModel(self.model)
        self.ui.label_schema.selectionModel().selectionChanged.connect(self._on_label_category_selection_changed)
        self.selected_row = 0

        # 表头宽度设置
        header = self.ui.label_schema.horizontalHeader()
        for i in range(len(headers)):
            header.setSectionResizeMode(i, headers[i]['mode'])
            header.resizeSection(i, headers[i]['size'])  # 设置初始宽度

        self.model.itemChanged.connect(self._on_label_schema_changed)
        self.ui.create_label_category.clicked.connect(self._on_create_label_category)
        self.ui.remove_label_category.clicked.connect(self._on_remove_label_category)
        self.ui.create_label_category.setIcon(qta.icon('fa5s.plus-square'))
        self.ui.remove_label_category.setIcon(qta.icon('fa5s.minus-square'))

    def _show_label_schema_table(self):
        self.model.removeRows(0, self.model.rowCount())

        if self.project is None:
            return

        for index, category in enumerate(self.project.schema.categories):
            row = [str(category.type), str(category.export_id), category.label]
            row = [QStandardItem(item) for item in row]
            for item in row:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.model.appendRow(row)

            # 选择颜色按钮
            button = QPushButton()
            button.setStyleSheet("QPushButton {background-color: " + category.color + "; }")
            button.clicked.connect(lambda checked, color=category.color: self._select_color(color))
            self.ui.label_schema.setIndexWidget(self.model.index(index, 3), button)

        self.selected_row = max(0, min(self.selected_row, len(self.project.schema.categories) - 1))
        self.ui.label_schema.selectRow(self.selected_row)

    def _on_label_schema_changed(self, item):
        """当表格数据发生变化时触发"""
        row = item.row()
        col = item.column()
        value = item.text()

        category = self.project.schema.categories[row]
        values = [(category.type, category.export_id, category.label) for category in self.project.schema.categories]
        values = [v[col] for v in values]

        invalid = True
        if col == 0 and value.isdigit() and int(value) not in values:
            category.type, invalid = int(value), False
        if col == 1 and value.isdigit():  # and int(value) not in values:
            category.export_id, invalid = int(value), False
        if col == 2:  # and value not in values:
            category.label, invalid = value, False

        if invalid:
            item.setText(str(values[row]))
        else:
            self._modified_project_schema()

    def _select_color(self, color):
        button = self.sender()
        table = self.ui.label_schema
        model = self.model
        rows = [row for row in range(model.rowCount()) if table.indexWidget(model.index(row, 3)) is button]
        if len(rows) == 0:
            return

        row = rows[0]
        color = QColorDialog.getColor(
            QColor(color),
            self.parent(),
            "选择颜色",
            # QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )

        if color.isValid():
            button.setStyleSheet("QPushButton {background-color: " + color.name() + "; }")
            self.project.schema.categories[row].color = color.name()
            self._modified_project_schema()

    def _on_create_label_category(self):
        type = self._generate_unique_value([category.type for category in self.project.schema.categories])
        export_id = self._generate_unique_value([category.export_id for category in self.project.schema.categories])
        category = LabelCategory(type=type, export_id=export_id, label='', color='#000000', remark='')
        self.project.schema.categories.append(category)
        self._modified_project_schema()

    def _on_remove_label_category(self):
        selected_indexes = self.ui.label_schema.selectionModel().selectedRows()
        rows = sorted([index.row() for index in selected_indexes], reverse=True)
        for row in rows:
            del self.project.schema.categories[row]
            self.model.removeRow(row)
        self._modified_project_schema()

    def _generate_unique_value(self, values):
        for value in range(512):
            if value not in values:
                return value

    def _modified_project_schema(self):
        self.project.schema.categories = sorted(self.project.schema.categories, key=lambda category: category.type)
        self.project.config['mschema'] = self.project.schema.model_dump()
        self.project.config.save()
        self.on_label_schema_changed.emit(self.project.schema)
        QTimer.singleShot(0, self._show_label_schema_table)

    def _on_label_category_selection_changed(self, selected, deselected):
        indexes = self.ui.label_schema.selectedIndexes()
        if len(indexes) == 0:
            self.selected_row = max(0, min(self.selected_row, len(self.project.schema.categories) - 1))
            self.ui.label_schema.selectRow(self.selected_row)
            return
        self.selected_row = indexes[0].row()
        # print('_on_label_category_selection_changed', self.selected_row)
