#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
API routes for custom scene management.
自定义场景管理 API。
"""

import logging
import uuid
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import get_config_dir
from ..platform.scene_manager import SceneManager, CustomScene

logger = logging.getLogger(__name__)

scene_router = APIRouter(prefix="/api/scenes", tags=["scenes"])

SCENES_FILE = get_config_dir() / "scenes.json"
_scene_manager: Optional[SceneManager] = None
_engine = None


def set_scene_engine(engine):
    """Set engine instance for scene switching."""
    global _engine
    _engine = engine


def get_scene_manager() -> SceneManager:
    """Get or create global SceneManager instance."""
    global _scene_manager
    if _scene_manager is None:
        _scene_manager = SceneManager(scenes_file=SCENES_FILE)
    return _scene_manager


class SceneCreate(BaseModel):
    """Request model for creating a scene."""
    name: str = Field(..., min_length=1, description="场景名称")
    prompt: str = Field(..., min_length=10, description="提示词模板")
    icon: str = Field(default="💬", description="图标")
    hotkey: str = Field(default="", description="快捷键")
    app_rules: List[str] = Field(default_factory=list, description="应用绑定规则")


class SceneUpdate(BaseModel):
    """Request model for updating a scene."""
    name: Optional[str] = None
    prompt: Optional[str] = None
    icon: Optional[str] = None
    hotkey: Optional[str] = None
    app_rules: Optional[List[str]] = None
    enabled: Optional[bool] = None


class SceneResponse(BaseModel):
    """Response model for a single scene."""
    id: str
    name: str
    prompt: str
    icon: str
    hotkey: str
    app_rules: List[str]
    enabled: bool
    builtin: bool


class ScenesListResponse(BaseModel):
    """Response model for list of scenes."""
    total: int
    scenes: List[SceneResponse]


class ImportRequest(BaseModel):
    """Request model for importing scenes."""
    scenes: List[dict]
    merge: bool = Field(default=True, description="是否合并（否则替换）")


@scene_router.get("", response_model=ScenesListResponse)
async def list_scenes(enabled_only: bool = False):
    """
    Get all scenes.
    获取所有场景。
    """
    manager = get_scene_manager()
    scenes = manager.list_scenes(enabled_only=enabled_only)
    
    return ScenesListResponse(
        total=len(scenes),
        scenes=[SceneResponse(**scene.to_dict()) for scene in scenes]
    )


@scene_router.get("/{scene_id}", response_model=SceneResponse)
async def get_scene(scene_id: str):
    """
    Get a single scene by ID.
    根据 ID 获取单个场景。
    """
    manager = get_scene_manager()
    scene = manager.get_scene(scene_id)
    
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    
    return SceneResponse(**scene.to_dict())


@scene_router.post("", response_model=SceneResponse)
async def create_scene(req: SceneCreate):
    """
    Create a new custom scene.
    创建新场景。
    """
    manager = get_scene_manager()
    
    scene_id = f"custom_{uuid.uuid4().hex[:8]}"
    scene = CustomScene(
        id=scene_id,
        name=req.name,
        prompt=req.prompt,
        icon=req.icon,
        hotkey=req.hotkey,
        app_rules=req.app_rules,
        enabled=True,
        builtin=False,
    )
    
    try:
        manager.add_scene(scene)
        logger.info(f"Created scene: {scene_id} ({req.name})")
        return SceneResponse(**scene.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@scene_router.put("/{scene_id}", response_model=SceneResponse)
async def update_scene(scene_id: str, req: SceneUpdate):
    """
    Update an existing scene.
    更新场景。
    """
    manager = get_scene_manager()
    scene = manager.get_scene(scene_id)
    
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    
    if req.name is not None:
        scene.name = req.name
    if req.prompt is not None:
        scene.prompt = req.prompt
    if req.icon is not None:
        scene.icon = req.icon
    if req.hotkey is not None:
        scene.hotkey = req.hotkey
    if req.app_rules is not None:
        scene.app_rules = req.app_rules
    if req.enabled is not None:
        scene.enabled = req.enabled
    
    try:
        manager.add_scene(scene)
        logger.info(f"Updated scene: {scene_id}")
        return SceneResponse(**scene.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@scene_router.delete("/{scene_id}")
async def delete_scene(scene_id: str):
    """
    Delete a custom scene.
    删除场景（内置场景不可删除）。
    """
    manager = get_scene_manager()
    
    try:
        if not manager.remove_scene(scene_id):
            raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
        
        logger.info(f"Deleted scene: {scene_id}")
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@scene_router.post("/switch/{scene_id}")
async def switch_scene(scene_id: str, manual: bool = True):
    """
    Switch to a scene.
    切换场景。
    
    Args:
        scene_id: Scene ID to switch to
        manual: If True, user manually switched (disable auto-detection until cleared)
    """
    manager = get_scene_manager()
    
    try:
        pipeline_scene = manager.switch_scene(scene_id, manual=manual)
        
        # Update engine pipeline
        if _engine:
            _engine.pipeline.set_scene(pipeline_scene)
            _engine.pipeline.set_custom_prompt(manager.get_scene(scene_id).prompt)
        
        return {
            "success": True,
            "scene": scene_id,
            "manual": manual
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@scene_router.post("/clear-override")
async def clear_scene_override():
    """
    Clear manual scene override, back to auto-detection.
    清除手动场景覆盖，回到自动检测。
    """
    manager = get_scene_manager()
    manager.clear_manual_override()
    
    # Trigger auto-detection with current window
    if _engine:
        window = _engine.window_watcher.current
        if window:
            detected_scene = manager.auto_detect_scene(window.app_name)
            if detected_scene:
                _engine.pipeline.set_scene(detected_scene)
    
    return {"success": True}


@scene_router.get("/active")
async def get_active_scene():
    """
    Get currently active scene.
    获取当前活动场景。
    """
    manager = get_scene_manager()
    scene = manager.get_active_scene()
    
    if not scene:
        raise HTTPException(status_code=404, detail="No active scene")
    
    return SceneResponse(**scene.to_dict())


@scene_router.post("/import")
async def import_scenes(req: ImportRequest):
    """
    Import scenes from JSON.
    从 JSON 导入场景。
    """
    manager = get_scene_manager()
    count = manager.import_scenes(req.scenes, merge=req.merge)
    
    return {
        "success": True,
        "imported": count,
        "message": f"Successfully imported {count} scenes"
    }


@scene_router.get("/export/json")
async def export_scenes_json(include_builtin: bool = False):
    """
    Export scenes as JSON.
    导出场景为 JSON。
    """
    manager = get_scene_manager()
    scenes = manager.export_scenes(include_builtin=include_builtin)
    
    return {
        "scenes": scenes,
        "total": len(scenes)
    }


@scene_router.post("/validate-hotkey")
async def validate_hotkey(hotkey: str, scene_id: str = ""):
    """
    Validate hotkey for conflicts.
    验证快捷键冲突。
    """
    manager = get_scene_manager()
    
    for scene in manager.list_scenes():
        if scene.id != scene_id and scene.hotkey == hotkey:
            return {
                "valid": False,
                "conflict": scene.name,
                "message": f"快捷键冲突：{scene.name} 已使用 {hotkey}"
            }
    
    return {
        "valid": True,
        "message": "快捷键可用"
    }
