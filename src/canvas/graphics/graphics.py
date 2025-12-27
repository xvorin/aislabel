# -*- coding: utf-8 -*-
from utils.logger import logger
from utils.config import Global
from models.data import LabelInstance, GraphicsType, Point
from canvas.graphics.anchor import Anchor

from PyQt6.QtCore import QPointF, Qt, QLineF, QRectF, QTimer
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsRectItem, QGraphicsLineItem, QGraphicsEllipseItem
from PyQt6.QtGui import QPainterPath, QColor, QPen, QBrush, QPolygonF


class GraphicsBase:
    def __init__(self, id: int):
        self._label = LabelInstance(id=id)
        self._draft_point = None

        self.anchors = []
        self.anchor_visible = False
        self.anchor_moving_index = -1

        logger.debug(f'image size:{Global["image_size"]}')
        self.thickness_normal = 2 / 1280 * Global["image_size"][0]
        self.thickness_select = 5 / 1280 * Global["image_size"][0]
        self.brush_alpha = 0.2

        self.could_redit = True

    def set_type(self, type, color=QColor(255, 0, 0)): ...

    def label(self):
        label = self._label.model_copy(deep=True)
        for index, point in enumerate(self._label.graphics.points):
            pos = self.mapToScene(point.x, point.y)  # 场景坐标
            label.graphics.points[index] = Point.from_QpointF(pos)
        return label

    def empty(self):
        return len(self._label.graphics.points) == 0

    # 添加临时点(最新点)
    def draft_point(self, point: Point):
        pos = self.mapFromScene(QPointF(point.x, point.y))
        self._draft_point = Point.from_QpointF(pos)
        self.refresh_shape()

    def commit_point(self, point: Point): ...  # 提交一个点
    def delete_point(self): ...  # 删除一个点

    # 切换编辑状态:anchor = None表示完成编辑,否则表示重新开始编辑
    def switch_edit_mode(self, anchor: Anchor = None): ...

    def refresh_shape(self): ...  # 更新图形

    def show_anchors(self): ...  # 创建控制锚点
    def hide_anchors(self): ...  # 隐藏控制锚点

    def on_anchor_position_changed(self, index, pos): ...

    def on_ancher_move_begin(self, index, pos):
        self.anchor_moving_index = index
        logger.info(f'items on scene {len(self.scene().items())}')

    def on_ancher_move_end(self, index, pos):
        self.anchor_moving_index = -1


class PolyGraphicsBase(GraphicsBase, QGraphicsPathItem):
    def __init__(self, id: int):
        GraphicsBase.__init__(self, id)
        QGraphicsPathItem.__init__(self)

        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsMovable, True)
        self.set_type(0)

    def set_type(self, type, color=QColor(255, 0, 0)):
        self._label.type = type

        pcolor = QColor.fromRgbF(color.redF(), color.greenF(), color.blueF(), color.alphaF())
        pen = QPen(pcolor, self.thickness_normal)  # 红色边框，2像素宽
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)

        # 半透明填充（RGBA：A=150表示约60%不透明）
        bcolor = QColor.fromRgbF(color.redF(), color.greenF(), color.blueF(), self.brush_alpha)
        brush = QBrush(bcolor)
        self.setBrush(brush)

    def commit_point(self, point: Point):
        pos = self.mapFromScene(QPointF(point.x, point.y))
        self._label.graphics.points.append(Point.from_QpointF(pos))
        self._draft_point = None
        self.refresh_shape()
        logger.debug(f"commit_point: {len(self._label.graphics.points)}")

    def delete_point(self):
        if len(self._label.graphics.points) <= 0:
            return
        self._label.graphics.points.pop()
        self.refresh_shape()

    def switch_edit_mode(self, anchor: Anchor = None):
        if anchor not in self.anchors:
            return

        index = self.anchors.index(anchor)  # 找到anchor的索引
        anchors = self.anchors[index + 1 :] + self.anchors[:index]  # 重新排列列表
        self._draft_point = Point.from_QpointF(anchor.pos())

        self._label.graphics.points = []
        for anchor in anchors:
            self._label.graphics.points.append(Point.from_QpointF(anchor.pos()))

        self.anchor_moving_index = -1
        self.refresh_shape()

    def refresh_shape(self): ...

    def show_anchors(self):
        """显示锚点"""
        self.hide_anchors()  # 清除现有锚点
        # 为每个路径点创建锚点
        for i in range(self.path().elementCount() - 1):
            element = self.path().elementAt(i)
            anchor = Anchor(i, QPointF(element.x, element.y), self, Qt.CursorShape.SizeAllCursor)
            self.anchors.append(anchor)

    def hide_anchors(self):
        """隐藏锚点"""
        for anchor in self.anchors:
            if anchor.scene():
                self.scene().removeItem(anchor)
        anchors_tobe_del = self.anchors.copy()
        self.anchors = []

        def cleanup():
            anchors_tobe_del.clear()

        QTimer.singleShot(0, cleanup)

    def itemChange(self, change, value):
        """响应item状态变化"""
        if change == QGraphicsPathItem.GraphicsItemChange.ItemSelectedChange:
            color = self.pen().color()
            self.anchor_visible = value or self.anchor_moving_index >= 0
            self.setPen(QPen(color, self.thickness_select if self.anchor_visible else self.thickness_normal))
            self.refresh_shape()  # 通知需要重绘
        return super().itemChange(change, value)

    def on_anchor_position_changed(self, index, pos):
        if index >= len(self._label.graphics.points):
            return
        self._label.graphics.points[index] = Point.from_QpointF(pos)
        self.refresh_shape()


class Polygon(PolyGraphicsBase):
    """多边形"""

    def __init__(self, id):
        super().__init__(id)
        self._label.graphics.type = GraphicsType.GT_POLYGON

    def refresh_shape(self):
        path = QPainterPath()
        points = self._label.graphics.points.copy()
        if self._draft_point is not None:
            points.append(self._draft_point)
        if len(points) > 0:
            path.moveTo(points[0].x, points[0].y)
            for point in points[1:]:
                path.lineTo(point.x, point.y)
        path.closeSubpath()
        self.setPath(path)
        if self.anchor_moving_index < 0:
            (self.show_anchors if self.anchor_visible else self.hide_anchors)()


class Polyline(PolyGraphicsBase):
    """折线"""

    def __init__(self, id):
        super().__init__(id)
        self._label.graphics.type = GraphicsType.GT_POLYLINE
        self.thickness_normal = 3
        self.thickness_select = 5

        self.point_index = 0

    def commit_point(self, point: Point):
        pos = self.mapFromScene(QPointF(point.x, point.y))
        self._label.graphics.points.insert(self.point_index, Point.from_QpointF(pos))
        self.point_index += 1
        self._draft_point = None
        self.refresh_shape()

    def delete_point(self):
        if self.point_index <= 0:
            return
        self.point_index -= 1
        del self._label.graphics.points[self.point_index]
        self.refresh_shape()

    def switch_edit_mode(self, anchor: Anchor = None):
        if anchor not in self.anchors:
            self.point_index = len(self._label.graphics.points)
            return

        self.point_index = self.anchors.index(anchor)  # 找到anchor的索引
        self._draft_point = Point.from_QpointF(anchor.pos())
        del self._label.graphics.points[self.point_index]

        self.anchor_moving_index = -1
        self.refresh_shape()

    def refresh_shape(self):
        path = QPainterPath()
        points = self._label.graphics.points.copy()
        if self._draft_point is not None:
            points.insert(self.point_index, self._draft_point)
        if len(points) > 0:
            path.moveTo(points[0].x, points[0].y)
            for point in points[1:]:
                path.lineTo(point.x, point.y)

        self.setBrush(QBrush(Qt.GlobalColor.transparent))
        self.setPath(path)
        if self.anchor_moving_index < 0:
            (self.show_anchors if self.anchor_visible else self.hide_anchors)()

    def show_anchors(self):
        """显示锚点"""
        self.hide_anchors()  # 清除现有锚点
        # 为每个路径点创建锚点
        for i in range(self.path().elementCount()):
            element = self.path().elementAt(i)
            anchor = Anchor(i, QPointF(element.x, element.y), self, Qt.CursorShape.SizeAllCursor)
            self.anchors.append(anchor)

    def on_anchor_position_changed(self, index, pos):
        if index >= len(self._label.graphics.points):
            return
        if index == self.point_index:
            return
        self._label.graphics.points[index] = Point.from_QpointF(pos)
        self.refresh_shape()


class Rectangle(GraphicsBase, QGraphicsRectItem):
    def __init__(self, id: int):
        GraphicsBase.__init__(self, id)
        QGraphicsRectItem.__init__(self)
        self._label.graphics.type = GraphicsType.GT_RECTANGLE

        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsMovable, True)
        self.set_type(0)

        self.could_redit = False

    def set_type(self, type, color=QColor(255, 0, 0)):
        self._label.type = type

        pcolor = QColor.fromRgbF(color.redF(), color.greenF(), color.blueF(), color.alphaF())
        pen = QPen(pcolor, self.thickness_normal)  # 红色边框，2像素宽
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)

        # 半透明填充（RGBA：A=150表示约60%不透明）
        bcolor = QColor.fromRgbF(color.redF(), color.greenF(), color.blueF(), self.brush_alpha)
        brush = QBrush(bcolor)
        self.setBrush(brush)

    def draft_point(self, point: Point):  # 添加一个临时点
        pos = self.mapFromScene(QPointF(point.x, point.y))
        if len(self._label.graphics.points) == 2:
            self._label.graphics.points[1] = Point.from_QpointF(pos)
            self.refresh_shape()

    def commit_point(self, point: Point):  # 提交一个点
        pos = self.mapFromScene(QPointF(point.x, point.y))
        point = Point.from_QpointF(pos)
        if len(self._label.graphics.points) == 0:
            self._label.graphics.points.append(point)
            self._label.graphics.points.append(point)
        else:
            self._label.graphics.points[1] = point
        self.refresh_shape()

    def delete_point(self):  # 删除一个点
        if len(self._label.graphics.points) <= 0:
            return
        self._label.graphics.points = []
        self.refresh_shape()

    def refresh_shape(self):  # 更新图形
        points = [point.to_QpointF() for point in self._label.graphics.points]
        self.setRect(QPolygonF(points).boundingRect() if len(points) == 2 else QRectF())
        (self.show_anchors if self.anchor_visible else self.hide_anchors)()

    def show_anchors(self):  # 创建控制锚点
        if len(self.anchors) != 8:
            self.hide_anchors()  # 不是8个锚点 就清除现有锚点重新创建所有,否则更新现有锚点

        attributes = self.calculate_anchor_attributes()
        if attributes is None:
            return

        if len(self.anchors) == 0:  # create
            for index, attribute in enumerate(attributes):
                self.anchors.append(Anchor(index, attribute['pos'], self, attribute['cursor']))
        else:  # update
            for index, attribute in enumerate(attributes):
                self.anchors[index].setPos(attribute['pos'])
                self.anchors[index].cursor = attribute['cursor']
                self.anchors[index].setCursor(attribute['cursor'])
                self.anchors[index].setVisible(True)

    def hide_anchors(self):
        """隐藏锚点"""
        for anchor in self.anchors:
            if anchor.scene() and anchor in self.scene().items():
                anchor.setVisible(False)

    def itemChange(self, change, value):
        """响应item状态变化"""
        if change == QGraphicsPathItem.GraphicsItemChange.ItemSelectedChange:
            color = self.pen().color()
            self.anchor_visible = value or self.anchor_moving_index >= 0
            self.setPen(QPen(color, self.thickness_select if self.anchor_visible else self.thickness_normal))
            self.refresh_shape()  # 通知需要重绘
        return super().itemChange(change, value)

    def on_anchor_position_changed(self, index, pos):
        if index == 0:
            self._label.graphics.points[0] = Point.from_QpointF(pos)
        elif index == 1:
            self._label.graphics.points[0].y = pos.y()
        elif index == 2:
            self._label.graphics.points[0].y = pos.y()
            self._label.graphics.points[1].x = pos.x()
        elif index == 3:
            self._label.graphics.points[1].x = pos.x()
        elif index == 4:
            self._label.graphics.points[1] = Point.from_QpointF(pos)
        elif index == 5:
            self._label.graphics.points[1].y = pos.y()
        elif index == 6:
            self._label.graphics.points[0].x = pos.x()
            self._label.graphics.points[1].y = pos.y()
        elif index == 7:
            self._label.graphics.points[0].x = pos.x()

        self.refresh_shape()

    def calculate_anchor_attributes(self):
        if len(self._label.graphics.points) != 2:
            return None

        # 0 1 2
        # 7   3
        # 6 5 4
        p0 = self._label.graphics.points[0].to_QpointF()
        p4 = self._label.graphics.points[1].to_QpointF()
        p2 = QPointF(p4.x(), p0.y())
        p6 = QPointF(p0.x(), p4.y())

        p1 = QLineF(p0, p2).center()
        p3 = QLineF(p2, p4).center()
        p5 = QLineF(p4, p6).center()
        p7 = QLineF(p6, p0).center()

        side = (p0.x() - p4.x()) * (p0.y() - p4.y()) > 0
        attributes = [
            {'pos': p0, 'cursor': Qt.CursorShape.SizeFDiagCursor if side else Qt.CursorShape.SizeBDiagCursor},
            {'pos': p1, 'cursor': Qt.CursorShape.SizeVerCursor},
            {'pos': p2, 'cursor': Qt.CursorShape.SizeBDiagCursor if side else Qt.CursorShape.SizeFDiagCursor},
            {'pos': p3, 'cursor': Qt.CursorShape.SizeHorCursor},
            {'pos': p4, 'cursor': Qt.CursorShape.SizeFDiagCursor if side else Qt.CursorShape.SizeBDiagCursor},
            {'pos': p5, 'cursor': Qt.CursorShape.SizeVerCursor},
            {'pos': p6, 'cursor': Qt.CursorShape.SizeBDiagCursor if side else Qt.CursorShape.SizeFDiagCursor},
            {'pos': p7, 'cursor': Qt.CursorShape.SizeHorCursor},
        ]
        return attributes


class Segment(GraphicsBase, QGraphicsLineItem):
    def __init__(self, id):
        GraphicsBase.__init__(self, id)
        QGraphicsLineItem.__init__(self)
        self._label.graphics.type = GraphicsType.GT_LINESEG

        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsMovable, True)
        self.set_type(0)

        self.could_redit = False

    def set_type(self, type, color=QColor(255, 0, 0)):
        self._label.type = type

        pcolor = QColor.fromRgbF(color.redF(), color.greenF(), color.blueF(), color.alphaF())
        pen = QPen(pcolor, self.thickness_normal)  # 红色边框，2像素宽
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)

    def draft_point(self, point: Point):  # 添加一个临时点
        pos = self.mapFromScene(QPointF(point.x, point.y))
        if len(self._label.graphics.points) == 2:
            self._label.graphics.points[1] = Point.from_QpointF(pos)
            self.refresh_shape()

    def commit_point(self, point: Point):  # 提交一个点
        pos = self.mapFromScene(QPointF(point.x, point.y))
        point = Point.from_QpointF(pos)
        if len(self._label.graphics.points) == 0:
            self._label.graphics.points.append(point)
            self._label.graphics.points.append(point)
        else:
            self._label.graphics.points[1] = point
        self.refresh_shape()

    def delete_point(self):  # 删除一个点
        if len(self._label.graphics.points) <= 0:
            return
        self._label.graphics.points = []
        self.refresh_shape()

    def refresh_shape(self):  # 更新图形
        points = [point.to_QpointF() for point in self._label.graphics.points]
        self.setLine(QLineF(points[0], points[1]) if len(points) == 2 else QLineF())
        # if self.anchor_moving_index < 0:
        (self.show_anchors if self.anchor_visible else self.hide_anchors)()

    def show_anchors(self):
        """显示锚点"""
        if len(self.anchors) != 2:
            self.hide_anchors()  # 不是2个锚点 就清除现有锚点重新创建所有,否则更新现有锚点

        if len(self._label.graphics.points) == 0:
            return

        p0 = self._label.graphics.points[0].to_QpointF()
        p1 = self._label.graphics.points[1].to_QpointF()

        if len(self.anchors) == 0:  # create
            self.anchors.append(Anchor(0, p0, self, Qt.CursorShape.SizeAllCursor))
            self.anchors.append(Anchor(1, p1, self, Qt.CursorShape.SizeAllCursor))
        else:  # update
            self.anchors[0].setPos(p0)
            self.anchors[0].setVisible(True)
            self.anchors[1].setPos(p1)
            self.anchors[1].setVisible(True)

    def hide_anchors(self):
        """隐藏锚点"""
        for anchor in self.anchors:
            if anchor.scene() and anchor in self.scene().items():
                anchor.setVisible(False)

    def itemChange(self, change, value):
        """响应item状态变化"""
        if change == QGraphicsPathItem.GraphicsItemChange.ItemSelectedChange:
            color = self.pen().color()
            self.anchor_visible = value or self.anchor_moving_index >= 0
            self.setPen(QPen(color, self.thickness_select if self.anchor_visible else self.thickness_normal))
            self.refresh_shape()  # 通知需要重绘
        return super().itemChange(change, value)

    def on_anchor_position_changed(self, index, pos):
        self._label.graphics.points[index] = Point.from_QpointF(pos)
        self.refresh_shape()


class Keypoint(GraphicsBase, QGraphicsEllipseItem):
    def __init__(self, id):
        GraphicsBase.__init__(self, id)
        QGraphicsEllipseItem.__init__(self)
        self._label.graphics.type = GraphicsType.GT_KEYPOINT

        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)

        self.set_type(0)

        self.radius = 8
        self.could_redit = False

    def set_type(self, type, color=QColor(255, 0, 0)):
        self._label.type = type

        pcolor = QColor.fromRgbF(color.redF(), color.greenF(), color.blueF())
        pen = QPen(pcolor, self.thickness_normal)  # 红色边框，2像素宽
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)

        # 半透明填充（RGBA：A=150表示约60%不透明）
        bcolor = QColor.fromRgbF(color.redF(), color.greenF(), color.blueF())
        brush = QBrush(bcolor)
        self.setBrush(brush)

    def commit_point(self, point: Point):  # 提交一个点
        pos = self.mapFromScene(QPointF(point.x, point.y))
        self._label.graphics.points[:1] = [Point.from_QpointF(pos)]
        self._draft_point = None
        self.refresh_shape()

    def delete_point(self):  # 删除一个点
        if len(self._label.graphics.points) <= 0:
            return
        self._label.graphics.points = []
        self.refresh_shape()

    def refresh_shape(self):  # 更新图形
        point = None
        if self._draft_point is not None:
            point = self._draft_point
        elif len(self._label.graphics.points) != 0:
            point = self._label.graphics.points[0]

        if point is not None:
            rect = QRectF(point.x - self.radius, point.y - self.radius, self.radius * 2, self.radius * 2)
            self.setRect(rect)

    def itemChange(self, change, value):
        """响应item状态变化"""
        if change == QGraphicsPathItem.GraphicsItemChange.ItemSelectedChange:
            color = self.pen().color()
            self.anchor_visible = value or self.anchor_moving_index >= 0
            self.setPen(QPen(color, self.thickness_select if self.anchor_visible else self.thickness_normal))
            self.setBrush(QBrush(QColor(255, 255, 0)) if self.anchor_visible else QBrush(color))
            self.refresh_shape()  # 通知需要重绘
        return super().itemChange(change, value)

    def on_anchor_position_changed(self, index, pos):
        self._label.graphics.points[index] = Point.from_QpointF(pos)
        self.refresh_shape()

    def hoverEnterEvent(self, event):
        """鼠标进入Item区域时触发"""
        # 改变鼠标样式为手形
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开Item区域时触发"""
        # 恢复默认的鼠标样式
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(event)
