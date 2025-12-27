# -*- coding: utf-8 -*-
from utils.logger import logger

from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image
from datetime import datetime

import numpy as np
import tempfile
import hashlib
import re
import cv2
import magic
import shutil


class Storage:
    def __init__(self, directory: str):
        """初始化图片存储器

        Args:
            directory: 存储目录路径
        """
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.md5s = set()  # 重命名避免与hashlib.md5冲突
        self.keys = []  # 更清晰的命名

        # 优化正则表达式：timestampus_md5.jpg
        self.filename_pattern = re.compile(r'^(\d{20})_([a-fA-F0-9]{32})\.(jpg|jpeg|png)$')

        # 扫描现有图片
        self._scan_existing_images()

    def filekeys(self) -> List[str]:
        """获取图片序列"""
        return self.keys.copy()  # 返回副本防止外部修改

    def get_create_time(self, filekey: str) -> Optional[datetime]:
        """获取图片创建时间"""
        filepath = self.get_image_path(filekey)
        if not filepath.is_file():
            return None
        timestamp, _ = self._parse_filename_pattern(filepath.name)
        create_time = datetime.strptime(timestamp, '%Y%m%d%H%M%S%f')
        return create_time

    def get_image_path(self, filekey: str) -> Path:
        """获取文件的完整路径"""
        return self.directory / f"{filekey}.jpg"

    def get_label_path(self, filekey: str) -> Path:
        """获取文件的完整路径"""
        return self.directory / f"{filekey}.txt"

    def import_media(self, sources: List[str]):
        """加载图片或视频源"""
        for source in sources:
            self._load_single_source(source)

    def _scan_existing_images(self):
        """扫描现有图片,初始化MD5集合和序列"""
        self.md5s.clear()
        self.keys.clear()

        if not self.directory.exists():
            return

        for filepath in self.directory.iterdir():
            if not filepath.is_file():
                continue

            timestamp, md5 = self._parse_filename_pattern(filepath.name)
            if timestamp is None or md5 is None:
                continue

            self.md5s.add(md5)
            self.keys.append((int(timestamp), filepath.stem))

        # 排序并提取文件名
        self.keys.sort(key=lambda x: x[0])
        self.keys = [filekey for _, filekey in self.keys]

    def _parse_filename_pattern(self, filename: str) -> Optional[Tuple[str, str]]:
        """解析文件名模式,返回时间戳、序列号和MD5"""
        match = self.filename_pattern.match(filename)
        if match:
            timestamp, md5, _ = match.groups()
            return timestamp, md5
        return None, None

    def _load_single_source(self, source: str):
        """加载单个源文件"""
        source_path = Path(source)
        if not source_path.exists():
            return False

        try:
            if source_path.is_dir():
                return self._import_directory(source_path) > 0

            mime = magic.Magic(mime=True)
            type = mime.from_file(str(source_path))

            if type.startswith('image/'):
                return self._import_image(source_path) > 0

            if type.startswith('video/'):
                return self._import_video(source_path) > 0
        except Exception as e:
            logger.error(f"Loading source: {source} {e}")
            return False

        return False

    def _import_directory(self, directory: Path) -> List[str]:
        """导入目录中的所有图片"""
        imported_frames = 0
        for filepath in directory.rglob('*'):
            mime = magic.Magic(mime=True)
            type = mime.from_file(str(filepath))
            if not type.startswith('image/'):
                continue
            if self._import_image(filepath):
                imported_frames += 1
        return imported_frames

    def _import_video(self, video_path: Path) -> List[str]:
        """从视频导入帧作为图片"""
        imported_frames = 0
        try:
            capture = cv2.VideoCapture(str(video_path))
            while True:
                retval, frame = capture.read()
                if not retval:
                    break

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # 转换BGR到RGB
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    filepath = tmp.name
                    Image.fromarray(frame).save(filepath, 'JPEG', quality=95)
                    if self._import_image(filepath, need_check=False):
                        imported_frames += 1
            capture.release()
        except Exception as e:
            logger.error(f"Video processing error {video_path}: {e}")
        return imported_frames

    def _import_image(self, source: str, need_check=True) -> Optional[str]:
        """保存图片并注册到系统"""
        md5 = self._calculate_md5(source)
        if md5 is None:
            logger.error(f"Failed to calculate MD5 for image source.")
            return False
        if md5 in self.md5s:
            # logger.warning(f"Image already exists with MD5: {md5}")
            return False

        if need_check:
            with Image.open(source) as image:
                frame = np.array(image)
                if frame is None or frame.size == 0:
                    logger.warning(f"Invalid image data from source: {source}")
                    return False

        # 生成唯一文件名
        filekey = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{md5}"
        shutil.copy(source, self.get_image_path(filekey))

        # 注册到系统
        self.md5s.add(md5)
        self.keys.append(filekey)
        # logger.info(f"Saved: {filekey} (from {source})")
        return True

    def remove(self, filekey: str) -> bool:
        """删除图片

        Args:
            filekey: 要删除的文件名（不含扩展名）

        Returns:
            是否删除成功
        """
        try:
            # 查找文件路径
            filepath = self.get_image_path(filekey)
            if not filepath.exists():
                logger.warning(f"File not found: {filepath} for {filekey}")
                return False

            _, md5 = self._parse_filename_pattern(filepath.name)
            if md5 is None:
                logger.error(f"Filename pattern mismatch: {filepath.name}")
                return False

            self.md5s.discard(md5)
            # 从序列中移除
            if filekey in self.keys:
                self.keys.remove(filekey)

            # 删除图像文件
            filepath.unlink()

            # 删除label文件
            filepath = self.get_label_path(filekey)
            if filepath.exists():
                filepath.unlink()

            logger.info(f"Removed: {filekey}")
            return True

        except Exception as e:
            logger.error(f"Error removing {filekey}: {e}")
            return False

    def _calculate_md5(self, file_path: Path, chunk_size: int = 8192) -> str:
        """分块计算MD5,防止大文件内存溢出"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating MD5 for {file_path}: {e}")
            return None

    def __len__(self) -> int:
        """获取图片数量"""
        return len(self.keys)

    def __contains__(self, filename: str) -> bool:
        """检查图片是否存在"""
        return filename in self.keys
