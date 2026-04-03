#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
API routes for term rule management.
术语规则管理 API。
"""

import logging
import uuid
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from ..config import get_config_dir
from ..pipeline.rule_replacer import RuleReplacer, TermRule

logger = logging.getLogger(__name__)

rule_router = APIRouter(prefix="/api/rules", tags=["rules"])

RULES_FILE = get_config_dir() / "rules.json"
_rule_replacer: Optional[RuleReplacer] = None


def get_rule_replacer() -> RuleReplacer:
    """Get or create global RuleReplacer instance."""
    global _rule_replacer
    if _rule_replacer is None:
        _rule_replacer = RuleReplacer(rules_file=RULES_FILE)
    return _rule_replacer


class RuleCreate(BaseModel):
    """Request model for creating a rule."""
    wrong: str = Field(..., min_length=1, description="错误发音")
    correct: str = Field(..., min_length=1, description="正确写法")
    category: str = Field(default="general", description="分类")
    case_sensitive: bool = Field(default=False, description="区分大小写")
    whole_word: bool = Field(default=False, description="全词匹配")


class RuleUpdate(BaseModel):
    """Request model for updating a rule."""
    wrong: Optional[str] = None
    correct: Optional[str] = None
    category: Optional[str] = None
    enabled: Optional[bool] = None
    case_sensitive: Optional[bool] = None
    whole_word: Optional[bool] = None


class RuleResponse(BaseModel):
    """Response model for a single rule."""
    id: str
    wrong: str
    correct: str
    category: str
    enabled: bool
    case_sensitive: bool
    whole_word: bool


class RulesListResponse(BaseModel):
    """Response model for list of rules."""
    total: int
    rules: List[RuleResponse]


class ImportRequest(BaseModel):
    """Request model for importing rules."""
    rules: List[dict]
    merge: bool = Field(default=True, description="是否合并（否则替换）")


@rule_router.get("", response_model=RulesListResponse)
async def list_rules(category: Optional[str] = None, enabled_only: bool = False):
    """
    Get all rules.
    获取所有规则。
    """
    replacer = get_rule_replacer()
    rules = replacer.list_rules(category=category, enabled_only=enabled_only)
    
    return RulesListResponse(
        total=len(rules),
        rules=[RuleResponse(**rule.to_dict()) for rule in rules]
    )


@rule_router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: str):
    """
    Get a single rule by ID.
    根据 ID 获取单个规则。
    """
    replacer = get_rule_replacer()
    rule = replacer.get_rule(rule_id)
    
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    
    return RuleResponse(**rule.to_dict())


@rule_router.post("", response_model=RuleResponse)
async def create_rule(req: RuleCreate):
    """
    Create a new rule.
    创建新规则。
    """
    replacer = get_rule_replacer()
    
    rule_id = f"user_{uuid.uuid4().hex[:8]}"
    rule = TermRule(
        rule_id=rule_id,
        wrong=req.wrong,
        correct=req.correct,
        category=req.category,
        enabled=True,
        case_sensitive=req.case_sensitive,
        whole_word=req.whole_word,
    )
    
    replacer.add_rule(rule)
    logger.info(f"Created rule: {rule_id} ({req.wrong} → {req.correct})")
    
    return RuleResponse(**rule.to_dict())


@rule_router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: str, req: RuleUpdate):
    """
    Update an existing rule.
    更新已有规则。
    """
    replacer = get_rule_replacer()
    rule = replacer.get_rule(rule_id)
    
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    
    if req.wrong is not None:
        rule.wrong = req.wrong
    if req.correct is not None:
        rule.correct = req.correct
    if req.category is not None:
        rule.category = req.category
    if req.enabled is not None:
        rule.enabled = req.enabled
    if req.case_sensitive is not None:
        rule.case_sensitive = req.case_sensitive
    if req.whole_word is not None:
        rule.whole_word = req.whole_word
    
    replacer.add_rule(rule)
    logger.info(f"Updated rule: {rule_id}")
    
    return RuleResponse(**rule.to_dict())


@rule_router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    """
    Delete a rule.
    删除规则。
    """
    replacer = get_rule_replacer()
    
    if not replacer.remove_rule(rule_id):
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    
    logger.info(f"Deleted rule: {rule_id}")
    return {"success": True}


@rule_router.post("/import")
async def import_rules(req: ImportRequest):
    """
    Import rules from JSON.
    从 JSON 导入规则。
    """
    replacer = get_rule_replacer()
    count = replacer.import_rules(req.rules, merge=req.merge)
    
    return {
        "success": True,
        "imported": count,
        "message": f"Successfully imported {count} rules"
    }


@rule_router.get("/export/json")
async def export_rules_json(category: Optional[str] = None):
    """
    Export rules as JSON.
    导出规则为 JSON。
    """
    replacer = get_rule_replacer()
    rules = replacer.export_rules(category=category)
    
    return {
        "rules": rules,
        "total": len(rules)
    }


@rule_router.get("/categories")
async def list_categories():
    """
    Get all rule categories.
    获取所有规则分类。
    """
    replacer = get_rule_replacer()
    categories = set()
    
    for rule in replacer.list_rules():
        categories.add(rule.category)
    
    return {
        "categories": sorted(list(categories))
    }


@rule_router.post("/test")
async def test_rules(text: str):
    """
    Test rule replacement on sample text.
    测试规则替换效果。
    """
    replacer = get_rule_replacer()
    result = replacer.apply(text, add_lock_tags=True)
    
    return {
        "input": text,
        "output": result,
        "changed": result != text
    }
