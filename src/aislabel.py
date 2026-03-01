# -*- coding: utf-8 -*-
from project.project import Project
from project.provider import Provider, LabelingDataItem
from project.manager import ProjectManagerDialog
from canvas.canvas import Canvas

from PyQt6.QtGui import QAction
from PyQt6.QtCore import QTimer

import qtawesome as qta


class AisLabel:
    def __init__(self, ui):
        self.ui = ui
        self.ui.splitter.setSizes([316, 560, 260])

        self.project = None  # 当前项目

        self.provider = Provider(self.ui)
        self.provider.activate_dataitem.connect(self.on_dataitem_activated)

        media = QAction(qta.icon('ri.file-list-line'), "项目管理", self.ui.tools)
        media.triggered.connect(lambda: self.manager.exec())
        self.ui.tools.addAction(media)
        self.ui.tools.addSeparator()

        self.canvas = Canvas(self.ui)
        self.canvas.on_label_group_saved.connect(self.on_label_group_saved)

        self.manager = ProjectManagerDialog()
        self.manager.project_opened.connect(self.on_project_opened)
        self.manager.open_project()

        self.ui.auto_annotate_label.setIcon(qta.icon('fa5s.magic'))  # fa5s.magic

    def on_project_opened(self, project: Project):
        self.project = project
        self.provider.set_project(self.project)
        self.canvas.set_project(self.project)

    def on_dataitem_activated(self, item: LabelingDataItem):
        self.canvas.load(item)

    def on_label_group_saved(self):
        self.provider.refresh_pictures_table()
        QTimer.singleShot(1, self.provider._on_next_clicked)
