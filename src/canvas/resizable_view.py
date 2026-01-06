# -*- coding: utf-8 -*-
from utils.logger import logger
from utils.config import Global

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsView, QApplication
from PyQt6.QtGui import QWheelEvent, QPainter, QKeyEvent


class ResizableGraphicsView(QGraphicsView):
    on_type_specified = pyqtSignal(int)
    on_scale_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)  # 设置变换锚点(鼠标位置为中心)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)  # 启用鼠标跟踪
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)  # 允许框选
        # view.setDragMode(QGraphicsView.DragMode.NoDrag)        # 仅点击选择

        self.on_mouse_left_press = None
        self.on_mouse_left_single_clicked = None
        self.on_mouse_left_double_clicked = None
        self.on_mouse_right_clicked = None
        self.on_mouse_move = None
        self.on_mouse_release = None
        self.on_view_resize = None
        self.is_left_double_clicked = False
        self.left_button_pressing = False

        self.scale_factor = 1.15  # 每次滚轮的缩放比例
        self.max_scale = 10.0  # 最大缩放比例
        self.min_scale = 0.1  # 最小缩放比例

        self.pixmap = None  # 当前显示的图元

        # 接收数字按键 指定元素类型
        self.type_specified_timer = QTimer()
        self.type_specified_timer.setSingleShot(True)  # 设置为一次性定时器
        self.type_specified_timer.timeout.connect(self.__type_specified_timeout)
        self.specified_type = ''

    def set_pixmap_item(self, pixmap: QGraphicsPixmapItem):
        """设置当前显示的图元"""
        self.pixmap = pixmap

    def wheelEvent(self, event: QWheelEvent):
        """处理鼠标滚轮事件：缩放视图"""
        # 检查是否按下了Ctrl键(可选的，用于更精确的控制)
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            (self.zoom_in if event.angleDelta().y() > 0 else self.zoom_out)()  # 执行缩放
            event.accept()
            return
        super().wheelEvent(event)

    def zoom_in(self):
        """放大图片"""
        # logger.info("Zooming in")
        if self.current_scale() > self.max_scale:
            return
        self.scale(self.scale_factor, self.scale_factor)
        self.__on_scale_changed()

    def zoom_out(self):
        """缩小图片"""
        # logger.info("Zooming out")
        if self.current_scale() < self.min_scale:
            return
        self.scale(1 / self.scale_factor, 1 / self.scale_factor)
        self.__on_scale_changed()

    def zoom_fit(self):
        # logger.info("Fitting view to window")
        if self.scene() and self.scene().sceneRect().isValid():  # 调整视图以适应窗口
            # logger.info(f"Scene rect is valid, fitting in view {self.scene().sceneRect()}")
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.__on_scale_changed()

    def zoom_100(self):
        logger.info("Resetting scale to original size")
        self.resetTransform()  # 重置为原始大小(100%缩放)
        if self.pixmap:  # 将视图中心对准图片中心
            self.centerOn(self.pixmap)
        self.__on_scale_changed()

    def current_scale(self):
        """
        从视图的变换矩阵中获取当前水平方向的缩放值
        """
        # 获取当前的变换矩阵
        transform = self.transform()

        # 矩阵的 m11 和 m22 分别表示水平和垂直缩放
        scale_x = transform.m11()
        scale_y = transform.m22()

        # 通常水平和垂直缩放相同，但可以取平均值
        return (scale_x + scale_y) / 2

    def keyPressEvent(self, event: QKeyEvent):
        """使用 modifiers() 方法检查 Ctrl 键状态"""
        if event.text().isdigit() and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.specified_type += event.text()
            if self.type_specified_timer.isActive():
                self.type_specified_timer.stop()
            self.type_specified_timer.start(360)  # 360ms
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """处理按键释放，特别是修饰键的释放"""
        if event.key() == Qt.Key.Key_Control:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        super().keyReleaseEvent(event)

    def enterEvent(self, event):
        # 鼠标进入部件时调用
        # logger.info("Mouse entered the graphics view")
        self.setFocus()  # 设置焦点以接收键盘事件
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
            # logger.info("Ctrl key is pressed while entering the view")
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().enterEvent(event)

    def focusOutEvent(self, event):
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        x, y = self.__get_mouse_postion(event)
        if event.buttons() == Qt.MouseButton.MiddleButton:
            pass
        elif event.buttons() == Qt.MouseButton.RightButton:
            self.__on_mouse_right_clicked(x, y)
        elif event.buttons() == Qt.MouseButton.LeftButton:
            self.left_button_pressing = True
            self.is_left_double_clicked = False
            QTimer.singleShot(260, lambda: self.__on_mouse_left_clicked(x, y))
            # logger.debug(f"Left mouse button pressed at ({x}, {y})")
            if self.on_mouse_left_press:
                self.on_mouse_left_press(x, y)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        x, y = self.__get_mouse_postion(event)
        # logger.debug(f"mouse button released at ({x}, {y})")
        if self.on_mouse_release:
            self.on_mouse_release(x, y)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        x, y = self.__get_mouse_postion(event)
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.is_left_double_clicked = True
        if event.buttons() == Qt.MouseButton.RightButton:
            self.__on_mouse_right_clicked(x, y)
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        x, y = self.__get_mouse_postion(event)
        # logger.debug(f"Mouse moved to ({x}, {y})")
        if self.on_mouse_move and not self.left_button_pressing:
            self.on_mouse_move(x, y)
        super().mouseMoveEvent(event)

    def __on_mouse_left_clicked(self, x, y):
        action = (
            self.__on_mouse_left_double_clicked if self.is_left_double_clicked else self.__on_mouse_left_single_clicked
        )
        self.left_button_pressing = False
        action(x, y)

    def __on_mouse_left_double_clicked(self, x, y):
        # logger.debug(f"__on_mouse_left_double_clicked ({x}, {y})")
        if self.on_mouse_left_double_clicked:
            self.on_mouse_left_double_clicked(x, y)

    def __on_mouse_left_single_clicked(self, x, y):
        # logger.debug(f"__on_mouse_left_single_clicked ({x}, {y})")
        if self.on_mouse_left_single_clicked:
            self.on_mouse_left_single_clicked(x, y)

    def __on_mouse_right_clicked(self, x, y):
        if self.on_mouse_right_clicked:
            self.on_mouse_right_clicked(x, y)

    def __get_mouse_postion(self, event):
        """简化版坐标转换"""
        # 视图坐标 → 场景坐标 → 图元坐标
        scene_pos = self.mapToScene(event.pos())
        if self.pixmap is None:
            return 0, 0
        pixel_pos = self.pixmap.mapFromScene(scene_pos)
        x, y = int(pixel_pos.x()), int(pixel_pos.y())
        return round(x, 2), round(y, 2)

    def __type_specified_timeout(self):
        self.on_type_specified.emit(int(self.specified_type))
        self.specified_type = ''

    def __on_scale_changed(self):
        Global["scale"] = self.current_scale()
        self.on_scale_changed.emit(Global["scale"])
