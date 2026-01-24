# -*- coding: utf-8 -*-
from resource.project_manager_ui import Ui_Dialog as Ui_ProjectDialog
from resource.project_create_ui import Ui_Dialog as Ui_CreateDialog

from utils.logger import logger
from utils.config import Config
from models.data import AnnotationTaskType
from models.exporter.yolo_det_exporter import YOLOMultiProjectExporter
from project.project import Project

from PyQt6.QtCore import pyqtSignal, QSize, Qt
from PyQt6.QtGui import QFont, QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QTableView, QHeaderView, QFileDialog, QPushButton, QDialog, QMessageBox

from pathlib import Path

import qtawesome as qta


class CreateDialog(QDialog):
    project_created = pyqtSignal(Project)  # 业务类型, 任务类型, 项目目录, 备注信息

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_CreateDialog()
        self.ui.setupUi(self)

        self.ui.accept.clicked.connect(self._accept)
        self.ui.rejust.clicked.connect(self._reject)

        self.ui.schema.addItems([t['name'] for t in Config['schemas']])
        self.ui.task.addItems([t.value for t in AnnotationTaskType])

        self.ui.scan.setIcon(qta.icon('ph.folder-open-light'))
        self.ui.scan.clicked.connect(self._on_select_directory_clicked)
        self.ui.scan.setToolTip('选择项目目录')

    def _accept(self):
        schema = self.ui.schema.currentText()
        task = self.ui.task.currentText()
        dir = self.ui.directory.text()
        desc = self.ui.description.toPlainText()

        directory = Path(dir)
        if not directory.exists() or not directory.is_absolute():
            QMessageBox.warning(self, "目录不存在", "请选择一个存在的项目目录")
            return

        try:
            project = Project.create(dir, schema, task, desc)
        except Exception as e:
            QMessageBox.warning(self, "创建项目失败", str(e))
            return

        self.project_created.emit(project)
        return super().accept()

    def _reject(self):
        return super().reject()

    def _on_select_directory_clicked(self):
        directory = QFileDialog.getExistingDirectory(
            self,  # 父窗口
            "选择项目目录",  # 对话框标题
            "",  # 初始目录，为空则从默认目录开始
            QFileDialog.Option.ShowDirsOnly,  # （可选）只显示目录的选项
        )

        # 如果用户选择了目录(没有点击取消)
        if directory:
            self.ui.directory.setText(directory)


class ProjectManagerDialog(QDialog):
    # 定义信号，用于传递对话框结果
    project_opened = pyqtSignal(Project)  # 业务类型, 任务类型, 项目目录, 备注信息

    def __init__(self, parent=None):
        super().__init__(parent)

        self.projects = []
        for directory in Config['projects']:
            try:
                project = Project(directory)
                self.projects.append(project)
                logger.info(f"加载项目成功: {directory}")
            except Exception as e:
                logger.error(f"加载项目失败: {directory}, 错误信息: {e}")

        # 创建UI实例
        self.ui = Ui_ProjectDialog()
        self.ui.setupUi(self)

        super().setWindowIcon(qta.icon('ei.livejournal'))

        self.ui.create.setIcon(qta.icon('fa5s.plus-square'))
        self.ui.create.clicked.connect(self._on_create_project_clicked)
        self.ui.create.setToolTip("创建项目")

        self.ui.remove.setIcon(qta.icon('fa5s.minus-square'))
        self.ui.remove.clicked.connect(self._on_remove_project_clicked)
        self.ui.remove.setToolTip("删除项目")

        self.ui.open.setIcon(qta.icon('mdi6.book-open-outline'))
        self.ui.open.setIconSize(QSize(25, 25))
        self.ui.open.clicked.connect(self._on_open_project_clicked)
        self.ui.open.setToolTip("打开项目")

        self.ui.scan.setIcon(qta.icon('ph.folder-open-light'))
        self.ui.scan.clicked.connect(self._on_select_directory_clicked)
        self.ui.scan.setToolTip('选择导出目录')

        self.ui.export.setIcon(qta.icon('mdi6.file-export-outline'))
        self.ui.export.clicked.connect(self._on_annotation_export_clicked)

        self.ui.export_progress.setVisible(False)

        self.ui.valset_ratio.setText('20%')

        # 初始化UI
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""

        # 勾选 项目名称 项目位置 业务类型 任务类型 创建时间 总帧数 标注进度 备注信息 导入数据 删除项目

        font = QFont()
        font.setPointSize(9)  # 设置字体大小
        self.ui.projects.setFont(font)
        self.ui.projects.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.ui.projects.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ui.projects.verticalHeader().setDefaultSectionSize(20)

        # # 设置居中图标委托
        # self.ui.projects.setItemDelegate(IconDelegate())

        title = [
            {'name': '', 'size': 20, 'mode': QHeaderView.ResizeMode.Fixed},
            {'name': '创建时间', 'size': 20, 'mode': QHeaderView.ResizeMode.ResizeToContents},
            {'name': '业务类型', 'size': 80, 'mode': QHeaderView.ResizeMode.Fixed},
            # {'name': '任务类型', 'size': 20, 'mode': QHeaderView.ResizeMode.Fixed},
            # {'name': '标注进度', 'size': 80, 'mode': QHeaderView.ResizeMode.ResizeToContents},
            {'name': '项目位置', 'size': 200, 'mode': QHeaderView.ResizeMode.ResizeToContents},
            {'name': '备注信息', 'size': 200, 'mode': QHeaderView.ResizeMode.Stretch},
            {'name': '', 'size': 40, 'mode': QHeaderView.ResizeMode.Fixed},
        ]

        self.model = QStandardItemModel()

        self.model.setHorizontalHeaderLabels([col['name'] for col in title])
        self.ui.projects.setModel(self.model)

        # 表头宽度设置
        header = self.ui.projects.horizontalHeader()
        for i in range(len(title)):
            header.setSectionResizeMode(i, title[i]['mode'])  # 第 0 列根据内容调整宽度
            header.resizeSection(i, title[i]['size'])  # 设置初始宽度为100

        for project in self.projects:
            self._show_project(project)

    def _show_project(self, project: Project):
        row, col = self.model.rowCount(), 0

        check = QStandardItem()
        check.setCheckable(True)
        check.setCheckState(Qt.CheckState.Unchecked)
        check.setEditable(True)
        self.model.setItem(row, col, check)
        col += 1

        item = QStandardItem(project.config['creation'])
        item.setEditable(False)
        self.model.setItem(row, col, item)
        col += 1

        item = QStandardItem(project.config['mschema']['name'])
        item.setEditable(False)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.model.setItem(row, col, item)
        col += 1

        # item = QStandardItem('20%[(123,34)/157]')
        # item.setEditable(False)
        # self.model.setItem(row, col, item)
        # col += 1

        item = QStandardItem(project.config['directory'])
        item.setEditable(False)
        self.model.setItem(row, col, item)
        col += 1

        item = QStandardItem(project.config['description'])
        item.setEditable(False)
        self.model.setItem(row, col, item)
        col += 1

        button = QPushButton()
        button.setIcon(qta.icon('mdi6.database-import'))
        button.clicked.connect(lambda checked, r=row: self._import_data(r))
        self.ui.projects.setIndexWidget(self.model.index(row, col), button)
        col += 1

    def _on_project_created(self, project: Project):
        self.projects.append(project)
        directories = [str(project.directory) for project in self.projects]
        Config['projects'] = directories
        Config.save()
        self._show_project(project)

    def _on_create_project_clicked(self):
        dialog = CreateDialog()
        dialog.project_created.connect(self._on_project_created)
        dialog.exec()

    def _on_remove_project_clicked(self):
        for row in range(self.model.rowCount() - 1, -1, -1):
            item = self.model.item(row, 0)
            if item.checkState() == Qt.CheckState.Checked:
                directory = self.model.item(row, 4).text()
                self.projects = [p for p in self.projects if p.config['directory'] != directory]
                self.model.removeRow(row)

                Config['projects'] = [str(p.directory) for p in self.projects]
                Config.save()

    def _on_open_project_clicked(self):
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 0)
            if item.checkState() == Qt.CheckState.Checked:
                self._open_project(row)
                break
        return super().accept()

    def _open_project(self, index):
        if index >= len(self.projects):
            return
        self.project_opened.emit(self.projects[index])
        Config['focus'] = index
        Config.save()

    def open_project(self):
        self._open_project(Config['focus'])

    def _on_select_directory_clicked(self):
        directory = QFileDialog.getExistingDirectory(
            self,  # 父窗口
            "选择导出目录",  # 对话框标题
            "",  # 初始目录，为空则从默认目录开始
            QFileDialog.Option.ShowDirsOnly,  # （可选）只显示目录的选项
        )
        # 如果用户选择了目录（没有点击取消）
        if directory:
            self.ui.destination.setText(directory)

    def _on_annotation_export_clicked(self):
        directory = Path(self.ui.destination.text())
        if not directory.exists() or not directory.is_absolute():
            QMessageBox.warning(self, "导出目录不合法", "请指定合法的导出目录")
            return

        indices = self._get_checked_project_indices()
        for idx in indices:
            logger.info(f"select project {self.projects[idx].directory}")

        self.ui.export_progress.setVisible(True)

        exporter = YOLOMultiProjectExporter()
        exporter.process.connect(lambda p, t: self.ui.export_progress.setValue(int(p / t * 100)))
        exporter.export(
            [self.projects[idx] for idx in indices],
            directory,
            train_ratio=1 - float(self.ui.valset_ratio.text().rstrip('%')) / 100,
            random_seed=0,
        )

        self.ui.export_progress.setVisible(False)

        logger.info(f"导出项目{str(directory)}")

    def _import_data(self, row):
        logger.info(f'{self.projects[row].directory} 导入数据')

        # 选择多个图片或视频文件
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片或视频文件",
            "",
            "媒体文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.mpg *.mpeg *.webm *.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif);;"
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.mpg *.mpeg *.webm);;"
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif);;"
            "所有文件 (*.*)",
        )

        if filenames:
            self.projects[row].import_media(filenames)

    def _get_checked_project_indices(self):
        """返回所有被勾选项目的行索引列表"""
        checked_indices = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 0)  # 第一列是复选框
            if item and item.checkState() == Qt.CheckState.Checked:
                checked_indices.append(row)
        return checked_indices
