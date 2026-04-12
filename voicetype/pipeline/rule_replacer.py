#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Term rule replacement system.
术语规则替换系统。

Applies user-defined rules to correct ASR mistakes before LLM processing.
在 LLM 处理前应用用户自定义规则纠正 ASR 错误。
"""

import re
import logging
from typing import Dict, List, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class TermRule:
    """Single term replacement rule."""
    
    def __init__(
        self,
        rule_id: str,
        wrong: str,
        correct: str,
        category: str = "general",
        enabled: bool = True,
        case_sensitive: bool = False,
        whole_word: bool = False,
    ):
        self.id = rule_id
        self.wrong = wrong
        self.correct = correct
        self.category = category
        self.enabled = enabled
        self.case_sensitive = case_sensitive
        self.whole_word = whole_word
    
    def apply(self, text: str) -> str:
        """Apply this rule to text."""
        if not self.enabled:
            return text
        
        if self.whole_word:
            pattern = rf'\b{re.escape(self.wrong)}\b'
        else:
            pattern = re.escape(self.wrong)
        
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.sub(pattern, self.correct, text, flags=flags)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "wrong": self.wrong,
            "correct": self.correct,
            "category": self.category,
            "enabled": self.enabled,
            "case_sensitive": self.case_sensitive,
            "whole_word": self.whole_word,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TermRule":
        return cls(
            rule_id=data["id"],
            wrong=data["wrong"],
            correct=data["correct"],
            category=data.get("category", "general"),
            enabled=data.get("enabled", True),
            case_sensitive=data.get("case_sensitive", False),
            whole_word=data.get("whole_word", False),
        )


class RuleReplacer:
    """
    Term rule replacement engine.
    术语规则替换引擎。
    
    Features:
    - Apply user-defined rules before LLM processing
    - Support locking tags to prevent LLM from overriding corrections
    - Category-based rule management
    """
    
    def __init__(self, rules_file: Optional[Path] = None):
        self._rules: Dict[str, TermRule] = {}
        self._rules_file = rules_file
        
        # 首先加载默认规则作为 fallback
        self._load_default_rules()
        
        # 然后尝试加载自定义规则（如果存在且有效）
        if rules_file and rules_file.exists():
            try:
                self.load_rules()
            except Exception as e:
                # 静默失败，继续使用默认规则
                logger.debug(f"Could not load custom rules, using defaults: {e}")
    
    def _load_default_rules(self):
        """Load built-in default rules for common tech terms."""
        default_rules = [
            # 产品名
            ("克劳德", "Claude", "product"),
            # 核心技术术语
            ("用户ID", "user_id", "tech"),
            ("用户艾迪", "user_id", "tech"),
            ("接口", "API", "tech"),
        ]
        
        for i, (wrong, correct, category) in enumerate(default_rules):
            rule = TermRule(
                rule_id=f"builtin_{i}",
                wrong=wrong,
                correct=correct,
                category=category,
                enabled=True,
            )
            self._rules[rule.id] = rule
        
        logger.info(f"Loaded {len(default_rules)} built-in rules")
    
    def add_rule(self, rule: TermRule) -> bool:
        """Add or update a rule."""
        self._rules[rule.id] = rule
        self.save_rules()
        logger.info(f"Added rule: '{rule.wrong}' → '{rule.correct}'")
        return True
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            self.save_rules()
            logger.info(f"Removed rule: {rule_id}")
            return True
        return False
    
    def get_rule(self, rule_id: str) -> Optional[TermRule]:
        """Get a rule by ID."""
        return self._rules.get(rule_id)
    
    def list_rules(self, category: Optional[str] = None, enabled_only: bool = False) -> List[TermRule]:
        """List all rules, optionally filtered by category and enabled status."""
        rules = list(self._rules.values())
        
        if category:
            rules = [r for r in rules if r.category == category]
        
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        
        return rules
    
    def apply(self, text: str, add_lock_tags: bool = True) -> str:
        """
        Apply all enabled rules to text.
        对文本应用所有启用的规则。
        
        Args:
            text: Input text from ASR
            add_lock_tags: If True, wrap corrected terms with <lock> tags
        
        Returns:
            Text with rules applied
        """
        result = text
        corrected_terms = []
        
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            before = result
            result = rule.apply(result)
            
            if result != before and add_lock_tags:
                corrected_terms.append(rule.correct)
        
        if add_lock_tags and corrected_terms:
            for term in corrected_terms:
                result = result.replace(term, f"<lock>{term}</lock>")
        
        if result != text:
            logger.info(f"Rule replacement: '{text}' → '{result}'")
        
        return result
    
    def save_rules(self):
        """Persist rules to file."""
        if not self._rules_file:
            return
        
        data = {
            "rules": [rule.to_dict() for rule in self._rules.values()]
        }
        
        self._rules_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._rules_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(self._rules)} rules to {self._rules_file}")
    
    def load_rules(self):
        """Load rules from file."""
        if not self._rules_file or not self._rules_file.exists():
            # 文件不存在时静默返回，保留默认规则
            logger.debug(f"Rules file not found: {self._rules_file}, using defaults")
            return
        
        try:
            with open(self._rules_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 清空并加载自定义规则
            self._rules.clear()
            for rule_data in data.get("rules", []):
                rule = TermRule.from_dict(rule_data)
                self._rules[rule.id] = rule
            
            logger.info(f"Loaded {len(self._rules)} custom rules from {self._rules_file}")
        except Exception as e:
            # JSON 格式错误等异常，静默失败，保留默认规则
            logger.debug(f"Failed to load custom rules: {e}")
    
    def import_rules(self, rules_data: List[dict], merge: bool = True) -> int:
        """
        Import rules from external data.
        
        Args:
            rules_data: List of rule dicts
            merge: If True, merge with existing rules; if False, replace all
        
        Returns:
            Number of rules imported
        """
        if not merge:
            self._rules.clear()
        
        count = 0
        for rule_data in rules_data:
            try:
                rule = TermRule.from_dict(rule_data)
                self._rules[rule.id] = rule
                count += 1
            except Exception as e:
                logger.error(f"Failed to import rule: {e}")
        
        self.save_rules()
        logger.info(f"Imported {count} rules (merge={merge})")
        return count
    
    def export_rules(self, category: Optional[str] = None) -> List[dict]:
        """Export rules to dict format."""
        rules = self.list_rules(category=category)
        return [rule.to_dict() for rule in rules]


def remove_lock_tags(text: str) -> str:
    """
    Remove <lock> tags from text after LLM processing.
    LLM 处理后移除锁定标签。
    """
    return re.sub(r'<lock>(.*?)</lock>', r'\1', text)
