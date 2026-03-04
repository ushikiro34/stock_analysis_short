"""
Paper Trading API Router
가상 자동매매 시뮬레이션 제어 및 조회
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ...core.paper_engine import paper_engine
from ...db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/paper", tags=["📄 Paper Trading"])


class StartConfig(BaseModel):
    initial_capital: float = 10_000_000.0
    market: str = "KR"
    strategy: str = "combined"
    min_score: float = 65.0
    max_positions: int = 3
    position_size_pct: float = 0.3


@router.post("/start")
async def start_paper_trading(config: StartConfig, db: AsyncSession = Depends(get_db)):
    """페이퍼 트레이딩 시작"""
    if paper_engine.is_running:
        raise HTTPException(status_code=400, detail="이미 실행 중입니다")
    await paper_engine.start(config.model_dump(), db)
    return {"status": "started", **paper_engine.get_status()}


@router.post("/stop")
async def stop_paper_trading(db: AsyncSession = Depends(get_db)):
    """페이퍼 트레이딩 중지"""
    await paper_engine.stop(db)
    return {"status": "stopped", **paper_engine.get_status()}


@router.post("/reset")
async def reset_paper_trading(db: AsyncSession = Depends(get_db)):
    """전체 초기화 (포지션·거래내역·이력 삭제, 자본 리셋)"""
    await paper_engine.reset(db)
    return {"status": "reset", **paper_engine.get_status()}


@router.get("/status")
async def get_status():
    """계좌 현황 조회"""
    return paper_engine.get_status()


@router.get("/positions")
async def get_positions():
    """현재 보유 포지션 조회"""
    return paper_engine.get_positions()


@router.get("/trades")
async def get_trades(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """체결 거래 내역 조회 (최신 N건)"""
    return await paper_engine.get_trades(db, limit)


@router.get("/history")
async def get_history(limit: int = 200, db: AsyncSession = Depends(get_db)):
    """포트폴리오 가치 변화 이력"""
    return await paper_engine.get_history(db, limit)
