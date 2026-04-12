#!/usr/bin/env python3
# Copyright (C) 2026 VoiceForge Contributors
# Licensed under AGPL-3.0

"""
Error handling with retry and fallback mechanisms.
错误处理（重试、降级）。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """重试策略"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_backoff: bool = True
    jitter: bool = True


@dataclass
class FallbackConfig:
    """降级配置"""
    enabled: bool = True
    fallback_func: Optional[Callable] = None
    default_value: Any = None


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self, retry_policy: Optional[RetryPolicy] = None):
        self.retry_policy = retry_policy or RetryPolicy()
        self._error_count = 0
        self._success_count = 0
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        retry_policy: Optional[RetryPolicy] = None,
        **kwargs
    ) -> Any:
        """执行函数并在失败时重试"""
        policy = retry_policy or self.retry_policy
        last_exception = None
        
        for attempt in range(1, policy.max_attempts + 1):
            try:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
                
                self._success_count += 1
                return result
            
            except Exception as e:
                last_exception = e
                self._error_count += 1
                
                if attempt < policy.max_attempts:
                    delay = self._calculate_delay(attempt, policy)
                    logger.warning(
                        f"执行失败 (尝试 {attempt}/{policy.max_attempts}): {e}, "
                        f"将在 {delay:.2f}s 后重试"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"执行失败，已达最大重试次数 ({policy.max_attempts}): {e}"
                    )
        
        raise last_exception
    
    def _calculate_delay(self, attempt: int, policy: RetryPolicy) -> float:
        """计算重试延迟"""
        if policy.exponential_backoff:
            delay = min(policy.base_delay * (2 ** (attempt - 1)), policy.max_delay)
        else:
            delay = policy.base_delay
        
        if policy.jitter:
            import random
            delay = delay * (0.5 + random.random())
        
        return delay
    
    async def execute_with_fallback(
        self,
        func: Callable,
        *args,
        fallback_config: Optional[FallbackConfig] = None,
        **kwargs
    ) -> Any:
        """执行函数并在失败时降级"""
        try:
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            
            self._success_count += 1
            return result
        
        except Exception as e:
            self._error_count += 1
            logger.error(f"执行失败，尝试降级: {e}")
            
            if fallback_config and fallback_config.enabled:
                if fallback_config.fallback_func:
                    try:
                        result = fallback_config.fallback_func(*args, **kwargs)
                        if asyncio.iscoroutine(result):
                            result = await result
                        
                        logger.info("降级成功")
                        return result
                    except Exception as fallback_error:
                        logger.error(f"降级失败: {fallback_error}")
                        return fallback_config.default_value
                else:
                    return fallback_config.default_value
            
            raise
    
    async def execute_with_timeout(
        self,
        func: Callable,
        *args,
        timeout: float = 30.0,
        **kwargs
    ) -> Any:
        """执行函数并设置超时"""
        try:
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await asyncio.wait_for(result, timeout=timeout)
            
            self._success_count += 1
            return result
        
        except asyncio.TimeoutError:
            self._error_count += 1
            logger.error(f"执行超时 ({timeout}s)")
            raise
        except Exception as e:
            self._error_count += 1
            logger.error(f"执行失败: {e}")
            raise
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        total = self._success_count + self._error_count
        success_rate = self._success_count / total if total > 0 else 0.0
        
        return {
            "success_count": self._success_count,
            "error_count": self._error_count,
            "total_count": total,
            "success_rate": success_rate,
        }
