#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
路径工具模块 - 处理开发和打包环境下的路径解析
"""

import sys
import os
from pathlib import Path


def get_base_path() -> Path:
    """
    获取应用基础路径（支持开发和打包环境）
    
    Returns:
        Path: 应用基础路径
        
    Note:
        - 开发环境: 返回项目根目录
        - PyInstaller 打包后: 返回 _MEIPASS（临时解压目录）
          在 _MEIPASS 下，目录结构与开发环境一致
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后，_MEIPASS 指向临时解压目录
        # 模型文件已经被打包在 _MEIPASS 下
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境，返回项目根目录
        base_path = Path(__file__).parent.parent
    return base_path


def resolve_path(relative_path: str) -> Path:
    """
    将相对路径解析为绝对路径
    
    Args:
        relative_path: 相对于项目根目录的路径
    
    Returns:
        Path: 解析后的绝对路径
    """
    path = Path(relative_path)
    if not path.is_absolute():
        base_path = get_base_path()
        path = base_path / relative_path
    return path


def resolve_model_path(model_dir: str) -> str:
    """
    解析模型目录路径
    
    Args:
        model_dir: 模型目录（相对或绝对路径）
    
    Returns:
        str: 解析后的绝对路径字符串
    """
    resolved = resolve_path(model_dir)
    return str(resolved)
