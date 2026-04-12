# -*- mode: python ; coding: utf-8 -*-

import sys
import platform

# ========== 平台特定配置 ==========

# 平台特定的 hiddenimports
platform_imports = []
if sys.platform == 'win32':
    platform_imports = ['win32gui', 'win32process', 'win32clipboard', 'win32con']
elif sys.platform == 'darwin':
    platform_imports = ['AppKit', 'Quartz', 'Foundation']
elif sys.platform.startswith('linux'):
    platform_imports = ['Xlib', 'Xlib.display', 'Xlib.X']

# ========== PyInstaller 配置 ==========

a = Analysis(
    ['voicetype\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('voicetype', 'voicetype'),
    ],
    hiddenimports=[
        'voicetype',
        'voicetype.engine',
        'voicetype.config',
        'voicetype.api.routes',
        'voicetype.api.config_routes',
        'voicetype.api.rule_routes',
        'voicetype.api.scene_routes',
        'voicetype.api.voiceprint_routes',
        'voicetype.voiceforge.extensions.providers.sherpa.asr_sherpa',
        'voicetype.voiceforge.extensions.providers.sherpa.kws_sherpa',
        'voicetype.voiceforge.extensions.providers.aliyun.asr_qwen',
        'voicetype.voiceforge.extensions.providers.tencent.asr_tencent',
        'fastapi',
        'uvicorn',
        'pynput',
        'sounddevice',
        'numpy',
        'openai',
        'psutil',
        'keyring',
        'sherpa_onnx',
    ] + platform_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',
        'torchvision',
        'torchaudio',
        'jax',
        'jaxlib',
        'tensorflow',
        'cv2',
        'opencv',
        'scipy',
        'pandas',
        'matplotlib',
        'imageio',
        'imageio_ffmpeg',
        'sklearn',
        'skimage',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 关键：输出为文件夹模式
    name='voicetype-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='voicetype-server'
)
