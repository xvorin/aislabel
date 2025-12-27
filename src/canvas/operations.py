# -*- coding: utf-8 -*-
from utils.logger import logger
from models.data import LabelGroup
from canvas.graphics.anchor import Anchor
from canvas.graphics.factory import GraphicsFactory

from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem


class Operations(QObject):
    dirty_state_changed = pyqtSignal(bool)

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.history = []
        self.index = -1
        self.dirty = False

    def record(self, labels: LabelGroup):
        self.index += 1
        self.history.insert(self.index, labels.model_copy(deep=True))
        self.history = self.history[: self.index + 1]
        self.set_dirty(True)

    def labels(self, index: int):
        if index < 0 or index >= len(self.history):
            return None
        return self.history[index].model_copy(deep=True)

    def undo(self):
        labels = self.labels(self.index - 1)
        if labels is not None:
            self.show_labels(labels)
            self.index = self.index - 1
            self.set_dirty(True)

    def redo(self):
        labels = self.labels(self.index + 1)
        if labels is not None:
            self.show_labels(labels)
            self.index = self.index + 1
            self.set_dirty(True)

    def show_labels(self, labels: LabelGroup):
        self._clear_items()
        if labels is not None:
            for label in labels.labels:
                graphics = GraphicsFactory.from_label(label)
                if graphics:
                    self.scene.addItem(graphics)
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
