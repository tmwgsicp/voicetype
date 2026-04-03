#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Scene classifier: maps active window info to a scene label.
Uses a rule engine (app name + title regex matching) with user-configurable rules.
"""

import re
import logging
import dataclasses
from typing import Optional

from ..platform.window_watcher import WindowInfo

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Scene:
    name: str
    display_name: str
    description: str


SCENES = {
    "terminal": Scene(
        name="terminal",
        display_name="Terminal",
        description="User is typing in a terminal/command line. Output should be concise, "
                    "technical, command-oriented. Preserve exact technical terms.",
    ),
    "code_comment": Scene(
        name="code_comment",
        display_name="Code",
        description="User is in a code editor. Output should be precise technical language, "
                    "suitable for code comments or documentation. Keep it brief.",
    ),
    "email": Scene(
        name="email",
        display_name="Email",
        description="User is composing an email. Output should be formal, well-structured, "
                    "with proper paragraph breaks. Use business-appropriate tone.",
    ),
    "chat": Scene(
        name="chat",
        display_name="Chat",
        description="User is in a messaging app. Output can be casual, concise. "
                    "Remove filler words but preserve conversational tone.",
    ),
    "document": Scene(
        name="document",
        display_name="Document",
        description="User is writing a document/report. Output should use formal written language, "
                    "complete sentences, and appropriate formatting.",
    ),
    "note": Scene(
        name="note",
        display_name="Note",
        description="User is taking notes. Output can use shorthand, bullet points, "
                    "and abbreviated forms. Focus on key information.",
    ),
    "translate_to_en": Scene(
        name="translate_to_en",
        display_name="Translate to EN",
        description="User dictates in Chinese, output fluent native English. "
                    "Translate meaning, not word-by-word. Use professional tone.",
    ),
    "general": Scene(
        name="general",
        display_name="General",
        description="General purpose input. Clean up filler words and self-corrections, "
                    "output clear written text.",
    ),
}


@dataclasses.dataclass
class ClassifyRule:
    scene: str
    app_names: list[str] = dataclasses.field(default_factory=list)
    title_patterns: list[str] = dataclasses.field(default_factory=list)


DEFAULT_RULES: list[ClassifyRule] = [
    ClassifyRule(
        scene="terminal",
        app_names=[
            "cmd.exe", "powershell.exe", "pwsh.exe",
            "WindowsTerminal.exe", "wt.exe",
            "Terminal", "iTerm2", "Alacritty", "Hyper",
            "bash", "zsh", "fish",
        ],
    ),
    ClassifyRule(
        scene="code_comment",
        app_names=[
            "Code.exe", "Code - Insiders",
            "code", "code-insiders",
            "idea64.exe", "idea", "pycharm64.exe", "pycharm",
            "webstorm64.exe", "goland64.exe",
            "Sublime Text", "sublime_text",
            "Atom", "Cursor.exe", "cursor",
        ],
    ),
    ClassifyRule(
        scene="email",
        title_patterns=[
            r"(?i)gmail", r"(?i)outlook", r"(?i)mail",
            r"(?i)thunderbird", r"(?i)foxmail",
        ],
        app_names=["OUTLOOK.EXE", "Foxmail.exe", "Thunderbird"],
    ),
    ClassifyRule(
        scene="chat",
        app_names=[
            "WeChat.exe", "wechat", "WeChat",
            "Slack.exe", "Slack",
            "Discord.exe", "Discord",
            "Telegram.exe", "Telegram",
            "Teams.exe", "Microsoft Teams",
            "QQ.exe", "DingTalk.exe", "dingtalk",
            "Feishu.exe", "Lark",
        ],
    ),
    ClassifyRule(
        scene="document",
        app_names=[
            "WINWORD.EXE", "EXCEL.EXE", "POWERPNT.EXE",
            "Pages", "Numbers", "Keynote",
            "wps.exe", "et.exe", "wpp.exe",
        ],
        title_patterns=[
            r"(?i)google docs", r"(?i)google sheets",
            r"(?i)notion\.so",
        ],
    ),
    ClassifyRule(
        scene="note",
        app_names=[
            "Obsidian.exe", "Obsidian",
            "Notion.exe", "Notion",
            "Typora.exe", "Typora",
            "Joplin.exe",
            "notepad.exe", "notepad++.exe",
            "TextEdit",
        ],
        title_patterns=[r"(?i)notion\.so/.*"],
    ),
    ClassifyRule(
        scene="translate_to_en",
        title_patterns=[
            r"(?i)clickup",
        ],
    ),
]


class SceneClassifier:
    """Classifies the current window into a scene using rule matching."""

    def __init__(self, custom_rules: Optional[list[ClassifyRule]] = None):
        self._rules = custom_rules or DEFAULT_RULES
        self._current_scene: Scene = SCENES["general"]
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        self._compile_rules()

    def _compile_rules(self):
        for rule in self._rules:
            self._compiled_patterns[rule.scene] = [
                re.compile(p) for p in rule.title_patterns
            ]

    @property
    def current_scene(self) -> Scene:
        return self._current_scene

    def classify(self, window: WindowInfo) -> Scene:
        if not window.app_name and not window.window_title:
            return SCENES["general"]

        app = window.app_name.lower()

        for rule in self._rules:
            for name in rule.app_names:
                if name.lower() == app:
                    self._current_scene = SCENES[rule.scene]
                    return self._current_scene

            for pattern in self._compiled_patterns.get(rule.scene, []):
                if pattern.search(window.window_title):
                    self._current_scene = SCENES[rule.scene]
                    return self._current_scene

        self._current_scene = SCENES["general"]
        return self._current_scene
