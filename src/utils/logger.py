# -*- coding: utf-8 -*-
import logging.handlers
from utils.workroot import WorkRoot

import logging
import os
import sys


class SingletonLogger:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            # 创建 Logger 实例
            logger = logging.getLogger(__name__)
            # 设置日志级别
            logger.setLevel(logging.DEBUG)

            formatter = logging.Formatter('[%(asctime)s|%(levelname)s|%(filename)s:%(lineno)d] %(message)s')

            file = os.path.join(WorkRoot, 'logs', 'mocke.log')
            os.makedirs(os.path.dirname(file), exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                file, maxBytes=100 * 1024 * 1024, backupCount=20, encoding='utf-8'
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            # 创建控制台处理器
            if not getattr(sys, 'frozen', False):
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)

            cls._instance = logger
        return cls._instance


logger = SingletonLogger()
