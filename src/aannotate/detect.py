# -*- coding: utf-8 -*-
from utils.logger import logger
from utils.workroot import WorkRoot

from models.data import *
from project.project import Project

from ultralytics import YOLO
from ultralytics.engine.results import Results

import os


class Detect:
    def __init__(self, model="best.pt"):
        self.project = None
        self.model = YOLO(os.path.join(WorkRoot, 'src', 'resource', 'models', model))

    def set_project(self, project: Project):
        self.project = project

    def infer(self, image):
        if self.project is None:
            return None
        results = self.model(
            image,
            save=False,  # 不保存检测结果图片
            show=False,  # 不显示图片
            save_txt=False,  # 不保存标签文件
            save_conf=False,  # 不保存置信度
            save_crop=False,  # 不保存裁剪的检测对象
            project=None,  # 不使用项目目录
            name=None,  # 不命名运行
            exist_ok=False,  # 如果存在不覆盖
        )

        # 转换结果为LabelGroup
        if not results or len(results) == 0:
            return None
        return self._convert_results(results[0], self.project.schema, 0.1)

    def _convert_results(self, results: Results, schema: LabelSchema, threshold: float = 0.1) -> LabelGroup:
        """
        将YOLO检测结果转换为LabelGroup

        Args:
            results: YOLO模型的推理结果
            schema: 标签分类方案
            threshold: 置信度阈值，低于此值的检测框将被过滤

        Returns:
            LabelGroup: 转换后的标注组
        """

        fetch_types = {category.import_id: category.type for category in schema.categories}

        # 检查是否有检测结果
        if results.boxes is None or len(results.boxes) == 0:
            return LabelGroup(ignored=False, labels=[])

        # 获取检测结果
        boxes = results.boxes

        # 提取数据
        bboxes = boxes.xyxy.cpu().numpy()
        confidences = boxes.conf.cpu().numpy()
        types = boxes.cls.cpu().numpy().astype(int)

        # 生成唯一的ID
        group = LabelGroup()

        # 遍历所有检测框
        idx = 0
        for id, (bbox, conf, type) in enumerate(zip(bboxes, confidences, types)):
            logger.info(f"Detected: {id} {self.model.names[type]} Type={type}, Confidence={conf:.2f}, BBox={bbox}")
            # 过滤低置信度的检测
            if conf < threshold:
                continue

            if type not in fetch_types.keys():
                continue

            # 获取边界框坐标 (xyxy格式: x1, y1, x2, y2)
            x1, y1, x2, y2 = bbox

            # 创建标签实例
            instance = LabelInstance(id=idx)
            instance.type = fetch_types[type]
            instance.graphics = Graphics(type=GraphicsType.GT_RECTANGLE, points=[Point(x=x1, y=y1), Point(x=x2, y=y2)])
            group.labels.append(instance)
            idx += 1

        return group
