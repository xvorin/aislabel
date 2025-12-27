# -*- coding: utf-8 -*-
from utils.config import Global

from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtWidgets import QGraphicsRectItem
from PyQt6.QtGui import QPen, QColor, QBrush


class Anchor(QGraphicsRectItem):
    """锚点控制柄"""

    position_changed = pyqtSignal(int, QPointF)  # 索引, 新位置

    def __init__(self, index, pos, parent, cursor=Qt.CursorShape.ArrowCursor):
        super().__init__(parent)
        self.index = index
        self.setPos(pos)
        self.parent = parent
        self.cursor = cursor

        # 设置位置和大小
        anchor_size = 6 / 1280 * Global["image_size"][0]
        self.setRect(anchor_size * -1, anchor_size * -1, anchor_size * 2, anchor_size * 2)
        # 设置样式
        self.setBrush(QBrush(QColor(255, 255, 0)))
        self.setPen(QPen(QColor(0, 0, 0), 1))

        # 启用交互
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

    def itemChange(self, change, value):
        """位置改变时触发"""
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            self.parent.on_anchor_position_changed(self.index, value)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        self.parent.on_ancher_move_begin(self.index, self.mapToScene(event.pos()))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        self.parent.on_ancher_move_end(self.index, self.mapToScene(event.pos()))
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        """鼠标进入Item区域时触发"""
        # 改变鼠标样式为手形
        self.setCursor(self.cursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开Item区域时触发"""
        # 恢复默认的鼠标样式
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(event)
