"""
Monitor API Router
서버 상태 및 실시간 로그 조회
"""
import time
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitor", tags=["🔍 Monitor"])

_start_time = time.time()


@router.get("/status")
async def get_status():
    """
    서버 상태 조회
    - uptime, background task 상태
    """
    from ..main import collector_task, scorer_task, paper_task

    def task_status(task):
        if task is None:
            return "not_started"
        if task.done():
            exc = task.exception() if not task.cancelled() else None
            return f"failed: {exc}" if exc else "stopped"
        return "running"

    return {
        "uptime_seconds": int(time.time() - _start_time),
        "tasks": {
            "collector": task_status(collector_task),
            "scorer":    task_status(scorer_task),
            "paper":     task_status(paper_task),
        },
    }


@router.get("/logs")
async def get_logs(level: str = "DEBUG", limit: int = 200):
    """
    최근 서버 로그 조회

    Args:
        level: 최소 로그 레벨 (DEBUG | INFO | WARNING | ERROR)
        limit: 최대 반환 건수
    """
    from ...core.log_buffer import get_log_handler
    return get_log_handler().get_logs(min_level=level, limit=limit)


@router.delete("/logs")
async def clear_logs():
    """로그 버퍼 초기화"""
    from ...core.log_buffer import get_log_handler
    get_log_handler().clear()
    return {"cleared": True}
