"""
Signal generation service for trading strategies.
주식 데이터를 가져와서 진입/청산 신호를 생성하는 서비스
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from pykrx import stock as pykrx_stock

from .signals import SignalManager

logger = logging.getLogger(__name__)


async def _run_sync(fn):
    """Run blocking function in thread executor"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn)


async def collect_ohlcv_data(code: str, market: str = "KR", days: int = 120) -> pd.DataFrame:
    """
    OHLCV 데이터 수집

    Args:
        code: 종목 코드
        market: "KR" | "US"
        days: 조회 기간

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    if market == "US":
        from ..us.yfinance_client import _run_sync as us_run_sync
        import yfinance as yf

        def _fetch():
            ticker = yf.Ticker(code)
            df = ticker.history(period=f"{days}d", interval="1d")
            if df.empty:
                return pd.DataFrame()

            # 컬럼명 통일
            df = df.rename(columns={
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Volume": "Volume"
            })
            return df[["Open", "High", "Low", "Close", "Volume"]]

        return await us_run_sync(_fetch)

    # KR
    end = datetime.now()
    start = end - timedelta(days=days)

    try:
        df = await _run_sync(
            lambda: pykrx_stock.get_market_ohlcv_by_date(
                start.strftime("%Y%m%d"),
                end.strftime("%Y%m%d"),
                code
            )
        )

        if df.empty:
            return pd.DataFrame()

        # 컬럼명 통일
        df = df.rename(columns={
            "시가": "Open",
            "고가": "High",
            "저가": "Low",
            "종가": "Close",
            "거래량": "Volume"
        })

        return df[["Open", "High", "Low", "Close", "Volume"]]

    except Exception as e:
        logger.error(f"[{code}] OHLCV collection error: {e}")
        return pd.DataFrame()


async def generate_entry_signal(code: str, market: str = "KR", strategy: str = "combined") -> Dict:
    """
    진입 신호 생성

    Args:
        code: 종목 코드
        market: "KR" | "US"
        strategy: "volume" | "technical" | "pattern" | "combined"

    Returns:
        {
            "code": 종목 코드,
            "signal": "BUY" | "HOLD",
            "strength": "high" | "medium" | "low",
            "score": 0-100,
            "reasons": [...],
            "timestamp": 생성 시각
        }
    """
    # OHLCV 데이터 수집
    ohlcv_data = await collect_ohlcv_data(code, market, days=120)

    if ohlcv_data.empty or len(ohlcv_data) < 20:
        logger.warning(f"[{code}] Insufficient data for signal generation")
        return {
            "code": code,
            "signal": "HOLD",
            "strength": "low",
            "score": 0,
            "reasons": ["데이터 부족"],
            "timestamp": datetime.now().isoformat(),
            "error": "insufficient_data"
        }

    # 신호 생성
    signal_manager = SignalManager()
    result = signal_manager.generate_entry_signal(ohlcv_data, strategy)

    return {
        "code": code,
        "market": market,
        "signal": result["signal"],
        "strength": result["strength"],
        "score": result["score"],
        "reasons": result["reasons"],
        "timestamp": datetime.now().isoformat(),
        "current_price": float(ohlcv_data["Close"].iloc[-1]),
        "breakdown": result.get("breakdown", {})
    }


async def generate_entry_signals_bulk(codes: List[str], market: str = "KR",
                                      strategy: str = "combined",
                                      min_score: float = 50) -> List[Dict]:
    """
    여러 종목의 진입 신호 생성 (필터링)

    Args:
        codes: 종목 코드 리스트
        market: "KR" | "US"
        strategy: 신호 전략
        min_score: 최소 점수 (이 이상만 반환)

    Returns:
        진입 신호 리스트 (점수 높은 순)
    """
    results = []

    for code in codes:
        try:
            signal = await generate_entry_signal(code, market, strategy)

            # 필터링: BUY 신호이고 최소 점수 이상
            if signal["signal"] == "BUY" and signal["score"] >= min_score:
                results.append(signal)

            # Rate limit 고려
            await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"[{code}] Signal generation failed: {e}")

    # 점수 높은 순 정렬
    results.sort(key=lambda x: x["score"], reverse=True)

    return results


async def generate_exit_signal(code: str, entry_price: float, entry_time: datetime,
                               market: str = "KR") -> Dict:
    """
    청산 신호 생성

    Args:
        code: 종목 코드
        entry_price: 진입 가격
        entry_time: 진입 시각
        market: "KR" | "US"

    Returns:
        {
            "code": 종목 코드,
            "should_exit": True/False,
            "exit_type": "take_profit" | "stop_loss" | "time_based",
            "volume_pct": 매도 비율,
            "reason": 청산 사유,
            "current_price": 현재 가격,
            "profit_loss": 손익,
            "profit_loss_pct": 손익률,
            "timestamp": 생성 시각
        }
    """
    # 현재 가격 조회
    ohlcv_data = await collect_ohlcv_data(code, market, days=5)

    if ohlcv_data.empty:
        logger.warning(f"[{code}] Cannot get current price for exit signal")
        return {
            "code": code,
            "should_exit": False,
            "error": "no_price_data"
        }

    current_price = float(ohlcv_data["Close"].iloc[-1])
    current_time = datetime.now()

    # 청산 신호 생성
    signal_manager = SignalManager()
    result = signal_manager.generate_exit_signal(
        entry_price=entry_price,
        entry_time=entry_time,
        current_price=current_price,
        current_time=current_time,
        position_size=1.0
    )

    # 손익 계산
    profit_loss = current_price - entry_price
    profit_loss_pct = (profit_loss / entry_price) * 100 if entry_price > 0 else 0

    return {
        "code": code,
        "market": market,
        "should_exit": result["should_exit"],
        "exit_type": result["exit_type"],
        "volume_pct": result["volume_pct"],
        "reason": result["reason"],
        "current_price": current_price,
        "entry_price": entry_price,
        "profit_loss": profit_loss,
        "profit_loss_pct": profit_loss_pct,
        "holding_time": (current_time - entry_time).total_seconds() / 60,  # 분
        "timestamp": current_time.isoformat(),
        "details": result.get("details", {})
    }


async def scan_signals_from_surge_stocks(market: str = "KR", strategy: str = "combined",
                                        min_score: float = 60) -> List[Dict]:
    """
    급등주에서 진입 신호 스캔

    Args:
        market: "KR" | "US"
        strategy: 신호 전략
        min_score: 최소 점수

    Returns:
        진입 신호 리스트
    """
    # 급등주 조회
    if market == "US":
        from ..us.yfinance_client import get_us_surge_stocks
        surge_stocks = await get_us_surge_stocks(limit=30)
    else:
        from ..kis.rest_client import KISRestClient
        kis_client = KISRestClient()
        surge_stocks = await kis_client.get_volume_rank(max_price=20000, limit=30)

    codes = [stock["code"] for stock in surge_stocks]

    # 진입 신호 생성
    signals = await generate_entry_signals_bulk(codes, market, strategy, min_score)

    # 급등주 정보와 결합
    surge_dict = {s["code"]: s for s in surge_stocks}

    for signal in signals:
        code = signal["code"]
        if code in surge_dict:
            signal["stock_info"] = surge_dict[code]

    return signals


# ═══════════════════════════════════════════════════════════════
# 신호 캐시 관리
# ═══════════════════════════════════════════════════════════════

_signal_cache: Dict[str, Dict] = {}
_SIGNAL_TTL = 300  # 5분


def get_cached_signal(code: str, market: str) -> Optional[Dict]:
    """캐시된 신호 조회"""
    import time
    cache_key = f"{market}:{code}"
    cached = _signal_cache.get(cache_key)

    if cached and time.time() - cached["ts"] < _SIGNAL_TTL:
        return cached["data"]

    return None


def cache_signal(code: str, market: str, signal_data: Dict):
    """신호 캐싱"""
    import time
    cache_key = f"{market}:{code}"
    _signal_cache[cache_key] = {
        "data": signal_data,
        "ts": time.time()
    }
