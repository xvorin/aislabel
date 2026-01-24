# -*- coding: utf-8 -*-
from utils.config import Config, Configuration
from project.storage import Storage

from datetime import datetime
import models.data as DataModel
import os


class Project:
    """项目管理器"""

    def __init__(self, directory: str, schema: str = None, task: str = "", desc: str = ""):
        self.directory = directory
        self.storage = Storage(self.directory)

        type = [s for s in Config['schemas'] if s['name'] == schema]
        project_filepath = os.path.join(directory, '.project')
        self.config = Configuration(
            project_filepath,
            default=DataModel.ProjectConfig(
                creation=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                directory=directory,
                task=task,
                description=desc,
                mschema=type[0] if len(type) > 0 else DataModel.LabelSchema(),
                mfilter=DataModel.ProjectFilterConfig(),
                aannotate=DataModel.AutoAnnotate(),
            ).model_dump(),
        )

        if self.config['mschema'] is None:
            raise ValueError("schema must be specified")

        self.schema = DataModel.LabelSchema.model_validate(self.config['mschema'])

    @classmethod
    def create(cls, directory: str, label: str, task: str, desc: str):
        """工厂方法：创建新项目"""
        os.makedirs(directory, exist_ok=True)
        return cls(directory, label, task, desc)

    def filekeys(self) -> int:
        return self.storage.filekeys()

    def create_time(self, filekey: str):
        return self.storage.get_create_time(filekey)

    def image_path(self, filekey: str):
        """获取文件的完整路径"""
        return self.storage.get_image_path(filekey)

    def label_path(self, filekey: str):
        """获取文件的完整路径"""
        return self.storage.get_label_path(filekey)

    def import_media(self, sources):
        self.storage.import_media(sources)

    def remove(self, filekey: str):
        self.storage.remove(filekey)
