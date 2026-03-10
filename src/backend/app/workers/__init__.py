"""
Background workers - async task queue for long-running operations.

Workers handle: evidence collection, webhook delivery, LLM requests, action execution.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional
import structlog

from .evidence_collector import (
    EvidenceCollectionResult,
    EvidenceCollector,
    NormalizationPipeline,
    DEFAULT_TTL_MINUTES,
    COLLECTION_TIMEOUT_SECONDS,
)

logger = structlog.get_logger(__name__)


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


@dataclass
class Task:
    id: str
    kind: str
    payload: Dict[str, Any]
    status: TaskStatus = TaskStatus.pending
    result: Optional[Any] = None
    error: Optional[str] = None


# In-process task registry (replace with Celery/ARQ in production)
_task_handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}


def register_task(kind: str):
    """Decorator to register an async task handler."""
    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        _task_handlers[kind] = fn
        return fn
    return decorator


async def dispatch(kind: str, payload: Dict[str, Any]) -> str:
    """
    Dispatch a background task.
    In production, this should enqueue to a real task queue (ARQ, Celery, etc.).
    For now, runs in a background asyncio task.
    """
    import uuid
    task_id = str(uuid.uuid4())
    handler = _task_handlers.get(kind)
    if not handler:
        raise ValueError(f"No handler registered for task kind: {kind}")

    async def _run():
        try:
            logger.info("task_started", task_id=task_id, kind=kind)
            await handler(**payload)
            logger.info("task_completed", task_id=task_id, kind=kind)
        except Exception as exc:
            logger.error("task_failed", task_id=task_id, kind=kind, error=str(exc))

    asyncio.create_task(_run())
    return task_id


__all__ = [
    "dispatch",
    "register_task",
    "Task",
    "TaskStatus",
    "EvidenceCollector",
    "EvidenceCollectionResult",
    "NormalizationPipeline",
    "DEFAULT_TTL_MINUTES",
    "COLLECTION_TIMEOUT_SECONDS",
]
