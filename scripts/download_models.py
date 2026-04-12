#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
统一的模型下载脚本（仅供开发者使用）
Download all required models for development.

生产用户请直接使用打包后的安装包，模型已内置。
For production users, use the built installer with models included.

Usage:
    python scripts/download_models.py              # 下载所有默认模型
    python scripts/download_models.py --all        # 下载所有可选模型
    python scripts/download_models.py --asr        # 仅下载 ASR 模型
    python scripts/download_models.py --kws        # 仅下载 KWS 模型
    python scripts/download_models.py --voiceprint # 仅下载声纹识别模型
"""

import os
import sys
import urllib.request
import tarfile
import zipfile
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 模型配置
MODELS = {
    "asr_bilingual": {
        "name": "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20",
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2",
        "type": "tar.bz2",
        "desc": "中英混合 ASR 模型（60MB，推荐，默认）",
        "default": True,
        "category": "asr"
    },
    "kws": {
        "name": "sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01",
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01.tar.bz2",
        "type": "tar.bz2",
        "desc": "关键词唤醒模型（3.3MB，支持自定义中文唤醒词，默认）",
        "default": True,
        "category": "kws"
    },
    "voiceprint": {
        "name": "speaker_recognition.onnx",
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx",
        "type": "direct",
        "desc": "声纹识别模型（用于说话人验证，默认）",
        "default": True,
        "category": "voiceprint"
    }
}


def download_file(url: str, output_path: Path):
    """下载文件并显示进度"""
    logger.info(f"下载中: {url}")
    
    def report_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(downloaded * 100 / total_size, 100) if total_size > 0 else 0
        # 使用 ASCII 字符避免编码问题
        sys.stdout.write(f"\r  Progress: {percent:.1f}%")
        sys.stdout.flush()
    
    try:
        urllib.request.urlretrieve(url, output_path, reporthook=report_progress)
        sys.stdout.write("\n")
        logger.info(f"Downloaded to: {output_path}")
    except Exception as e:
        sys.stdout.write("\n")
        raise e


def extract_archive(archive_path: Path, extract_to: Path, archive_type: str):
    """解压压缩包"""
    if archive_type == "direct":
        # 直接文件，不需要解压
        return
    
    logger.info(f"解压中: {archive_path}")
    
    if archive_type == "tar.bz2":
        with tarfile.open(archive_path, "r:bz2") as tar:
            tar.extractall(path=extract_to)
    elif archive_type == "zip":
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    
    logger.info(f"已解压到: {extract_to}")


def download_models(categories=None, all_models=False):
    """
    下载模型
    
    Args:
        categories: 指定要下载的类别列表 ['asr', 'kws', 'voiceprint']
        all_models: 是否下载所有模型（包括可选模型）
    """
    # 确定模型目录
    project_root = Path(__file__).parent.parent
    models_dir = project_root / "models"
    models_dir.mkdir(exist_ok=True)
    
    logger.info(f"模型目录: {models_dir}")
    logger.info("="*60)
    
    # 筛选要下载的模型
    if categories:
        # 只下载指定类别
        models_to_download = {
            k: v for k, v in MODELS.items() 
            if v["category"] in categories
        }
    elif all_models:
        # 下载所有模型
        models_to_download = MODELS
    else:
        # 下载默认模型
        models_to_download = {
            k: v for k, v in MODELS.items() 
            if v.get("default", False)
        }
    
    if not models_to_download:
        logger.error("没有找到要下载的模型")
        return False
    
    # 显示下载计划
    logger.info("将下载以下模型:")
    for model_key, model_info in models_to_download.items():
        logger.info(f"  - {model_key}: {model_info['desc']}")
    logger.info("="*60 + "\n")
    
    success_count = 0
    total_count = len(models_to_download)
    
    for model_key, model_info in models_to_download.items():
        model_name = model_info["name"]
        model_url = model_info["url"]
        model_type = model_info["type"]
        model_desc = model_info.get("desc", "")
        
        # 特殊处理声纹模型（单文件）
        if model_type == "direct":
            # 直接下载，不解压
            model_path = models_dir / model_name
        else:
            model_path = models_dir / model_name
        
        # 如果已存在则跳过
        if model_path.exists():
            logger.info(f"✓ 模型已存在，跳过: {model_name}")
            success_count += 1
            continue
        
        logger.info(f"\n{'='*60}")
        logger.info(f"下载模型 [{success_count + 1}/{total_count}]: {model_key.upper()}")
        logger.info(f"描述: {model_desc}")
        logger.info(f"{'='*60}")
        
        # 下载文件
        if model_type == "direct":
            # 直接下载到目标位置
            try:
                download_file(model_url, model_path)
                logger.info(f"✓ 成功安装: {model_name}\n")
                success_count += 1
            except Exception as e:
                logger.error(f"✗ 下载失败 {model_name}: {e}")
                if model_path.exists():
                    model_path.unlink()
                continue
        else:
            # 下载压缩包并解压
            archive_name = f"{model_key}_temp.{model_type}"
            archive_path = models_dir / archive_name
            
            try:
                download_file(model_url, archive_path)
                extract_archive(archive_path, models_dir, model_type)
                
                # 清理压缩包
                archive_path.unlink()
                logger.info(f"清理压缩包: {archive_name}")
                
                logger.info(f"✓ 成功安装: {model_name}\n")
                success_count += 1
            
            except Exception as e:
                logger.error(f"✗ 下载失败 {model_name}: {e}")
                if archive_path.exists():
                    archive_path.unlink()
                # 继续下载其他模型
                continue
    
    # 总结
    logger.info("\n" + "="*60)
    logger.info(f"下载完成: {success_count}/{total_count} 个模型")
    logger.info("="*60)
    
    if success_count > 0:
        logger.info("\n模型位置:")
        for model_key, model_info in models_to_download.items():
            model_name = model_info["name"]
            model_path = models_dir / model_name
            if model_path.exists():
                logger.info(f"  ✓ {model_key}: {model_path}")
        
        logger.info("\n后续步骤:")
        logger.info("  1. 复制 .env.example 为 .env")
        logger.info("  2. 配置 LLM API Key（必需）")
        logger.info("  3. 启动服务: python -m voicetype.main")
        logger.info("  4. 访问 Web UI: http://127.0.0.1:18233/")
    
    return success_count == total_count


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="VoiceType 模型下载工具（开发者专用）",
        epilog="注意：生产用户请使用打包后的安装包，模型已内置。"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="下载所有模型（包括可选模型）"
    )
    parser.add_argument(
        "--asr",
        action="store_true",
        help="仅下载 ASR 语音识别模型"
    )
    parser.add_argument(
        "--kws",
        action="store_true",
        help="仅下载 KWS 关键词唤醒模型"
    )
    parser.add_argument(
        "--voiceprint",
        action="store_true",
        help="仅下载声纹识别模型"
    )
    
    args = parser.parse_args()
    
    # 确定下载类别
    categories = []
    if args.asr:
        categories.append("asr")
    if args.kws:
        categories.append("kws")
    if args.voiceprint:
        categories.append("voiceprint")
    
    # 执行下载
    success = download_models(
        categories=categories if categories else None,
        all_models=args.all
    )
    
    sys.exit(0 if success else 1)
