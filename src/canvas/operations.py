# -*- coding: utf-8 -*-
from utils.logger import logger
from models.data import LabelGroup
from canvas.graphics.anchor import Anchor
from canvas.graphics.factory import GraphicsFactory

from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from PyQt6.QtWidgets import QGraphicsPixmapItem


class Operations(QObject):
    dirty_state_changed = pyqtSignal(bool)

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.scene = canvas.scene
        self.history = []
        self.index = -1
        self.dirty = False

    def record(self, group: LabelGroup):
        self.index += 1
        self.history.insert(self.index, group.model_copy(deep=True))
        self.history = self.history[: self.index + 1]
        self.set_dirty(True)
        self.canvas.group.set_label_group(group)  # 通知table数据变化

    def label_group(self, index: int):
        if index < 0 or index >= len(self.history):
            return None
        return self.history[index].model_copy(deep=True)

    def current_label_group(self):
        return self.label_group(self.index)

    def refresh(self):
        group = self.current_label_group()
        self.show_label_group(group)
        self.canvas.group.set_label_group(group)  # 通知table数据变化

    def undo(self):
        group = self.label_group(self.index - 1)
        if group is not None:
            self.show_label_group(group)
            self.index = self.index - 1
            self.set_dirty(True)
            self.canvas.group.set_label_group(group)  # 通知table数据变化

    def redo(self):
        group = self.label_group(self.index + 1)
        if group is not None:
            self.show_label_group(group)
            self.index = self.index + 1
            self.set_dirty(True)
            self.canvas.group.set_label_group(group)  # 通知table数据变化

    def show_label_group(self, group: LabelGroup):
        self._clear_items()
        if group is not None:
            for label in group.labels:
                graphics = GraphicsFactory.from_label(label)
                if graphics:
                    self.scene.addItem(graphics)
                    graphics.setVisible(label.visible)
                    label.type, color = self.canvas.get_color_by_type(label.type)
                    graphics.set_type(label.type, color)
        self.scene.update()

    def set_dirty(self, dirty: bool = None):
        self.dirty = self.dirty if dirty is None else dirty
        self.dirty_state_changed.emit(self.dirty)

    def _clear_items(self):
        items = self.scene.items()
        items = [item for item in items if not isinstance(item, Anchor) and not isinstance(item, QGraphicsPixmapItem)]

        items_tobe_del = []
        for item in items:
            if item.scene():
                items_tobe_del.append(item)
                self.scene.removeItem(item)

        def cleanup():
            items_tobe_del.clear()

        QTimer.singleShot(0, cleanup)
