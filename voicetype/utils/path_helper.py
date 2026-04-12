#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
路径工具模块 - 处理开发和打包环境下的路径解析
"""

import sys
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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
        base_path = Path(sys._MEIPASS)
        
        logger.info("=" * 60)
        logger.info("PACKAGED MODE - Path Resolution")
        logger.info("=" * 60)
        logger.info(f"Base path (sys._MEIPASS): {base_path}")
        logger.info(f"sys.executable: {sys.executable}")
        logger.info(f"Working directory: {os.getcwd()}")
        
        # 验证模型目录是否存在
        models_dir = base_path / "models"
        if models_dir.exists():
            logger.info(f"✓ Models directory found: {models_dir}")
            # 列出模型目录内容
            try:
                model_items = list(models_dir.iterdir())
                logger.info(f"  Contains {len(model_items)} items:")
                for item in model_items[:5]:  # 只显示前5个
                    logger.info(f"    - {item.name}")
                if len(model_items) > 5:
                    logger.info(f"    ... and {len(model_items) - 5} more")
            except Exception as e:
                logger.warning(f"  Failed to list models directory: {e}")
        else:
            logger.error(f"✗ Models directory NOT found at: {models_dir}")
            logger.error("This will cause model loading failures!")
        
        logger.info("=" * 60)
    else:
        # 开发环境，返回项目根目录
        base_path = Path(__file__).parent.parent.parent
        logger.debug(f"DEV MODE - Base path: {base_path}")
    
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
    解析模型目录路径（支持多路径回退机制）
    
    Args:
        model_dir: 模型目录（相对或绝对路径）
    
    Returns:
        str: 解析后的绝对路径字符串
        
    Raises:
        FileNotFoundError: 如果所有候选路径都不存在
    """
    # 如果已经是绝对路径且存在，直接返回
    if Path(model_dir).is_absolute():
        if Path(model_dir).exists():
            logger.info(f"✓ Model path (absolute): {model_dir}")
            return str(model_dir)
    
    # 构建候选路径列表
    candidates = []
    
    if getattr(sys, 'frozen', False):
        # 打包模式：多个候选位置
        base = Path(sys._MEIPASS)
        cwd = Path(os.getcwd())
        exe_dir = Path(sys.executable).parent
        
        candidates = [
            base / model_dir,                    # 1. _MEIPASS/models/...
            cwd / model_dir,                     # 2. 工作目录/models/...
            exe_dir / model_dir,                 # 3. exe目录/models/...
            exe_dir / "_internal" / model_dir,   # 4. exe/_internal/models/...
        ]
        
        logger.info(f"PACKAGED MODE - Resolving model path: {model_dir}")
    else:
        # 开发模式
        base = Path(__file__).parent.parent.parent
        
        candidates = [
            Path(model_dir),           # 1. 相对于当前目录
            base / model_dir,          # 2. 相对于项目根目录
        ]
        
        logger.debug(f"DEV MODE - Resolving model path: {model_dir}")
    
    # 尝试所有候选路径
    for i, path in enumerate(candidates, 1):
        logger.debug(f"  Trying [{i}/{len(candidates)}]: {path}")
        if path.exists():
            logger.info(f"  ✓ Model found at: {path}")
            return str(path)
    
    # 所有路径都失败
    logger.error(f"✗ Model NOT found: {model_dir}")
    logger.error("  Tried the following paths:")
    for i, path in enumerate(candidates, 1):
        logger.error(f"    [{i}] {path} (exists: {path.exists()})")
    
    raise FileNotFoundError(
        f"Model directory not found: {model_dir}\n"
        f"Tried {len(candidates)} locations. See logs for details."
    )

