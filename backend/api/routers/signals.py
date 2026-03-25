"""
Signals API Router
매매 신호 관련 엔드포인트
"""
from fastapi import APIRouter
from datetime import datetime
import time
import logging

from ...core.signal_service import (
    generate_entry_signal,
    generate_exit_signal,
    scan_signals_from_surge_stocks,
    scan_pullback_candidates,
)
from pydantic import BaseModel
from typing import List

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["🚦 Signals"])

# 신호 캐시
_entry_signals_cache: dict = {}


@router.get("/entry/{code}")
async def get_entry_signal(code: str, market: str = "KR", strategy: str = "combined"):
    """
    단일 종목 진입 신호 조회

    Args:
        code: 종목 코드
        market: KR | US
        strategy: volume | technical | pattern | rsi_golden_cross | combined

    Returns:
        {
            "code": 종목 코드,
            "signal": "BUY" | "HOLD",
            "strength": "high" | "medium" | "low",
            "score": 0-100,
            "reasons": [신호 발생 이유],
            "current_price": 현재 가격,
            "timestamp": 생성 시각
        }
    """
    try:
        result = await generate_entry_signal(code, market, strategy)
        return result
    except Exception as e:
        logger.error(f"Entry signal error for {code}: {e}")
        return {
            "code": code,
            "signal": "HOLD",
            "strength": "low",
            "score": 0,
            "reasons": [f"오류: {str(e)}"],
            "error": str(e)
        }


@router.get("/scan")
async def scan_entry_signals(market: str = "KR", strategy: str = "combined", min_score: float = 60):
    """
    급등주에서 진입 신호 스캔

    Args:
        market: KR | US
        strategy: volume | technical | pattern | rsi_golden_cross | combined
        min_score: 최소 점수 (0-100)

    Returns:
        진입 신호 리스트 (점수 높은 순)
    """
    now = time.time()
    cache_key = f"{market}:{strategy}:{min_score}"

    # 3분 캐싱
    if cache_key in _entry_signals_cache and now - _entry_signals_cache[cache_key]["ts"] < 180:
        return _entry_signals_cache[cache_key]["data"]

    try:
        results = await scan_signals_from_surge_stocks(market, strategy, min_score)
        _entry_signals_cache[cache_key] = {"data": results, "ts": now}
        return results
    except Exception as e:
        logger.error(f"Signal scan error: {e}")
        if cache_key in _entry_signals_cache:
            return _entry_signals_cache[cache_key]["data"]
        return []


class PullbackScanRequest(BaseModel):
    codes: List[str]
    market: str = "KR"
    min_score: int = 60


@router.post("/pullback")
async def scan_pullback(req: PullbackScanRequest):
    """
    Track B: 눌림목/반등 스캐너
    관심종목 또는 지정 종목 코드 리스트에서 피보나치+MA20 기반 눌림목 후보 탐색

    Args:
        codes: 종목 코드 리스트
        market: KR | US
        min_score: 최소 점수 (기본 60)

    Returns:
        눌림목 후보 리스트 (score 내림차순)
        [{ code, score, reasons, current_price, fib_levels, adjustment_days }, ...]
    """
    if not req.codes:
        return []
    try:
        return await scan_pullback_candidates(req.codes, req.market, req.min_score)
    except Exception as e:
        logger.error(f"Pullback scan error: {e}")
        return []


@router.post("/exit")
async def get_exit_signal(
    code: str,
    entry_price: float,
    entry_time: str,
    market: str = "KR"
):
    """
    청산 신호 조회

    Args:
        code: 종목 코드
        entry_price: 진입 가격
        entry_time: 진입 시각 (ISO 8601 형식, 예: "2024-01-01T09:30:00")
        market: KR | US

    Returns:
        {
            "code": 종목 코드,
            "should_exit": True/False,
            "exit_type": "take_profit" | "stop_loss" | "time_based",
            "volume_pct": 매도 비율 (0.0-1.0),
            "reason": 청산 사유,
            "current_price": 현재 가격,
            "profit_loss": 손익,
            "profit_loss_pct": 손익률 (%),
            "holding_time": 보유 시간 (분)
        }
    """
    try:
        # ISO 8601 문자열을 datetime으로 변환
        entry_datetime = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))

        result = await generate_exit_signal(code, entry_price, entry_datetime, market)
        return result
    except Exception as e:
        logger.error(f"Exit signal error for {code}: {e}")
        return {
            "code": code,
            "should_exit": False,
            "error": str(e)
        }
