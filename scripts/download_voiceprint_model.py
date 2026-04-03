#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Download speaker recognition ONNX model.
下载声纹识别 ONNX 模型。
"""

import urllib.request
import tarfile
from pathlib import Path

MODEL_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx.tar.bz2"
MODEL_DIR = Path("models")
MODEL_ARCHIVE = MODEL_DIR / "speaker_model.tar.bz2"
MODEL_FILE = MODEL_DIR / "speaker_recognition.onnx"

def download_model():
    """下载声纹识别模型"""
    
    print("Downloading speaker recognition model...")
    print(f"URL: {MODEL_URL}")
    print(f"Target: {MODEL_ARCHIVE}")
    
    MODEL_DIR.mkdir(exist_ok=True)
    
    try:
        # 下载
        urllib.request.urlretrieve(MODEL_URL, MODEL_ARCHIVE)
        print(f"[OK] Downloaded: {MODEL_ARCHIVE}")
        
        # 解压
        print("Extracting...")
        with tarfile.open(MODEL_ARCHIVE, "r:bz2") as tar:
            tar.extractall(MODEL_DIR)
        
        # 查找模型文件
        onnx_files = list(MODEL_DIR.glob("**/*.onnx"))
        if onnx_files:
            # 重命名为统一名称
            onnx_files[0].rename(MODEL_FILE)
            print(f"[OK] Model ready: {MODEL_FILE}")
            
            # 清理压缩包
            MODEL_ARCHIVE.unlink()
            print("[OK] Cleaned up archive")
        else:
            print("[FAIL] No ONNX file found in archive")
        
        print("\n[SUCCESS] Model download completed!")
        return True
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

if __name__ == "__main__":
    download_model()
