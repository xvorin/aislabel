# -*- coding: utf-8 -*-
from PyQt6.QtCore import pyqtSignal, QObject

from models.data import GraphicsType
from project.project import Project
from project.provider import LabelingDataItem

from utils.logger import logger

from typing import List, Optional, Tuple
from pathlib import Path

import random
import shutil


# ---------- YOLO 多项目导出器 ----------
class YOLOMultiProjectExporter(QObject):
    """标注数据导出器基类"""

    process = pyqtSignal(int, int)  # processed, total

    def __init__(self):
        super().__init__()
        self.total = 0
        self.processed = 0

    def export(
        self,
        projects: List[Project],
        output_dir: str,
        train_ratio: float = 0.8,
        random_seed: Optional[int] = None,
        **kwargs,
    ) -> None:
        """
        :param train_ratio: 训练集比例 (0~1)
        :param random_seed: 随机种子（用于复现划分）
        """
        if len(projects) == 0:
            logger.warning("警告：没有提供任何项目进行导出")
            return

        # 1. 构建全局类别映射
        class_names = self._build_global_categories(projects)

        logger.info(f"全局类别列表(共 {len(class_names)} 类):{class_names}")

        # 2. 收集所有图像及其元数据
        images = []  # 每个元素为 (filekey, image_path, LabelGroup)
        for project in projects:
            for filekey in project.filekeys():
                item = LabelingDataItem(filekey, project)
                if item.ignored():
                    continue
                if not item.labeled():
                    continue
                images.append((filekey, project.image_path(filekey), item.group))
        if not images:
            logger.warning("警告：没有找到任何图像")
            return

        # 3. 随机划分训练/验证集
        if random_seed is not None:
            random.seed(random_seed)
        shuffled = images.copy()
        random.shuffle(shuffled)
        split_idx = int(len(shuffled) * train_ratio)
        trains = shuffled[:split_idx]
        vals = shuffled[split_idx:]

        self.total = len(images)
        self.processed = 0

        # 4. 准备输出目录
        output_path = Path(output_dir)
        for subset in ["train", "val"]:
            (output_path / "images" / subset).mkdir(parents=True, exist_ok=True)
            (output_path / "labels" / subset).mkdir(parents=True, exist_ok=True)

        # 5. 处理训练集和验证集
        export_table = {category.type: category.export_id for category in projects[0].schema.categories}
        self._process_subset(trains, output_path / "images" / "train", output_path / "labels" / "train", export_table)
        self._process_subset(vals, output_path / "images" / "val", output_path / "labels" / "val", export_table)

        # 6. 生成 dataset.yaml 和 classes.txt
        with open(output_path / "dataset.yaml", "w", encoding="utf-8") as fout:
            fout.write(f"path: {str(output_path.absolute())}\n")
            fout.write(f"train: images/train\n")
            fout.write(f"val: images/val\n")
            fout.write(f"test:\n\n")
            fout.write(f"nc: {len(class_names)}\n\n")
            fout.write(f"names: {class_names}\n")

        with open(output_path / "classes.txt", "w", encoding="utf-8") as fout:
            fout.write("\n".join(class_names))

    def _build_global_categories(self, projects: List[Project]) -> List[Tuple[int, str]]:
        """收集所有项目的类别，按 (export_id, label) 排序，并去重（基于标签名）"""
        categories_from_every_projects = []  # 每个项目的类别列表
        for project in projects:
            categories = project.schema.categories
            categories_from_every_projects.append([(category.export_id, category.label) for category in categories])

        categories = categories_from_every_projects[0]
        for rest_categories in categories_from_every_projects[1:]:
            if categories != rest_categories:
                raise ValueError(f"Projects has different category")

        # 基于export_id去重
        categories = {export_id: label for export_id, label in categories}

        # 按export_id升序排序
        sorted_export_ids = sorted(categories.keys())

        # 检查 export_id 是否构成 0..n-1 的连续整数（顺序无关）
        if sorted_export_ids != list(range(len(sorted_export_ids))):
            raise ValueError(f"export_id must be continuous integers starting from 0 ")

        # 返回排序后的标签列表
        return [categories[export_id] for export_id in sorted_export_ids]

    def _process_subset(self, images_data, image_dir: Path, label_dir: Path, export_table) -> None:
        """处理一个子集（训练或验证）"""
        for filekey, path, group in images_data:
            # 拷贝图片文件
            shutil.copy2(path, image_dir / f"{filekey}{path.suffix}")

            # 生成标注文件
            txt_path = label_dir / f"{filekey}.txt"
            lines = []

            for instance in group.labels:
                if not instance.visible or instance.graphics.type != GraphicsType.GT_RECTANGLE:
                    continue
                points = instance.graphics.points
                if len(points) < 2:
                    continue

                if instance.type not in export_table.keys():
                    continue

                x1, y1 = points[0].x, points[0].y
                x2, y2 = points[1].x, points[1].y
                # 计算归一化中心坐标和宽高
                cx = ((x1 + x2) / 2) / group.width
                cy = ((y1 + y2) / 2) / group.height
                w = abs(x2 - x1) / group.width
                h = abs(y2 - y1) / group.height

                lines.append(f"{export_table[instance.type]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

            if lines:
                txt_path.write_text("\n".join(lines))

            self.processed = self.processed + 1

            if self.processed % 10 == 0 or self.processed == self.total:
                self.process.emit(self.processed, self.total)


# ---------- 便捷导出函数 ----------
def export_projects_to_yolo(
    projects: List[Project], output_dir: str, train_ratio: float = 0.8, random_seed: Optional[int] = None
) -> None:
    """便捷函数：导出多个项目为 YOLO 格式"""
    exporter = YOLOMultiProjectExporter()
    exporter.export(projects, output_dir, train_ratio=train_ratio, random_seed=random_seed)
