#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Qdrant server process manager.
Auto-discovers and launches qdrant binary, monitors health, and shuts down on exit.

Default layout (self-contained under vendor/qdrant/):
  vendor/qdrant/
  ├── qdrant.exe       # Binary (auto-downloaded per platform)
  └── storage/         # Vector data (runtime generated)
"""

import atexit
import logging
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

QDRANT_PORT = 6333
QDRANT_GRPC_PORT = 6334
HEALTH_URL = f"http://127.0.0.1:{QDRANT_PORT}/healthz"
STARTUP_TIMEOUT_S = 15
STARTUP_POLL_INTERVAL_S = 0.5

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
VENDOR_QDRANT_DIR = PROJECT_ROOT / "vendor" / "qdrant"


def _find_qdrant_binary() -> Optional[Path]:
    """
    Search for qdrant binary in known locations.
    Priority: vendor/qdrant/ > bin/ > PATH > auto-download
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    exe_name = "qdrant.exe" if system == "windows" else "qdrant"

    search_dirs = [
        VENDOR_QDRANT_DIR,
        PROJECT_ROOT / "bin",
        PROJECT_ROOT,
    ]

    for d in search_dirs:
        candidate = d / exe_name
        if candidate.exists() and candidate.is_file():
            logger.info("Found Qdrant binary: %s", candidate)
            return candidate

    # Fallback: system PATH
    import shutil
    path_bin = shutil.which(exe_name)
    if path_bin:
        logger.info("Found Qdrant in PATH: %s", path_bin)
        return Path(path_bin)

    # Auto-download to vendor/qdrant/
    logger.info("Qdrant binary not found locally, attempting auto-download...")
    downloaded = _auto_download_qdrant(VENDOR_QDRANT_DIR)
    if downloaded and downloaded.exists():
        return downloaded

    return None


def _auto_download_qdrant(target_dir: Path) -> Optional[Path]:
    """
    Download Qdrant binary for current platform.
    Returns path to binary or None on failure.
    """
    import io
    import shutil as _shutil
    import stat
    import tarfile
    import zipfile
    from urllib.request import urlopen, Request
    from urllib.error import URLError

    QDRANT_VERSION = "v1.17.0"
    BASE_URL = f"https://github.com/qdrant/qdrant/releases/download/{QDRANT_VERSION}"

    ASSETS = {
        ("windows", "x86_64"): "qdrant-x86_64-pc-windows-msvc.zip",
        ("darwin", "arm64"): "qdrant-aarch64-apple-darwin.tar.gz",
        ("darwin", "x86_64"): "qdrant-x86_64-apple-darwin.tar.gz",
        ("linux", "x86_64"): "qdrant-x86_64-unknown-linux-musl.tar.gz",
        ("linux", "arm64"): "qdrant-aarch64-unknown-linux-musl.tar.gz",
    }

    MACHINE_MAP = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }

    system = platform.system().lower()
    machine = MACHINE_MAP.get(platform.machine().lower(), platform.machine().lower())
    key = (system, machine)

    if key not in ASSETS:
        logger.error("Unsupported platform for Qdrant auto-download: %s/%s", system, machine)
        return None

    asset_name = ASSETS[key]
    url = f"{BASE_URL}/{asset_name}"
    exe_name = "qdrant.exe" if system == "windows" else "qdrant"
    target_path = target_dir / exe_name

    target_dir.mkdir(parents=True, exist_ok=True)

    if target_path.exists():
        return target_path

    logger.info("Downloading Qdrant %s for %s/%s ...", QDRANT_VERSION, system, machine)
    logger.info("  URL: %s", url)

    try:
        req = Request(url, headers={"User-Agent": "VoiceType/0.1"})
        response = urlopen(req, timeout=120)
        data = response.read()
        logger.info("  Downloaded %.1f MB", len(data) / 1024 / 1024)
    except (URLError, OSError) as e:
        logger.error("Failed to download Qdrant: %s", e)
        return None

    try:
        if asset_name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    if name.endswith(exe_name):
                        with zf.open(name) as src, open(target_path, "wb") as dst:
                            _shutil.copyfileobj(src, dst)
                        break
        elif asset_name.endswith(".tar.gz"):
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                for member in tf.getmembers():
                    if member.name.endswith(exe_name) or member.name == exe_name:
                        f = tf.extractfile(member)
                        if f:
                            with open(target_path, "wb") as dst:
                                _shutil.copyfileobj(f, dst)
                        break

        if not target_path.exists():
            logger.error("Failed to extract %s from archive", exe_name)
            return None

        if system != "windows":
            target_path.chmod(target_path.stat().st_mode | stat.S_IEXEC)

        logger.info("Qdrant binary saved to: %s", target_path)
        return target_path

    except Exception as e:
        logger.error("Failed to extract Qdrant binary: %s", e)
        return None


def _is_qdrant_running() -> bool:
    try:
        r = requests.get(HEALTH_URL, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


class QdrantServer:
    """Manages a local Qdrant server process."""

    def __init__(self, port: int = QDRANT_PORT, storage_path: str = ""):
        self._port = port
        self._grpc_port = port + 1
        self._storage_path = storage_path or str(VENDOR_QDRANT_DIR / "storage")
        self._process: Optional[subprocess.Popen] = None
        self._managed = False

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    @property
    def is_running(self) -> bool:
        return _is_qdrant_running()

    def start(self) -> bool:
        """
        Start Qdrant server. Returns True if server is available.
        If already running externally, skip launch.
        """
        if _is_qdrant_running():
            logger.info("Qdrant already running at port %d, reusing", self._port)
            self._managed = False
            return True

        binary = _find_qdrant_binary()
        if binary is None:
            logger.error(
                "Qdrant binary not found and auto-download failed.\n"
                "  Manual download: https://github.com/qdrant/qdrant/releases/latest\n"
                "  Place qdrant binary in vendor/qdrant/ directory"
            )
            return False

        storage = Path(self._storage_path)
        storage.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["QDRANT__SERVICE__HTTP_PORT"] = str(self._port)
        env["QDRANT__SERVICE__GRPC_PORT"] = str(self._grpc_port)
        env["QDRANT__STORAGE__STORAGE_PATH"] = str(storage.resolve())
        # Minimize logging noise from Qdrant
        env["QDRANT__LOG_LEVEL"] = "WARN"

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW

        try:
            self._process = subprocess.Popen(
                [str(binary)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            self._managed = True
            logger.info("Starting Qdrant (pid=%d, port=%d, storage=%s)", self._process.pid, self._port, storage)
        except Exception as e:
            logger.error("Failed to start Qdrant: %s", e)
            return False

        atexit.register(self.stop)

        deadline = time.time() + STARTUP_TIMEOUT_S
        while time.time() < deadline:
            if self._process.poll() is not None:
                logger.error("Qdrant process exited with code %d", self._process.returncode)
                self._process = None
                self._managed = False
                return False
            if _is_qdrant_running():
                logger.info("Qdrant is ready (port %d)", self._port)
                return True
            time.sleep(STARTUP_POLL_INTERVAL_S)

        logger.error("Qdrant failed to start within %ds", STARTUP_TIMEOUT_S)
        self.stop()
        return False

    def stop(self):
        """Stop managed Qdrant process."""
        if not self._managed or self._process is None:
            return

        pid = self._process.pid
        logger.info("Stopping Qdrant (pid=%d)...", pid)

        try:
            if sys.platform == "win32":
                self._process.terminate()
            else:
                self._process.send_signal(signal.SIGTERM)
            self._process.wait(timeout=5)
            logger.info("Qdrant stopped gracefully")
        except subprocess.TimeoutExpired:
            logger.warning("Qdrant did not stop in time, killing")
            self._process.kill()
            self._process.wait(timeout=3)
        except Exception as e:
            logger.warning("Error stopping Qdrant: %s", e)
        finally:
            self._process = None
            self._managed = False

    def health_check(self) -> dict:
        """Return Qdrant health status."""
        try:
            r = requests.get(HEALTH_URL, timeout=2)
            return {"status": "ok", "code": r.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}
