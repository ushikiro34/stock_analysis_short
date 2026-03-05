"""
Stocks API Router
주식 데이터 관련 엔드포인트
"""
from fastapi import APIRouter, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncio
import time
import logging

from ...core.score_service import calculate_score
from ...kis.rest_client import get_kis_client
from pykrx import stock as pykrx_stock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stocks", tags=["📊 Stocks"])


# ── Response Models ──────────────────────────────────────────
class ScoreResponse(BaseModel):
    code: str
    calculated_at: Optional[str] = None
    value_score: Optional[float] = None
    trend_score: Optional[float] = None
    stability_score: Optional[float] = None
    risk_penalty: Optional[float] = None
    total_score: Optional[float] = None
    fundamental: Optional[dict] = None
    technical: Optional[dict] = None


class DailyOHLCVResponse(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class SurgeStockResponse(BaseModel):
    code: str
    name: str
    price: float
    change_rate: float
    volume: int
    change_price: float


class MinuteOHLCVResponse(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int


# ── KIS REST Client ───────────────────────────────────────────
kis_client = get_kis_client()
_surge_cache: dict = {"data": [], "ts": 0}
_us_surge_cache: dict = {"data": [], "ts": 0}
_penny_stocks_cache: dict = {"data": [], "ts": 0}
_weekly_cache: dict = {}
_minute_cache: dict = {}
_daily_cache: dict = {}


# ── Endpoints ────────────────────────────────────────────────
@router.get("/{code}/score", response_model=Optional[ScoreResponse])
async def get_stock_score(code: str, market: str = "KR"):
    """종목 점수 조회 (인메모리 캐시, 없으면 실시간 계산)"""
    try:
        result = await calculate_score(code, market=market)
        return result
    except Exception as e:
        logger.error(f"Score calculation failed for {code}: {e}")
        return None


@router.get("/surge", response_model=List[SurgeStockResponse])
async def get_surge_stocks(market: str = "KR", limit: int = 100):
    """
    급등주 목록
    - KR: 가격 2만원 이하 거래량 급증 종목
    - US: Top Gainers (day_gainers + most_actives)

    Args:
        market: 시장 (KR/US)
        limit: 최대 종목 수 (기본값: 100, US는 최대 200)
    """
    now = time.time()

    if market == "US":
        # limit 범위 제한 (10~200)
        limit = max(10, min(limit, 200))

        if now - _us_surge_cache["ts"] < 30:
            return _us_surge_cache["data"][:limit]
        try:
            from ...us.yfinance_client import get_us_surge_stocks
            results = await get_us_surge_stocks(limit=limit)
            _us_surge_cache["data"] = results
            _us_surge_cache["ts"] = now
            return results
        except Exception as e:
            logger.error(f"US surge error: {e}")
            return _us_surge_cache["data"][:limit]

    # KR
    # limit 범위 제한 (10~200)
    limit = max(10, min(limit, 200))

    if now - _surge_cache["ts"] < 30:
        return _surge_cache["data"][:limit]
    try:
        results = await kis_client.get_volume_rank(max_price=20000, limit=limit)
        _surge_cache["data"] = results
        _surge_cache["ts"] = now
        return results
    except Exception as e:
        logger.error(f"KIS volume rank error: {e}")
        return _surge_cache["data"][:limit]


@router.get("/penny-stocks", response_model=List[dict])
async def get_penny_stocks():
    """
    미국 주식 중 조건 필터링:
    - 주가 1달러 미만
    - 당일 거래량 급증 (전일 대비 2배 이상)
    - 최근 2일(D-1, D-2) 거래량이 그 이전(D-3)보다 작음
    """
    now = time.time()

    # 5분 캐싱
    if now - _penny_stocks_cache["ts"] < 300:
        return _penny_stocks_cache["data"]

    try:
        from ...us.yfinance_client import get_penny_stocks_with_volume_pattern
        results = await get_penny_stocks_with_volume_pattern(limit=50)
        _penny_stocks_cache["data"] = results
        _penny_stocks_cache["ts"] = now
        return results
    except Exception as e:
        logger.error(f"Penny stocks error: {e}")
        return _penny_stocks_cache["data"]


@router.get("/{code}/weekly", response_model=List[DailyOHLCVResponse])
async def get_stock_weekly(code: str, market: str = "KR"):
    """주봉 데이터 조회 (KR: pykrx 1년, US: yfinance 1년)"""
    now = time.time()
    cache_key = f"{market}:{code}"
    cached = _weekly_cache.get(cache_key)
    if cached and now - cached["ts"] < 600:
        return cached["data"]

    try:
        if market == "US":
            from ...us.yfinance_client import get_us_weekly_chart
            results = await get_us_weekly_chart(code)
        else:
            end = datetime.now()
            start = end - timedelta(days=365)
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: pykrx_stock.get_market_ohlcv_by_date(
                    start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), code, frequency="w"
                ),
            )
            if df.empty:
                return []
            results = []
            for date, row in df.iterrows():
                if int(row["거래량"]) == 0:
                    continue
                results.append({
                    "time": date.strftime("%Y-%m-%d"),
                    "open": int(row["시가"]),
                    "high": int(row["고가"]),
                    "low": int(row["저가"]),
                    "close": int(row["종가"]),
                    "volume": int(row["거래량"]),
                })

        _weekly_cache[cache_key] = {"data": results, "ts": now}
        return results
    except Exception as e:
        logger.error(f"Weekly chart error for {code}: {e}")
        if cached:
            return cached["data"]
        return []


@router.get("/{code}/minute", response_model=List[MinuteOHLCVResponse])
async def get_stock_minute(code: str, market: str = "KR"):
    """분봉 데이터 조회 (KR: KIS API, US: yfinance)"""
    now = time.time()
    cache_key = f"{market}:{code}"
    cached = _minute_cache.get(cache_key)
    if cached and now - cached["ts"] < 60:
        return cached["data"]

    try:
        if market == "US":
            from ...us.yfinance_client import get_us_minute_chart
            results = await get_us_minute_chart(code)
        else:
            results = await kis_client.get_minute_chart(code)
        _minute_cache[cache_key] = {"data": results, "ts": now}
        return results
    except Exception as e:
        logger.error(f"Minute chart error for {code}: {e}")
        if cached:
            return cached["data"]
        return []


@router.get("/{code}/daily", response_model=List[DailyOHLCVResponse])
async def get_stock_daily(code: str, market: str = "KR"):
    """일봉 데이터 조회 (KR: pykrx, US: yfinance)"""
    now = time.time()
    cache_key = f"{market}:{code}"
    cached = _daily_cache.get(cache_key)
    if cached and now - cached["ts"] < 300:
        return cached["data"]

    try:
        if market == "US":
            from ...us.yfinance_client import get_us_daily_chart
            results = await get_us_daily_chart(code)
        else:
            end = datetime.now()
            start = end - timedelta(days=90)
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: pykrx_stock.get_market_ohlcv_by_date(
                    start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), code
                ),
            )
            if df.empty:
                return []
            results = []
            for date, row in df.iterrows():
                if int(row["거래량"]) == 0:
                    continue
                results.append({
                    "time": date.strftime("%Y-%m-%d"),
                    "open": int(row["시가"]),
                    "high": int(row["고가"]),
                    "low": int(row["저가"]),
                    "close": int(row["종가"]),
                    "volume": int(row["거래량"]),
                })

        _daily_cache[cache_key] = {"data": results, "ts": now}
        return results
    except Exception as e:
        logger.error(f"Daily chart error for {code}: {e}")
        if cached:
            return cached["data"]
        return []


# ── Finviz Screener ──────────────────────────────────────────
@router.get("/surge/finviz", response_model=List[dict])
async def get_finviz_surge_stocks_endpoint(
    strategy: str = Query(
        default="gainers",
        description="스크리닝 전략: gainers, breakout, volume, momentum, penny, all"
    ),
    limit: int = Query(default=100, ge=10, le=500, description="최대 종목 수")
):
    """
    Finviz 스크리너로 급등주 발굴

    **전략 종류:**
    - `gainers`: 가격 급등주 (Top Gainers)
    - `breakout`: 신고가 돌파
    - `volume`: 거래량 급증
    - `momentum`: 모멘텀 종목
    - `penny`: 페니스탁 (<$1)
    - `all`: 모든 활발한 종목

    **Yahoo Finance 대비 장점:**
    - Yahoo Finance: 최대 47개
    - Finviz: 최대 500개 (전략당)

    **예시:**
    ```
    GET /stocks/surge/finviz?strategy=gainers&limit=100
    GET /stocks/surge/finviz?strategy=penny&limit=50
    ```
    """
    try:
        from ...us.finviz_screener import get_finviz_surge_stocks

        results = await get_finviz_surge_stocks(
            limit=limit,
            strategy=strategy
        )

        logger.info(f"Finviz screener returned {len(results)} stocks for {strategy}")
        return results

    except Exception as e:
        logger.error(f"Finviz screener error: {e}")
        import traceback
        traceback.print_exc()
        return []


@router.get("/surge/combined", response_model=List[dict])
async def get_combined_surge_stocks_endpoint(
    limit: int = Query(default=100, ge=10, le=500, description="최대 종목 수")
):
    """
    여러 스크리닝 전략 조합 (최고의 급등주 발굴)

    **조합 비율:**
    - Gainers: 50%
    - Volume: 30%
    - Momentum: 20%

    중복 제거 후 change_rate 높은 순 정렬

    **예시:**
    ```
    GET /stocks/surge/combined?limit=100
    ```
    """
    try:
        from ...us.finviz_screener import get_combined_surge_stocks

        results = await get_combined_surge_stocks(limit=limit)

        logger.info(f"Combined screener returned {len(results)} unique stocks")
        return results

    except Exception as e:
        logger.error(f"Combined screener error: {e}")
        import traceback
        traceback.print_exc()
        return []


@router.get("/screener/strategies", response_model=dict)
async def get_screener_strategies():
    """
    사용 가능한 모든 스크리닝 전략 정보

    Returns:
        {
            "gainers": {
                "name": "Top Gainers",
                "description": "가격 급등주",
                "filters": {...}
            },
            ...
        }
    """
    try:
        from ...us.finviz_screener import get_available_strategies
        return get_available_strategies()
    except Exception as e:
        logger.error(f"Get strategies error: {e}")
        return {}
