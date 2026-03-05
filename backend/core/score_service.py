"""
Score calculation service.
Collects fundamental + technical data, runs Scorer.
Supports both DB-backed and in-memory (no DB) modes.
"""
import asyncio
import logging
from datetime import datetime, timedelta

import pandas as pd
from pykrx import stock as pykrx_stock

from .scorer import Scorer
from .indicators import IndicatorEngine
from ..kis.rest_client import get_kis_client

logger = logging.getLogger(__name__)


async def _run_sync(fn):
    """Run a blocking function in a thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn)


async def collect_fundamental(code: str, market: str = "KR") -> dict:
    """펀더멘털 데이터 수집 (KR: KIS REST API, US: yfinance)"""
    if market == "US":
        from ..us.yfinance_client import get_us_fundamental
        return await get_us_fundamental(code)

    # KR: KIS REST API 사용 (pykrx의 KRX 통계 API는 인증 정책 변경으로 사용 불가)
    try:
        return await get_kis_client().get_kr_fundamental(code)
    except Exception as e:
        logger.error(f"[{code}] KIS fundamental collection error: {e}")
        return {}


async def collect_technical(code: str, market: str = "KR") -> dict:
    """기술적 지표 수집 (KR: pykrx, US: yfinance)"""
    if market == "US":
        from ..us.yfinance_client import get_us_technical
        return await get_us_technical(code)

    end = datetime.now()
    start = end - timedelta(days=200)  # MA120 계산을 위해 충분한 기간

    try:
        df = await _run_sync(
            lambda: pykrx_stock.get_market_ohlcv_by_date(
                start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), code
            )
        )
        if df.empty or len(df) < 20:
            logger.warning(f"[{code}] Insufficient OHLCV data ({len(df)} rows)")
            return {}

        closes = df["종가"].astype(float)

        # 이동평균
        ma20 = IndicatorEngine.calculate_ma(closes, 20)
        ma60 = IndicatorEngine.calculate_ma(closes, 60)
        ma120 = IndicatorEngine.calculate_ma(closes, 120)

        # RSI
        rsi = IndicatorEngine.calculate_rsi(closes, 14)

        # 변동성 (일간 수익률의 표준편차)
        returns = closes.pct_change().dropna()
        volatility = IndicatorEngine.calculate_volatility(returns, 20)

        # 60일 수익률
        if len(closes) >= 60:
            return_60d = (closes.iloc[-1] / closes.iloc[-60] - 1) * 100
        else:
            return_60d = 0

        latest_ma20 = float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else None
        latest_ma60 = float(ma60.iloc[-1]) if pd.notna(ma60.iloc[-1]) else None
        latest_ma120 = float(ma120.iloc[-1]) if pd.notna(ma120.iloc[-1]) else None
        latest_rsi = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50
        latest_vol = float(volatility.iloc[-1]) if pd.notna(volatility.iloc[-1]) else 0

        return {
            "ma20": latest_ma20,
            "ma60": latest_ma60,
            "ma120": latest_ma120,
            "rsi": latest_rsi,
            "volatility": latest_vol,
            "return_60d": float(return_60d),
        }
    except Exception as e:
        logger.error(f"[{code}] Technical collection error: {e}")
        return {}


# ── In-memory score cache ─────────────────────────────────────
# key: "MARKET:CODE", value: {"result": {...}, "ts": float}
_score_cache: dict = {}
_SCORE_TTL = 600  # 10분


async def calculate_score(code: str, market: str = "KR") -> dict | None:
    """단일 종목 점수 계산 (DB 없이 인메모리)"""
    import time

    cache_key = f"{market}:{code}"
    cached = _score_cache.get(cache_key)
    if cached and time.time() - cached["ts"] < _SCORE_TTL:
        return cached["result"]

    fundamental = await collect_fundamental(code, market)
    technical = await collect_technical(code, market)

    if not fundamental and not technical:
        logger.warning(f"[{code}] No data available for scoring")
        return None

    scorer = Scorer(fundamental, technical)
    value = scorer.calculate_value_score()
    trend = scorer.calculate_trend_score()
    stability = scorer.calculate_stability_score()
    risk = scorer.calculate_risk_penalty()
    total = scorer.calculate_total_score()

    result = {
        "code": code,
        "calculated_at": datetime.now().isoformat(),
        "value_score": value,
        "trend_score": trend,
        "stability_score": stability,
        "risk_penalty": risk,
        "total_score": total,
        "fundamental": fundamental,
        "technical": technical,
    }

    _score_cache[cache_key] = {"result": result, "ts": time.time()}
    logger.info(f"[{code}] Score calculated: total={total} (V{value} T{trend} S{stability} R-{risk})")
    return result


async def calculate_scores_for_codes(codes: list[str], market: str = "KR") -> list[dict]:
    """여러 종목의 점수를 순차적으로 계산 (rate limit 고려)"""
    results = []
    for code in codes:
        try:
            result = await calculate_score(code, market)
            if result:
                results.append(result)
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"[{code}] Score calculation failed: {e}")
    return results
