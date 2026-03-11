"""
Paper Trading API Router
가상 자동매매 시뮬레이션 제어 및 조회
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...core.paper_engine import paper_engine
from ...db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/paper", tags=["📄 Paper Trading"])


class StartConfig(BaseModel):
    initial_capital: float = 10_000_000.0
    market: str = "KR"
    strategy: str = "combined"
    min_score: float = 65.0
    max_positions: int = 2
    position_size_pct: float = 0.15


class AddPositionRequest(BaseModel):
    code: str
    name: str = ""
    entry_price: float
    quantity: int = 0   # 0 = config 기준 자동 계산


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


@router.post("/positions")
async def add_position(req: AddPositionRequest, db: AsyncSession = Depends(get_db)):
    """수동 포지션 추가 (quantity=0이면 자동 계산)"""
    try:
        result = await paper_engine.open_position_manually(
            req.code, req.name, req.entry_price, req.quantity, db
        )
        return {"status": "opened", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {type(e).__name__}: {e}")


@router.get("/positions")
async def get_positions():
    """현재 보유 포지션 조회"""
    return paper_engine.get_positions()


@router.post("/positions/close-all")
async def close_all_positions(db: AsyncSession = Depends(get_db)):
    """전체 포지션 일괄 청산"""
    results = await paper_engine.close_all_positions(db)
    return {"status": "closed_all", "closed": len(results), "positions": results}


@router.post("/positions/{code}/close")
async def close_position(code: str, db: AsyncSession = Depends(get_db)):
    """특정 포지션 수동 강제 청산"""
    result = await paper_engine.close_position_manually(code, db)
    if result is None:
        raise HTTPException(status_code=404, detail=f"포지션 없음: {code}")
    return {"status": "closed", **result}


@router.get("/trades")
async def get_trades(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """체결 거래 내역 조회 (최신 N건)"""
    return await paper_engine.get_trades(db, limit)


@router.get("/history")
async def get_history(limit: int = 200, db: AsyncSession = Depends(get_db)):
    """포트폴리오 가치 변화 이력"""
    return await paper_engine.get_history(db, limit)


@router.get("/journal")
async def get_journal(
    date_from: Optional[str] = Query(None, description="시작 날짜 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="종료 날짜 YYYY-MM-DD"),
    code: Optional[str] = Query(None, description="종목코드/종목명 검색"),
    profit_type: str = Query("all", description="all | profit | loss"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """투자일지 조회 (날짜·종목·수익여부 필터)"""
    return await paper_engine.get_journal(
        db, date_from, date_to, code, profit_type, limit, offset
    )
