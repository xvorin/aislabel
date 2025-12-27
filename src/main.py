# -*- coding: utf-8 -*-
import resource.aislabel_ui as aislabel_ui
import aislabel

from PyQt6.QtWidgets import QApplication, QMainWindow

import qtawesome as qta

import sys


if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowIcon(qta.icon('ei.livejournal'))

    ui = aislabel_ui.Ui_MainWindow()
    ui.setupUi(window)

    tool = aislabel.AisLabel(ui)

    window.show()
    sys.exit(app.exec())
