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
from ...core.signal_service import collect_ohlcv_data
from ...core.signals import SignalManager

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
_pre_surge_cache: dict = {"data": [], "ts": 0}
_weekly_cache: dict = {}
_minute_cache: dict = {}
_daily_cache: dict = {}
_analyze_cache: dict = {}


# ── Endpoints ────────────────────────────────────────────────

@router.get("/{code}/analyze")
async def analyze_stock(code: str, market: str = "KR"):
    """
    종목 종합 분석 (관심주식 탭용)
    현재가·등락률·거래량비율·이동평균 이격·52주/20일 신고가·진입신호 반환
    """
    now = time.time()
    cache_key = f"{market}:{code}"
    cached = _analyze_cache.get(cache_key)
    if cached and now - cached["ts"] < 300:   # 5분 캐시
        return cached["data"]

    loop = asyncio.get_event_loop()

    try:
        # ── OHLCV 로드 (300일) ──────────────────────────────────
        if market == "KR":
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=300)
            raw = await loop.run_in_executor(
                None,
                lambda: pykrx_stock.get_market_ohlcv_by_date(
                    start_dt.strftime("%Y%m%d"), end_dt.strftime("%Y%m%d"), code
                ),
            )
            if raw.empty:
                return {"error": "no_data"}
            # 한글 컬럼 → 영문
            ohlcv = raw.rename(columns={
                "시가": "Open", "고가": "High", "저가": "Low",
                "종가": "Close", "거래량": "Volume"
            })[["Open", "High", "Low", "Close", "Volume"]]
            # 종목명
            _ticker_name = pykrx_stock.get_market_ticker_name(code)
            name = _ticker_name if isinstance(_ticker_name, str) and _ticker_name else code
        else:
            ohlcv = await collect_ohlcv_data(code, market, 300)
            if ohlcv.empty:
                return {"error": "no_data"}
            name = code

        close  = ohlcv["Close"]
        volume = ohlcv["Volume"]
        last   = ohlcv.iloc[-1]
        prev   = ohlcv.iloc[-2] if len(ohlcv) >= 2 else last

        curr_price  = float(last["Close"])
        prev_close  = float(prev["Close"])
        change_pct  = (curr_price - prev_close) / prev_close * 100 if prev_close else 0.0

        # 이동평균
        ma5   = float(close.rolling(5).mean().iloc[-1])   if len(close) >= 5   else curr_price
        ma20  = float(close.rolling(20).mean().iloc[-1])  if len(close) >= 20  else curr_price
        ma60  = float(close.rolling(60).mean().iloc[-1])  if len(close) >= 60  else curr_price
        ma120 = float(close.rolling(120).mean().iloc[-1]) if len(close) >= 120 else curr_price

        # 거래량 비율
        vol_ma20  = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else float(last["Volume"])
        vol_ratio = float(last["Volume"]) / vol_ma20 if vol_ma20 > 0 else 1.0

        # 52주 / 20일 신고가
        high52w = float(close.tail(252).max())
        low52w  = float(close.tail(252).min())
        high20d = float(close.tail(20).max())
        is_52w_high = bool(curr_price >= high52w * 0.999)
        is_20d_high = bool(curr_price >= high20d * 0.999)

        # 진입 신호
        mgr = SignalManager()
        sig = mgr.generate_entry_signal(ohlcv, strategy="combined")

        result = {
            "code": code,
            "name": name,
            "market": market,
            "current_price": curr_price,
            "open": float(last["Open"]),
            "high": float(last["High"]),
            "low": float(last["Low"]),
            "change_pct": round(change_pct, 2),
            "volume": int(last["Volume"]),
            "vol_ma20": round(vol_ma20, 0),
            "vol_ratio": round(vol_ratio, 2),
            "ma5":   round(ma5, 2),
            "ma20":  round(ma20, 2),
            "ma60":  round(ma60, 2),
            "ma120": round(ma120, 2),
            "vs_ma5_pct":   round((curr_price / ma5  - 1) * 100, 1) if ma5  > 0 else 0,
            "vs_ma20_pct":  round((curr_price / ma20 - 1) * 100, 1) if ma20 > 0 else 0,
            "vs_ma60_pct":  round((curr_price / ma60 - 1) * 100, 1) if ma60 > 0 else 0,
            "high52w": round(high52w, 2),
            "low52w":  round(low52w, 2),
            "high20d": round(high20d, 2),
            "is_52w_high": is_52w_high,
            "is_20d_high": is_20d_high,
            "signal": sig.get("signal", "HOLD"),
            "score":  sig.get("score", 0),
            "chase_blocked": sig.get("chase_blocked", False),
            "signal_reasons": sig.get("reasons", []),
            "pre_surge": sig.get("breakdown", {}).get("pattern", {}).get("pre_surge"),
            "updated_at": datetime.now().isoformat(),
        }

        _analyze_cache[cache_key] = {"data": result, "ts": now}
        return result

    except Exception as e:
        logger.error(f"Analyze error for {code}: {e}")
        return {"error": str(e)}
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


@router.get("/pre-surge", response_model=List[dict])
async def get_pre_surge_stocks():
    """
    거래량 상위 종목 중 급등 전 시그널 감지 목록
    - 건조회복 / 세력매집 / 압축횡보 패턴 탐색
    - 5분 캐시
    """
    now = time.time()
    if now - _pre_surge_cache["ts"] < 300:
        return _pre_surge_cache["data"]
    try:
        from ...core.signal_service import scan_pre_surge_stocks
        results = await scan_pre_surge_stocks()
        _pre_surge_cache["data"] = results
        _pre_surge_cache["ts"] = now
        return results
    except Exception as e:
        logger.error(f"Pre-surge scan error: {e}")
        return _pre_surge_cache["data"]


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
                    start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), code, freq="d"
                ),
            )
            if df.empty:
                return []
            # 일봉 → 주봉 리샘플 (pykrx는 weekly 미지원)
            df_w = df.resample("W-FRI").agg({
                "시가": "first", "고가": "max", "저가": "min", "종가": "last", "거래량": "sum"
            }).dropna(subset=["거래량"])
            df_w = df_w[df_w["거래량"] > 0]
            results = []
            for date, row in df_w.iterrows():
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
            results = await kis_client.get_full_day_minute_chart(code)
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
