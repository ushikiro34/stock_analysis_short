"""
Finviz Screener Integration
Provides advanced stock screening with 60+ filters and multiple strategies
"""
import asyncio
import logging
from typing import List, Optional, Dict
from datetime import datetime
from collections import deque
from time import time

import pandas as pd
from finvizfinance.screener.overview import Overview

logger = logging.getLogger(__name__)


# ── Rate Limiting ────────────────────────────────────────────
_request_times = deque(maxlen=10)  # 분당 최대 10회


def _check_rate_limit():
    """Rate limiting: 분당 최대 10회 요청"""
    now = time()
    if len(_request_times) == 10:
        if now - _request_times[0] < 60:
            wait_time = 60 - (now - _request_times[0])
            raise Exception(f"Rate limit exceeded. Wait {wait_time:.1f}s")
    _request_times.append(now)


# ── Caching System ────────────────────────────────────────────
_finviz_cache = {
    "gainers": {"data": [], "ts": 0},
    "breakout": {"data": [], "ts": 0},
    "volume": {"data": [], "ts": 0},
    "momentum": {"data": [], "ts": 0},
    "penny": {"data": [], "ts": 0},
    "all": {"data": [], "ts": 0},
}

CACHE_TTL = 300  # 5분


# ── Strategy Definitions ─────────────────────────────────────
STRATEGIES = {
    "gainers": {
        "name": "Top Gainers",
        "description": "가격 급등주 (상승률 높은 종목)",
        "filters": {
            "Change": "Up 5%",                        # 5% 이상 상승 (페이지 감소)
            "Average Volume": "Over 1M",              # 거래량 100만 이상
            "Market Cap.": "+Small (over $300mln)"    # 시가총액 3억 이상
        }
    },
    "breakout": {
        "name": "Breakout Stocks",
        "description": "신고가 돌파 종목",
        "filters": {
            "Price": "Over $1",
            "Average Volume": "Over 1M",              # 거래량 증가
            "Change": "Up 3%",                        # 3% 이상
            "20-Day Simple Moving Average": "Price above SMA20"
        }
    },
    "volume": {
        "name": "Volume Surge",
        "description": "거래량 급증 종목",
        "filters": {
            "Relative Volume": "Over 3",              # 3배 이상 (더 엄격)
            "Average Volume": "Over 1M",
            "Change": "Up"
        }
    },
    "momentum": {
        "name": "Momentum Stocks",
        "description": "모멘텀 종목 (상승 추세)",
        "filters": {
            "Performance": "Week Up 10%",             # 주간 10% 이상
            "RSI (14)": "Overbought (70)",           # RSI 70 이상 (더 강한 모멘텀)
            "Average Volume": "Over 1M",
            "20-Day Simple Moving Average": "Price above SMA20"
        }
    },
    "penny": {
        "name": "Penny Stocks",
        "description": "페니스탁 ($1 미만)",
        "filters": {
            "Price": "Under $1",
            "Average Volume": "Over 1M",              # 거래량 증가
            "Change": "Up 10%",                       # 10% 이상 (더 엄격)
            "Relative Volume": "Over 2"               # 2배 이상
        }
    },
    "all": {
        "name": "All Active Stocks",
        "description": "모든 활발한 종목 (최소 필터)",
        "filters": {
            "Average Volume": "Over 2M",              # 거래량 200만 이상
            "Change": "Up"                            # 상승 종목만
        }
    }
}


async def _run_sync(fn):
    """동기 함수를 비동기로 실행"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn)


def _convert_to_standard_format(df: pd.DataFrame) -> List[Dict]:
    """
    Finviz DataFrame을 시스템 표준 포맷으로 변환

    Finviz 컬럼 -> 시스템 컬럼 매핑:
    - Ticker -> code
    - Company -> name
    - Price -> price
    - Change -> change_pct
    - Volume -> volume
    - Market Cap -> market_cap
    - Sector -> sector
    - Industry -> industry
    """
    results = []

    for _, row in df.iterrows():
        try:
            # 가격 파싱 (문자열에서 숫자 추출)
            price_str = str(row.get("Price", "0"))
            price = float(price_str.replace(",", "").replace("$", ""))

            # 변동률 파싱 ("+5.23%" -> 5.23)
            change_str = str(row.get("Change", "0%"))
            change_pct = float(change_str.replace("%", "").replace("+", ""))

            # 거래량 파싱 ("1.5M" -> 1500000)
            volume_str = str(row.get("Volume", "0"))
            volume = _parse_volume(volume_str)

            # 시가총액 파싱 ("1.2B" -> "1.2B")
            market_cap = str(row.get("Market Cap", ""))

            results.append({
                "code": str(row.get("Ticker", "")),
                "name": str(row.get("Company", "")),
                "price": round(price, 2),
                "change_price": round(price * change_pct / 100, 2),
                "change_rate": round(change_pct, 2),
                "volume": int(volume),
                "market_cap": market_cap,
                "sector": str(row.get("Sector", "")),
                "industry": str(row.get("Industry", "")),
                "source": "finviz"
            })
        except Exception as e:
            logger.debug(f"Failed to parse row: {e}")
            continue

    return results


def _parse_volume(volume_str: str) -> int:
    """거래량 문자열을 숫자로 변환 (1.5M -> 1500000)"""
    volume_str = volume_str.upper().replace(",", "")

    if "M" in volume_str:
        return int(float(volume_str.replace("M", "")) * 1_000_000)
    elif "K" in volume_str:
        return int(float(volume_str.replace("K", "")) * 1_000)
    elif "B" in volume_str:
        return int(float(volume_str.replace("B", "")) * 1_000_000_000)
    else:
        try:
            return int(float(volume_str))
        except:
            return 0


async def get_finviz_surge_stocks(
    limit: int = 100,
    strategy: str = "gainers",
    custom_filters: Optional[Dict] = None
) -> List[Dict]:
    """
    Finviz 스크리너로 급등주 발굴

    Args:
        limit: 반환할 최대 종목 수 (10-500)
        strategy: 스크리닝 전략
            - "gainers": 가격 급등주
            - "breakout": 신고가 돌파
            - "volume": 거래량 급증
            - "momentum": 모멘텀 종목
            - "penny": 페니스탁 (<$1)
            - "all": 모든 활발한 종목
        custom_filters: 커스텀 필터 (선택)

    Returns:
        [
            {
                "code": "AAPL",
                "name": "Apple Inc.",
                "price": 150.25,
                "change_price": 3.45,
                "change_rate": 2.35,
                "volume": 75000000,
                "market_cap": "2.5T",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "source": "finviz"
            },
            ...
        ]
    """
    # 전략 선택
    if strategy not in STRATEGIES:
        logger.warning(f"Unknown strategy '{strategy}', using 'gainers'")
        strategy = "gainers"

    # ── Phase 2: 캐시 확인 ──
    now = time()
    cache_entry = _finviz_cache.get(strategy, {"data": [], "ts": 0})

    if now - cache_entry["ts"] < CACHE_TTL and cache_entry["data"]:
        logger.info(f"Returning cached Finviz data for {strategy} ({len(cache_entry['data'])} stocks)")
        return cache_entry["data"][:limit]

    # ── 캐시 만료 또는 없음 → 새로 조회 ──
    logger.info(f"Cache miss for {strategy}, fetching from Finviz...")

    # Rate limiting 체크
    try:
        _check_rate_limit()
    except Exception as e:
        logger.warning(f"Rate limit exceeded: {e}")
        # Rate limit 초과 시 오래된 캐시라도 반환
        if cache_entry["data"]:
            logger.info(f"Returning stale cache for {strategy}")
            return cache_entry["data"][:limit]
        raise

    strategy_config = STRATEGIES[strategy]
    filters = custom_filters or strategy_config["filters"]

    logger.info(f"Finviz screening: {strategy_config['name']} (limit={limit})")

    def _fetch():
        """동기 함수: Finviz 스크리닝 실행"""
        try:
            screener = Overview()
            screener.set_filter(filters_dict=filters)
            df = screener.screener_view()

            if df is None or df.empty:
                logger.warning(f"Finviz returned empty results for {strategy}")
                return []

            logger.info(f"Finviz returned {len(df)} stocks for {strategy}")

            # 표준 포맷으로 변환
            results = _convert_to_standard_format(df)

            # change_rate 높은 순으로 정렬
            results.sort(key=lambda x: abs(x.get("change_rate", 0)), reverse=True)

            return results[:limit]

        except Exception as e:
            logger.error(f"Finviz screening error: {e}")
            import traceback
            traceback.print_exc()
            return []

    # 비동기 실행
    results = await _run_sync(_fetch)

    # ── 캐시 업데이트 ──
    if results:
        _finviz_cache[strategy] = {"data": results, "ts": time()}
        logger.info(f"Cached {len(results)} stocks for {strategy} (TTL={CACHE_TTL}s)")

    return results[:limit]


async def get_all_strategies(limit_per_strategy: int = 50) -> Dict[str, List[Dict]]:
    """
    모든 스크리닝 전략 실행하여 결과 반환

    Args:
        limit_per_strategy: 각 전략당 최대 종목 수

    Returns:
        {
            "gainers": [...],
            "breakout": [...],
            "volume": [...],
            "momentum": [...],
            "penny": [...]
        }
    """
    results = {}

    # "all" 전략 제외
    strategies = [s for s in STRATEGIES.keys() if s != "all"]

    for strategy in strategies:
        try:
            logger.info(f"Running strategy: {strategy}")
            stocks = await get_finviz_surge_stocks(
                limit=limit_per_strategy,
                strategy=strategy
            )
            results[strategy] = stocks

            # Rate limiting을 위한 대기
            await asyncio.sleep(6)  # 6초 대기 (분당 10회)

        except Exception as e:
            logger.error(f"Strategy {strategy} failed: {e}")
            results[strategy] = []

    return results


async def get_combined_surge_stocks(limit: int = 100) -> List[Dict]:
    """
    여러 전략을 조합하여 최고의 급등주 발굴
    - gainers (50%)
    - volume (30%)
    - momentum (20%)

    중복 제거 후 change_rate 높은 순 정렬
    """
    logger.info("Running combined surge stock screening")

    # 병렬 실행
    gainers_task = get_finviz_surge_stocks(limit=int(limit * 0.5), strategy="gainers")
    volume_task = get_finviz_surge_stocks(limit=int(limit * 0.3), strategy="volume")
    momentum_task = get_finviz_surge_stocks(limit=int(limit * 0.2), strategy="momentum")

    # Rate limiting 고려하여 순차 실행
    gainers = await gainers_task
    await asyncio.sleep(6)

    volume = await volume_task
    await asyncio.sleep(6)

    momentum = await momentum_task

    # 중복 제거 (code 기준)
    all_stocks = {}
    for stock in gainers + volume + momentum:
        code = stock["code"]
        if code not in all_stocks:
            all_stocks[code] = stock
        else:
            # 더 높은 change_rate 선택
            if abs(stock["change_rate"]) > abs(all_stocks[code]["change_rate"]):
                all_stocks[code] = stock

    # change_rate 높은 순 정렬
    results = sorted(
        all_stocks.values(),
        key=lambda x: abs(x.get("change_rate", 0)),
        reverse=True
    )

    logger.info(f"Combined screening: {len(results)} unique stocks")

    return results[:limit]


def get_available_strategies() -> Dict:
    """사용 가능한 모든 스크리닝 전략 정보 반환"""
    return {
        strategy: {
            "name": config["name"],
            "description": config["description"],
            "filters": config["filters"]
        }
        for strategy, config in STRATEGIES.items()
    }
