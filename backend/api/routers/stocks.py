"""
Stocks API Router
주식 데이터 관련 엔드포인트
"""
from fastapi import APIRouter
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncio
import time
import logging

from ...core.score_service import calculate_score
from ...kis.rest_client import KISRestClient
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
kis_client = KISRestClient()
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
async def get_surge_stocks(market: str = "KR"):
    """급등주 목록 (KR: 가격 2만원 이하, US: Top Gainers)"""
    now = time.time()

    if market == "US":
        if now - _us_surge_cache["ts"] < 30:
            return _us_surge_cache["data"]
        try:
            from ...us.yfinance_client import get_us_surge_stocks
            results = await get_us_surge_stocks(limit=20)
            _us_surge_cache["data"] = results
            _us_surge_cache["ts"] = now
            return results
        except Exception as e:
            logger.error(f"US surge error: {e}")
            return _us_surge_cache["data"]

    # KR
    if now - _surge_cache["ts"] < 30:
        return _surge_cache["data"]
    try:
        results = await kis_client.get_volume_rank(max_price=20000, limit=20)
        _surge_cache["data"] = results
        _surge_cache["ts"] = now
        return results
    except Exception as e:
        logger.error(f"KIS volume rank error: {e}")
        return _surge_cache["data"]


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
