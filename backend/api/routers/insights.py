"""
Trading Insights API Router
거래 패턴 학습 분석 결과 제공
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db

router = APIRouter(prefix="/insights", tags=["🧠 Insights"])


@router.get("/trade-analysis")
async def get_trade_analysis(
    source: str = Query(default="all", description="live | paper | all"),
    db: AsyncSession = Depends(get_db),
):
    """
    청산 거래 통계 분석
    - 진입 점수 구간별 승률/평균 수익률
    - 급등전 vs 일반 비교
    - 청산 사유별 분포
    - 시간대별 성과
    - 보유 시간별 성과
    - 파라미터 제안
    - AI 내러티브
    """
    if source not in ("live", "paper", "all"):
        raise HTTPException(status_code=400, detail="source must be 'live', 'paper', or 'all'")
    from ...core.trade_learner import analyze_trades
    return await analyze_trades(db, source=source)


@router.post("/apply-recommendation")
async def apply_recommendation(
    param: str,
    value: float | bool | None = None,
    target: str = Query(default="paper", description="live | paper"),
    db: AsyncSession = Depends(get_db),
):
    """
    파라미터 제안 적용 (live 또는 paper 엔진에 즉시 반영)
    """
    if target == "live":
        from ...core.live_engine import live_engine
        if param == "min_score" and value is not None:
            live_engine.config["min_score"] = float(value)
        elif param == "pre_surge_mode" and value is not None:
            live_engine.config["pre_surge_mode"] = bool(value)
        else:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 파라미터: {param}")
        return {"status": "applied", "target": "live", "param": param, "value": value}

    elif target == "paper":
        from ...core.paper_engine import paper_engine
        if param == "min_score" and value is not None:
            paper_engine.config["min_score"] = float(value)
            # DB 동기화
            from sqlalchemy import update
            from ...db.models import PaperAccount
            await db.execute(
                update(PaperAccount).where(PaperAccount.id == 1).values(min_score=float(value))
            )
            await db.commit()
        elif param == "pre_surge_mode":
            # PaperEngine에는 pre_surge_mode 필드 없으므로 config에만 반영
            paper_engine.config["pre_surge_mode"] = bool(value)
        else:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 파라미터: {param}")
        return {"status": "applied", "target": "paper", "param": param, "value": value}

    raise HTTPException(status_code=400, detail="target must be 'live' or 'paper'")
