# -*- coding: utf-8 -*-
from models.data import PaintCommand, LabelInstance, GraphicsType
from canvas.graphics.graphics import *

from PyQt6.QtWidgets import QGraphicsItem

from typing import Optional


class GraphicsFactory:
    """图形项工厂,根据GraphicsType创建对应的图形项"""

    @staticmethod
    def create(cmd: PaintCommand, id: int = 0) -> Optional[QGraphicsItem]:
        """根据LabelInstance创建对应的图形项"""
        itemtbl = {
            PaintCommand.PCMD_LINESEG: Segment,
            PaintCommand.PCMD_RECTANGLE: Rectangle,
            PaintCommand.PCMD_POLYLINE: Polyline,
            PaintCommand.PCMD_POLYGON: Polygon,
            PaintCommand.PCMD_KEYPOINT: Keypoint,
        }

        item_class = itemtbl.get(cmd)
        return item_class(id) if item_class else None

    @staticmethod
    def from_label(label: LabelInstance):
        itemtbl = {
            GraphicsType.GT_LINESEG: PaintCommand.PCMD_LINESEG,
            GraphicsType.GT_RECTANGLE: PaintCommand.PCMD_RECTANGLE,
            GraphicsType.GT_POLYLINE: PaintCommand.PCMD_POLYLINE,
            GraphicsType.GT_POLYGON: PaintCommand.PCMD_POLYGON,
            GraphicsType.GT_KEYPOINT: PaintCommand.PCMD_KEYPOINT,
        }

        cmd = itemtbl.get(label.graphics.type)
        if not cmd:
            return None
        graphics = GraphicsFactory.create(cmd)
        if graphics:
            graphics._label = label
            graphics.refresh_shape()
        return graphics
