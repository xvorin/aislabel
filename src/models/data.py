# -*- coding: utf-8 -*-
from enum import Enum
from typing import List
from pydantic import BaseModel
from datetime import datetime

from PyQt6.QtCore import QPointF


class AnnotationTaskType(Enum):
    ATT_OBJ_DETECTION = "目标检测"
    ATT_TXT_DETECTION = "文本检测"
    ATT_SEG_INSTANCE = "实例分割"
    ATT_SEG_SEMANTIC = "语义分割"
    ATT_CLASSIFY = "图像分类"
    ATT_KEYPOINT = "关键点检测"


class PaintCommand(Enum):
    PCMD_NONE = 0
    PCMD_ARROR = 1
    PCMD_LINESEG = 2
    PCMD_POLYLINE = 3
    PCMD_RECTANGLE = 4
    PCMD_POLYGON = 5
    PCMD_KEYPOINT = 6
    PCMD_DELETE = 7


class GraphicsType(Enum):
    GT_LINESEG = '线段'
    GT_POLYLINE = '折线'
    GT_RECTANGLE = '矩形'
    GT_POLYGON = '多边形'
    GT_KEYPOINT = '关键点'


class Point(BaseModel):
    x: float
    y: float

    def to_tuple(self) -> tuple:
        return (self.x, self.y)

    @classmethod
    def from_tuple(cls, t: tuple) -> 'Point':
        return cls(x=t[0], y=t[1])

    def to_QpointF(self) -> QPointF:
        return QPointF(self.x, self.y)

    @classmethod
    def from_QpointF(cls, point: QPointF) -> 'Point':
        return cls(x=point.x(), y=point.y())

    def __eq__(self, other):
        if not isinstance(other, Point):
            return False
        return abs(self.x - other.x) < 1e-9 and abs(self.y - other.y) < 1e-9


class Graphics(BaseModel):
    type: GraphicsType = GraphicsType.GT_RECTANGLE
    points: List[Point] = []


class LabelCategory(BaseModel):
    type: int
    import_id: int
    export_id: int
    label: str
    color: str
    remark: str


class LabelSchema(BaseModel):
    name: str = ""
    categories: List[LabelCategory] = []
    version: str = "1.0"  # 可选：版本号
    description: str = ""  # 可选：描述


class LabelInstance(BaseModel):
    id: int = 0
    type: int = 0
    visible: bool = True
    graphics: Graphics = Graphics()


class LabelGroup(BaseModel):
    ignored: bool = False
    width: int = 0
    height: int = 0
    labels: List[LabelInstance] = []


class AisLabelConfig(BaseModel):
    projects: List = []
    focus: int = 0
    schemas: List[LabelSchema] = [
        LabelSchema(
            name="足球",
            categories=[
                LabelCategory(type=0, import_id=0, export_id=0, label="Football", color="#000000", remark=""),
                LabelCategory(type=1, import_id=1, export_id=1, label="Person", color="#FFFFFF", remark=""),
            ],
        ),
        LabelSchema(
            name="篮球",
            categories=[
                LabelCategory(type=0, import_id=32, export_id=0, label="Basketball", color="#FFFFFF", remark=""),
                LabelCategory(type=0, import_id=38, export_id=0, label="Basketball", color="#FFFFFF", remark=""),
                LabelCategory(type=1, import_id=100, export_id=1, label="BasketballInNet", color="#FF0000", remark=""),
                LabelCategory(type=2, import_id=101, export_id=2, label="EmptyNet", color="#0000FF", remark=""),
            ],
        ),
    ]


class TimeFilterMode(Enum):
    TIME_NONE = '忽略时间'
    TIME_CREATE = '创建时间'
    TIME_MODIFY = '修改时间'

    @classmethod
    def values(cls) -> List:
        """获取所有枚举值"""
        return [member.value for member in cls]


class TimeLogicType(Enum):
    LOGIC_LT = '早于'
    LOGIC_GT = '晚于'

    @classmethod
    def values(cls) -> List:
        """获取所有枚举值"""
        return [member.value for member in cls]


class TimeFilterConfig(BaseModel):
    mode: str = TimeFilterMode.TIME_NONE.value
    type: str = TimeLogicType.LOGIC_GT.value
    time: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class AttributeFilterConfig(BaseModel):
    reverse: bool = False
    indices: List[int] = []


class ProjectFilterConfig(BaseModel):
    show_ignored_images: bool = True
    show_labeled_images: bool = True
    image_index: AttributeFilterConfig = AttributeFilterConfig()
    label_num: AttributeFilterConfig = AttributeFilterConfig()
    label_category: AttributeFilterConfig = AttributeFilterConfig()
    time_filter: TimeFilterConfig = TimeFilterConfig()


class AutoAnnotate(BaseModel):
    enable: bool = True


class ProjectConfig(BaseModel):
    creation: str
    directory: str
    task: str
    description: str
    mschema: LabelSchema
    mfilter: ProjectFilterConfig
    aannotate: AutoAnnotate
