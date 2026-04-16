"""
Live Trading API Router
KIS 실전 자동매매 제어 및 조회

⚠️ 실제 자금이 사용됩니다. LIVE_TRADING_ENABLED=true 환경변수 필요.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...core.live_engine import live_engine
from ...db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/live", tags=["🔴 Live Trading"])


class LiveStartConfig(BaseModel):
    market: str = "KR"
    strategy: str = "combined"
    min_score: float = 65.0
    max_positions: int = 2
    position_size_pct: float = 0.15
    pre_surge_mode: bool = False


@router.post("/start")
async def start_live_trading(config: LiveStartConfig, db: AsyncSession = Depends(get_db)):
    """실전 매매 시작 (LIVE_TRADING_ENABLED=true 필요)"""
    if live_engine.is_running:
        raise HTTPException(status_code=400, detail="이미 실행 중입니다")
    try:
        await live_engine.start(config.model_dump(), db)
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"status": "started", **live_engine.get_status()}


@router.post("/stop")
async def stop_live_trading(db: AsyncSession = Depends(get_db)):
    """실전 매매 중지"""
    try:
        await live_engine.stop(db)
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"status": "stopped", **live_engine.get_status()}


@router.get("/status")
async def get_live_status():
    """실전 매매 현황 조회"""
    return live_engine.get_status()


@router.get("/balance")
async def get_live_balance():
    """KIS 실시간 잔고 조회"""
    try:
        from ...kis.rest_client import get_kis_order_client
        bal = await get_kis_order_client().get_balance()
        return bal
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"잔고 조회 실패: {e}")


@router.get("/positions")
async def get_live_positions():
    """현재 보유 포지션 조회"""
    return live_engine.get_positions()


@router.post("/positions/close-all")
async def close_all_live_positions(db: AsyncSession = Depends(get_db)):
    """전체 포지션 긴급 청산"""
    try:
        results = await live_engine.close_all_positions(db)
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"status": "closed_all", "closed": len(results), "positions": results}


@router.get("/trades")
async def get_live_trades(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """체결 거래 내역 조회"""
    return await live_engine.get_trades(db, limit)


@router.get("/history")
async def get_live_history(limit: int = 200, db: AsyncSession = Depends(get_db)):
    """포트폴리오 가치 변화 이력"""
    return await live_engine.get_history(db, limit)


# ── Daily Reports ──────────────────────────────────────────────

@router.get("/daily-reports")
async def get_daily_reports(limit: int = 30, db: AsyncSession = Depends(get_db)):
    """일별 트레이딩 분석 리포트 목록 (최신순)"""
    from sqlalchemy import select
    from ...db.models import LiveDailyReport
    rows = (await db.execute(
        select(LiveDailyReport).order_by(LiveDailyReport.report_date.desc()).limit(limit)
    )).scalars().all()
    from ...core.live_daily_report import _row_to_dict
    return [_row_to_dict(r) for r in rows]


@router.get("/daily-reports/{report_date}")
async def get_daily_report(report_date: str, db: AsyncSession = Depends(get_db)):
    """특정 날짜 리포트 조회 (YYYY-MM-DD)"""
    from sqlalchemy import select
    from ...db.models import LiveDailyReport
    from ...core.live_daily_report import _row_to_dict
    row = (await db.execute(
        select(LiveDailyReport).where(LiveDailyReport.report_date == report_date)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"{report_date} 리포트 없음")
    return _row_to_dict(row)


@router.post("/daily-reports/generate")
async def generate_report(report_date: str = "", db: AsyncSession = Depends(get_db)):
    """수동으로 리포트 생성 (report_date 미입력 시 오늘 날짜)"""
    from ...core.live_daily_report import generate_daily_report
    try:
        from zoneinfo import ZoneInfo
        KST = ZoneInfo("Asia/Seoul")
    except ImportError:
        import pytz
        KST = pytz.timezone("Asia/Seoul")
    from datetime import datetime
    if not report_date:
        report_date = datetime.now(KST).strftime("%Y-%m-%d")
    result = await generate_daily_report(report_date, db)
    if result is None:
        raise HTTPException(status_code=404, detail=f"{report_date} 청산 거래 없음")
    return result
