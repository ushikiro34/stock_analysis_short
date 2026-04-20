"""
Morning Briefing API Router
장전 브리핑 (DART 공시 + 뉴스 LLM + 테마 스캔)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...db.session import get_db

router = APIRouter(prefix="/briefing", tags=["🌅 Morning Briefing"])


class GenerateRequest(BaseModel):
    date: str = ""        # YYYY-MM-DD, 빈 값이면 오늘
    force: bool = False   # True이면 기존 데이터 덮어쓰기


@router.get("/today")
async def get_today_briefing(db: AsyncSession = Depends(get_db)):
    """오늘 장전 브리핑 조회"""
    try:
        from zoneinfo import ZoneInfo
        KST = ZoneInfo("Asia/Seoul")
    except ImportError:
        import pytz
        KST = pytz.timezone("Asia/Seoul")
    from datetime import datetime
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    return await _get_briefing_by_date(today_str, db)


@router.get("/history")
async def get_briefing_history(limit: int = 30, db: AsyncSession = Depends(get_db)):
    """브리핑 이력 목록 (최신순)"""
    from ...db.models import MorningBriefing
    rows = (await db.execute(
        select(MorningBriefing).order_by(MorningBriefing.briefing_date.desc()).limit(limit)
    )).scalars().all()
    from ...core.morning_briefing import _row_to_dict
    return [
        {
            "briefing_date":    r.briefing_date,
            "total_candidates": r.total_candidates,
            "dart_count":       r.dart_count,
            "ai_summary":       (r.ai_summary or "")[:120],
            "generated_at":     (r.generated_at.isoformat() + "Z") if r.generated_at else None,
        }
        for r in rows
    ]


@router.get("/themes")
async def get_themes():
    """테마-종목 맵 조회"""
    from ...core.theme_map import THEME_MAP
    return THEME_MAP


@router.get("/{briefing_date}")
async def get_briefing_by_date(briefing_date: str, db: AsyncSession = Depends(get_db)):
    """특정 날짜 브리핑 조회 (YYYY-MM-DD)"""
    return await _get_briefing_by_date(briefing_date, db)


@router.post("/generate")
async def generate_briefing(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """브리핑 수동 생성 (force=true이면 기존 데이터 덮어쓰기)"""
    try:
        from zoneinfo import ZoneInfo
        KST = ZoneInfo("Asia/Seoul")
    except ImportError:
        import pytz
        KST = pytz.timezone("Asia/Seoul")
    from datetime import datetime
    from ...core.morning_briefing import generate_morning_briefing, regenerate_morning_briefing

    date_str = req.date or datetime.now(KST).strftime("%Y-%m-%d")
    if req.force:
        result = await regenerate_morning_briefing(date_str, db)
    else:
        result = await generate_morning_briefing(date_str, db)

    if result is None:
        raise HTTPException(status_code=500, detail="브리핑 생성 실패")
    return result


async def _get_briefing_by_date(date_str: str, db: AsyncSession):
    from ...db.models import MorningBriefing
    from ...core.morning_briefing import _row_to_dict
    row = (await db.execute(
        select(MorningBriefing).where(MorningBriefing.briefing_date == date_str)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"{date_str} 브리핑 없음")
    return _row_to_dict(row)
