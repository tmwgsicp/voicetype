#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Custom scene management system.
自定义场景管理系统。

Allows users to create unlimited custom scenes with:
- Custom prompt templates
- Independent hotkeys
- Application binding rules
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, asdict

from ..context.scene_classifier import Scene

logger = logging.getLogger(__name__)


@dataclass
class CustomScene:
    """Custom scene definition."""
    
    id: str
    name: str
    prompt: str
    hotkey: str = ""
    icon: str = "💬"
    app_rules: List[str] = None
    enabled: bool = True
    builtin: bool = False
    
    def __post_init__(self):
        if self.app_rules is None:
            self.app_rules = []
    
    def matches_app(self, app_name: str, window_title: str = "") -> bool:
        """
        Check if this scene matches the given window.
        规则（子串、大小写不敏感）同时匹配应用名和窗口标题——这样浏览器里的
        网页应用（如标题含 gmail / docs / feishu）也能被识别。
        """
        if not self.app_rules:
            return False

        haystack = f"{app_name} {window_title}".lower()
        for rule in self.app_rules:
            if rule.lower() in haystack:
                return True
        return False
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_scene(self) -> Scene:
        """Convert to Scene object for pipeline."""
        return Scene(
            name=self.id,
            display_name=self.name,
            description=self.prompt[:100] + "..." if len(self.prompt) > 100 else self.prompt,
        )
    
    @classmethod
    def from_dict(cls, data: dict) -> "CustomScene":
        return cls(**data)


class SceneManager:
    """
    Scene management system.
    场景管理系统。
    
    Features:
    - Load/save custom scenes
    - Hotkey management with conflict detection
    - App binding rules
    - Scene switching logic
    """
    
    def __init__(self, scenes_file: Optional[Path] = None):
        self._scenes: Dict[str, CustomScene] = {}
        self._scenes_file = scenes_file
        self._active_scene: Optional[CustomScene] = None
        self._manual_override: bool = False
        self._on_scene_change: Optional[Callable[[Scene], Awaitable[None]]] = None
        
        if scenes_file and scenes_file.exists():
            self.load_scenes()
        else:
            self._load_builtin_scenes()
    
    def _load_builtin_scenes(self):
        """Load built-in default scenes."""
        for scene in self._builtin_scene_defs():
            self._scenes[scene.id] = scene

    def _builtin_scene_defs(self) -> List["CustomScene"]:
        """内置场景的代码定义（唯一真源，供加载和刷新使用）。"""
        return [
            CustomScene(
                id="code",
                name="编程",
                icon="💻",
                prompt="保留所有技术术语原样（如 API、user_id、callback），不要翻译成中文。",
                hotkey="",
                app_rules=["cursor", "code.exe", "vscode", "pycharm", "idea", "webstorm",
                           "goland", "clion", "rider", "sublime", "trae", "android studio",
                           "zed", "windsurf"],
                builtin=True,
            ),
            CustomScene(
                id="document",
                name="文档",
                icon="📝",
                prompt="正式书面语，补全标点，注意段落结构。",
                hotkey="",
                app_rules=["winword", "wps", "excel", "powerpnt", "notion", "obsidian",
                           "腾讯文档", "语雀", "yuque", "飞书文档", "docs.google", "石墨"],
                builtin=True,
            ),
            CustomScene(
                id="terminal",
                name="终端",
                icon="⌨️",
                prompt="终端命令，保留命令和参数原样，不加标点。",
                hotkey="",
                app_rules=["cmd.exe", "powershell", "pwsh", "windowsterminal", "wt.exe",
                           "terminal", "iterm", "alacritty", "cmder", "warp", "hyper"],
                builtin=True,
            ),
            CustomScene(
                id="email",
                name="邮件",
                icon="✉️",
                prompt="正式邮件语气，结构清晰，补全称呼和标点，商务得体。",
                hotkey="",
                app_rules=["outlook", "foxmail", "thunderbird", "gmail", "邮箱", "mail.qq",
                           "网易邮箱", "mailmaster"],
                builtin=True,
            ),
            CustomScene(
                id="chat",
                name="聊天",
                icon="💬",
                prompt="保持口语化和简洁，不要改成书面语。",
                hotkey="",
                app_rules=["wechat", "微信", "qq.exe", "tim", "dingtalk", "钉钉", "slack",
                           "discord", "telegram", "teams", "feishu", "lark", "飞书",
                           "企业微信", "wxwork", "whatsapp"],
                builtin=True,
            ),
            CustomScene(
                id="translate_to_en",
                name="中译英",
                icon="🌐",
                prompt="【翻译模式，覆盖上面的默认清理规则和禁止翻译规则】这是唯一允许翻译的场景。将用户口述的内容翻译成地道自然的英文，必须 100% 输出英文，绝对不要输出中文原文。先去掉口语和填充词再翻译，表达核心意思而非逐字直译，语气专业简洁。",
                hotkey="<ctrl>+<shift>+1",
                app_rules=[],
                builtin=True,
            ),
            CustomScene(
                id="general",
                name="通用",
                icon="📄",
                prompt="通用场景，基础清理即可。",
                hotkey="",
                app_rules=[],
                builtin=True,
            ),
        ]

        logger.info(f"Loaded {len(builtin_scenes)} built-in scenes")
    
    def add_scene(self, scene: CustomScene) -> bool:
        """Add or update a scene."""
        if not scene.id:
            scene.id = f"scene_{uuid.uuid4().hex[:8]}"
        
        # Check hotkey conflict
        if scene.hotkey:
            conflict = self._check_hotkey_conflict(scene.hotkey, scene.id)
            if conflict:
                raise ValueError(f"Hotkey conflict: {conflict.name} already uses {scene.hotkey}")
        
        self._scenes[scene.id] = scene
        self.save_scenes()
        logger.info(f"Added scene: {scene.name} (id={scene.id})")
        return True
    
    def remove_scene(self, scene_id: str) -> bool:
        """Remove a custom scene (builtin scenes cannot be removed)."""
        scene = self._scenes.get(scene_id)
        if not scene:
            return False
        
        if scene.builtin:
            raise ValueError("Cannot remove builtin scene")
        
        del self._scenes[scene_id]
        self.save_scenes()
        logger.info(f"Removed scene: {scene_id}")
        return True
    
    def get_scene(self, scene_id: str) -> Optional[CustomScene]:
        """Get a scene by ID."""
        return self._scenes.get(scene_id)
    
    def list_scenes(self, enabled_only: bool = False) -> List[CustomScene]:
        """List all scenes."""
        scenes = list(self._scenes.values())
        
        if enabled_only:
            scenes = [s for s in scenes if s.enabled]
        
        return scenes
    
    def switch_scene(self, scene_id: str, manual: bool = False) -> Scene:
        """
        Switch to a scene.
        切换场景。
        
        Args:
            scene_id: Scene ID to switch to
            manual: If True, user manually switched (disable auto-detection)
        
        Returns:
            Scene object for pipeline
        """
        scene = self._scenes.get(scene_id)
        if not scene:
            raise ValueError(f"Scene {scene_id} not found")
        
        self._active_scene = scene
        self._manual_override = manual
        
        logger.info(f"Switched to scene: {scene.name} (manual={manual})")
        return scene.to_scene()
    
    def auto_detect_scene(self, app_name: str) -> Optional[Scene]:
        """Auto-detect scene based on app name (返回 pipeline 用的 Scene)。"""
        cs = self.detect_scene(app_name)
        return cs.to_scene() if cs else None

    def detect_scene(self, app_name: str, window_title: str = "") -> Optional["CustomScene"]:
        """
        根据当前窗口自动匹配场景，返回 CustomScene（含提示词），供引擎应用。
        手动覆盖生效时返回 None（不自动切换）。无匹配时回退到 general。
        """
        if self._manual_override:
            return None

        for scene in self._scenes.values():
            if scene.enabled and scene.id != "general" and scene.matches_app(app_name, window_title):
                self._active_scene = scene
                return scene

        general = self._scenes.get("general")
        if general:
            self._active_scene = general
        return general
    
    def clear_manual_override(self):
        """Clear manual override, back to auto-detection."""
        self._manual_override = False
        logger.info("Manual scene override cleared")
    
    def get_active_scene(self) -> Optional[CustomScene]:
        """Get currently active scene."""
        return self._active_scene
    
    def _check_hotkey_conflict(self, hotkey: str, exclude_id: str = "") -> Optional[CustomScene]:
        """Check if hotkey conflicts with existing scenes."""
        for scene in self._scenes.values():
            if scene.id != exclude_id and scene.hotkey == hotkey:
                return scene
        return None
    
    def save_scenes(self):
        """Persist scenes to file."""
        if not self._scenes_file:
            return
        
        data = {
            "scenes": [scene.to_dict() for scene in self._scenes.values()]
        }
        
        self._scenes_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._scenes_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(self._scenes)} scenes to {self._scenes_file}")
    
    def load_scenes(self):
        """Load scenes from file."""
        if not self._scenes_file or not self._scenes_file.exists():
            logger.warning(f"Scenes file not found: {self._scenes_file}")
            self._load_builtin_scenes()
            return
        
        try:
            with open(self._scenes_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._scenes.clear()
            for scene_data in data.get("scenes", []):
                scene = CustomScene.from_dict(scene_data)
                self._scenes[scene.id] = scene

            # 用代码里的最新定义刷新内置场景的提示词/名称/图标（内置场景的行为以代码为准，
            # 保留用户自定义的 app_rules/hotkey/enabled）。缺失的内置场景则补齐。
            for bd in self._builtin_scene_defs():
                existing = self._scenes.get(bd.id)
                if existing and existing.builtin:
                    existing.name = bd.name
                    existing.icon = bd.icon
                    existing.prompt = bd.prompt
                elif existing is None:
                    self._scenes[bd.id] = bd
            self.save_scenes()

            logger.info(f"Loaded {len(self._scenes)} scenes from {self._scenes_file}")
        except Exception as e:
            logger.error(f"Failed to load scenes: {e}")
            self._load_builtin_scenes()
    
    def export_scenes(self, include_builtin: bool = True) -> List[dict]:
        """Export scenes to dict format."""
        scenes = self.list_scenes()
        
        if not include_builtin:
            scenes = [s for s in scenes if not s.builtin]
        
        return [scene.to_dict() for scene in scenes]
    
    def import_scenes(self, scenes_data: List[dict], merge: bool = True) -> int:
        """
        Import scenes from external data.
        
        Args:
            scenes_data: List of scene dicts
            merge: If True, merge with existing; if False, replace all (except builtin)
        
        Returns:
            Number of scenes imported
        """
        if not merge:
            # Keep builtin scenes
            builtin = {sid: s for sid, s in self._scenes.items() if s.builtin}
            self._scenes.clear()
            self._scenes.update(builtin)
        
        count = 0
        for scene_data in scenes_data:
            try:
                scene = CustomScene.from_dict(scene_data)
                self._scenes[scene.id] = scene
                count += 1
            except Exception as e:
                logger.error(f"Failed to import scene: {e}")
        
        self.save_scenes()
        logger.info(f"Imported {count} scenes (merge={merge})")
        return count
