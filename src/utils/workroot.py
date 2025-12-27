# -*- coding: utf-8 -*-
import sys
import os
import platform

from pathlib import Path


def _work_root() -> str:
    """获取应用程序基础路径（兼容开发模式、打包模式及不同平台）"""
    # 开发模式
    if not getattr(sys, 'frozen', False):
        current = Path(os.path.abspath(__file__))
        return str(current.parent.parent.parent)

    current = Path(sys.executable)

    # 打包模式 macOS 系统获取可执行文件路径(在.app/Contents/MacOS/下)
    if platform.system() == 'Darwin':
        # 向上回退三层：MacOS → Contents → .app
        current = current.parent.parent.parent

    # 打包模式 Windows/Linux/macOS 或其他系统
    return str(current.parent)


WorkRoot = _work_root()
