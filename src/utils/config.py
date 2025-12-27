# -*- coding: utf-8 -*-
from utils.workroot import WorkRoot
from utils.logger import logger

import models.data as DataModel

from pathlib import Path
from typing import Any, Dict

import json
import os


class Configuration:
    def __init__(self, filepath: str = None, default: Dict[str, Any] = None):
        """
        初始化配置管理类

        :param filepath: JSON配置文件的路径
        :param default_config: 默认配置字典（当文件不存在时使用）
        """
        self.workroot = Path(WorkRoot)

        self.file = None if filepath is None else Path(filepath)
        self.default = default or {}

        self.config = {}

        if self.file is None:
            return

        # 确保配置文件存在
        if not self.file.exists():
            self._create_config_file()
        else:
            self.load()

        logger.info(f"AisLabel config @ {self.file}: {self}")

    def _create_config_file(self):
        """创建配置文件并写入默认值"""
        if self.file is None:
            return

        # 创建父目录（如果不存在）
        os.makedirs(self.file.parent, exist_ok=True)
        self.config = self.default.copy()  # 写入默认配置
        self.save()
        logger.info(f"配置文件已创建: {self.file}")

    def load(self):
        """从文件加载配置"""
        if self.file is None:
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"配置加载失败: {e}, 使用默认配置")
            self.config = self.default_config.copy()
            self.save()

    def save(self):
        """将当前配置保存到文件"""
        if self.file is None:
            return
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项的值"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """设置配置项的值"""
        self.config[key] = value
        self.save()

    def update(self, config: Dict[str, Any]):
        """批量更新配置项"""
        self.config.update(config)
        self.save()

    def __getitem__(self, key: str) -> Any:
        """通过下标访问配置项"""
        return self.config[key]

    def __setitem__(self, key: str, value: Any):
        """通过下标设置配置项"""
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        """检查配置项是否存在"""
        return key in self.config

    def __repr__(self) -> str:
        return f"<JsonConfig: {self.file}>"

    def __str__(self) -> str:
        return json.dumps(self.config, indent=4, ensure_ascii=False)


Config = Configuration(WorkRoot + '/.aislabel', DataModel.AisLabelConfig().model_dump())

Global = Configuration()
