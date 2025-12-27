# -*- coding: utf-8 -*-
from enum import Enum
from typing import List
from pydantic import BaseModel
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
    GT_LINESEG = 'segment'
    GT_POLYLINE = 'polyline'
    GT_RECTANGLE = 'rectangle'
    GT_POLYGON = 'polygon'
    GT_KEYPOINT = 'keypoint'


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
    labels: List[LabelInstance] = []


class AisLabelConfig(BaseModel):
    projects: List = []
    focus: int = 0
    schemas: List[LabelSchema] = [
        LabelSchema(
            name="足球",
            categories=[
                LabelCategory(type=0, export_id=0, label="Football", color="#000000", remark=""),
                LabelCategory(type=1, export_id=1, label="Person", color="#FFFFFF", remark=""),
            ],
        ),
        LabelSchema(
            name="篮球",
            categories=[
                LabelCategory(type=0, export_id=0, label="Basketball", color="#000000", remark=""),
                LabelCategory(type=1, export_id=1, label="EmptyNet", color="#FFFFFF", remark=""),
                LabelCategory(type=2, export_id=2, label="BasketballInNet", color="#EEEEEE", remark=""),
            ],
        ),
    ]


class ProjectConfig(BaseModel):
    creation: str
    directory: str
    task: str
    description: str
    mschema: LabelSchema
