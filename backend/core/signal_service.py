"""
Signal generation service for trading strategies.
주식 데이터를 가져와서 진입/청산 신호를 생성하는 서비스
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
from pykrx import stock as pykrx_stock

from .signals import SignalManager
from .indicators import IndicatorEngine

logger = logging.getLogger(__name__)

# KRX 업종 지수 코드 — 구체적 키워드를 앞에 배치 (순서 중요: 첫 번째 매칭 사용)
# 예: "반도체" 가 "IT" 보다 앞에 있어야 "반도체장비" 종목이 "IT" 로 잘못 분류되지 않음
_KRX_SECTOR_INDEX: List[Tuple[str, str]] = [
    # ── KOSPI 세부 업종 (구체적 → 일반 순) ───────────────────────────────
    ("반도체",   "1028"),   # KOSPI 200 정보기술(반도체 포함)
    ("디스플레이", "1028"),
    ("전기전자",  "1028"),
    ("2차전지",   "1020"),   # KOSPI 200 소재 (배터리/소재 계열)
    ("배터리",    "1020"),
    ("자동차",    "1034"),   # KOSPI 200 자동차
    ("타이어",    "1034"),
    ("은행",      "1035"),   # KOSPI 200 금융
    ("보험",      "1035"),
    ("증권",      "1035"),
    ("금융",      "1035"),
    ("바이오",    "1006"),   # KOSPI 200 헬스케어
    ("제약",      "1006"),
    ("의료",      "1006"),
    ("헬스케어",  "1006"),
    ("화학",      "1033"),   # KOSPI 200 화학
    ("정유",      "1030"),   # KOSPI 200 에너지
    ("에너지",    "1030"),
    ("건설",      "1025"),   # KOSPI 200 건설
    ("철강",      "1027"),   # KOSPI 200 철강/소재
    ("금속",      "1027"),
    ("소재",      "1027"),
    ("음식료",    "1002"),   # KOSPI 200 (소비재 근사치)
    ("유통",      "1002"),
    ("소비자",    "1002"),
    ("운송",      "1026"),   # KOSPI 200 운송
    ("조선",      "1024"),   # KOSPI 200 조선
    ("기계",      "1022"),   # KOSPI 200 기계
    ("통신",      "1037"),   # KOSPI 200 통신
    ("IT",        "1028"),   # 일반 IT — 구체 키워드 소진 후 마지막 매칭
]
_KOSPI_INDEX_TICKER = "1001"
_KOSDAQ_INDEX_TICKER = "2001"

# ── 공유 시장 데이터 캐시 (시장 지수 + 섹터 분류표) ────────────────────────
# 시장 지수 OHLCV와 섹터 분류는 모든 종목에 동일 → Bulk 스캔 시 1회만 조회
# 캐시 키: "shared:{KOSPI|KOSDAQ}:{days}" → 시장별 분리
_shared_market_cache: Dict = {}
_SHARED_MARKET_TTL = 300  # 5분 TTL

# ── 종목별 상장 시장(KOSPI/KOSDAQ) 감지 캐시 ─────────────────────────────
_ticker_market_cache: Dict = {}
_TICKER_MARKET_TTL = 3600  # 1시간 TTL (장중 상장 시장은 변하지 않음)


async def _run_sync(fn):
    """Run blocking function in thread executor"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn)


async def _detect_stock_market(code: str) -> str:
    """종목 코드가 KOSPI인지 KOSDAQ인지 감지 (결과 1시간 캐싱)

    Returns:
        "KOSPI" | "KOSDAQ"  (판별 불가 시 "KOSPI" 기본값)
    """
    import time
    now = time.time()

    # 종목별 캐시 확인
    cached = _ticker_market_cache.get(code)
    if cached and now - cached["ts"] < _TICKER_MARKET_TTL:
        return cached["market"]

    today = datetime.now().strftime("%Y%m%d")

    async def _get_ticker_list(market_name: str) -> List[str]:
        list_key = f"ticker_list:{market_name}:{today}"
        c = _ticker_market_cache.get(list_key)
        if c and now - c["ts"] < _TICKER_MARKET_TTL:
            return c["tickers"]
        try:
            tickers = await _run_sync(
                lambda: pykrx_stock.get_market_ticker_list(today, market=market_name)
            )
            _ticker_market_cache[list_key] = {"tickers": tickers or [], "ts": now}
            return tickers or []
        except Exception as e:
            logger.debug(f"티커 목록 조회 실패 ({market_name}): {e}")
            return []

    kospi_tickers, kosdaq_tickers = await asyncio.gather(
        _get_ticker_list("KOSPI"),
        _get_ticker_list("KOSDAQ"),
    )

    if code in kospi_tickers:
        market = "KOSPI"
    elif code in kosdaq_tickers:
        market = "KOSDAQ"
    else:
        market = "KOSPI"  # 기본값

    _ticker_market_cache[code] = {"market": market, "ts": now}
    return market


def _compute_atr_stop(entry_price: float, atr: float, max_loss_ratio: float = 0.08) -> float:
    """ATR 기반 손절가 계산 (StopLossStrategy 와 동일 로직)

    ATR% 에 따라 배수를 자동 결정:
        ATR% < 2%  → 1.2배 (안정적 종목)
        ATR% 2~4%  → 1.5배 (표준)
        ATR% > 4%  → 2.0배 (고변동 종목)

    hard floor: entry_price × (1 - max_loss_ratio) — 최대 손실 상한선
    """
    if entry_price <= 0 or atr <= 0:
        return 0.0
    atr_pct = atr / entry_price
    if atr_pct < 0.02:
        mult = 1.2
    elif atr_pct < 0.04:
        mult = 1.5
    else:
        mult = 2.0
    raw_stop = entry_price - atr * mult
    hard_floor = entry_price * (1 - max_loss_ratio)
    return max(raw_stop, hard_floor)


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


async def collect_investor_supply_data(code: str, market: str = "KR", days: int = 12) -> Optional[pd.DataFrame]:
    """기관/외국인 투자자별 거래량 조회 (KR 전용)

    pykrx get_market_trading_volume_by_date 결과를 반환한다.
    MultiIndex 컬럼: (거래유형, 투자자유형)
    거래유형: 매도, 매수, 순매수
    투자자유형: 기관합계, 기타법인, 개인, 외국인합계, 전체

    Args:
        code:  종목 코드
        market: "KR"만 지원 (US는 None 반환)
        days:  조회 기간 (영업일 기준 10일 + 여유 2일)

    Returns:
        DataFrame 또는 None (조회 실패 시)
    """
    if market != "KR":
        return None

    end = datetime.now()
    start = end - timedelta(days=days + 5)  # 영업일 여유 확보

    try:
        df = await _run_sync(
            lambda: pykrx_stock.get_market_trading_volume_by_date(
                start.strftime("%Y%m%d"),
                end.strftime("%Y%m%d"),
                code
            )
        )
        return df if df is not None and not df.empty else None
    except Exception as e:
        logger.warning(f"[{code}] 투자자별 거래량 조회 실패: {e}")
        return None


async def _get_shared_market_data(days: int = 20, market: str = "KOSPI") -> Dict:
    """시장 지수 OHLCV + KRX 섹터 분류표를 시장별 1회 캐싱

    KOSPI/KOSDAQ 를 별도 캐시 키로 분리하여 각각 캐싱.
    시장 지수와 섹터 분류는 asyncio.gather 병렬 조회 후 저장.

    Bulk 스캔 효과: 30종목 × 2 API → 2 API (TTL 내 재사용)

    Args:
        days:   조회 기간
        market: "KOSPI" | "KOSDAQ"

    Returns:
        {
            "market_ohlcv": DataFrame|None,   # 시장 지수 OHLCV
            "sector_df":    DataFrame|None,   # KRX 섹터 분류표
            "from_str":     str,
            "to_str":       str,
            "col_map":      dict,
        }
    """
    import time
    now = time.time()
    cache_key = f"shared:{market}:{days}"  # 시장별 분리

    cached = _shared_market_cache.get(cache_key)
    if cached and now - cached["ts"] < _SHARED_MARKET_TTL:
        return cached["data"]

    end = datetime.now()
    start = end - timedelta(days=days + 10)
    from_str = start.strftime("%Y%m%d")
    to_str = end.strftime("%Y%m%d")
    col_map = {"시가": "Open", "고가": "High", "저가": "Low", "종가": "Close", "거래량": "Volume"}

    index_ticker = _KOSDAQ_INDEX_TICKER if market == "KOSDAQ" else _KOSPI_INDEX_TICKER

    async def _fetch_market_ohlcv():
        try:
            raw = await _run_sync(
                lambda: pykrx_stock.get_index_ohlcv_by_date(from_str, to_str, index_ticker)
            )
            return raw.rename(columns=col_map) if raw is not None and not raw.empty else None
        except Exception as e:
            logger.debug(f"{market} 지수 조회 실패: {e}")
            return None

    async def _fetch_sector_df():
        try:
            df = await _run_sync(
                lambda: pykrx_stock.get_market_sector_classifications(to_str, market)
            )
            return df if df is not None and not df.empty else None
        except Exception as e:
            logger.debug(f"KRX 섹터 분류 조회 실패 ({market}): {e}")
            return None

    market_ohlcv, sector_df = await asyncio.gather(_fetch_market_ohlcv(), _fetch_sector_df())

    result = {
        "market_ohlcv": market_ohlcv,
        "sector_df": sector_df,
        "from_str": from_str,
        "to_str": to_str,
        "col_map": col_map,
    }
    _shared_market_cache[cache_key] = {"data": result, "ts": now}
    return result


async def collect_sector_momentum_data(code: str, market: str = "KR", days: int = 20) -> Dict:
    """종목의 업종 지수 + 시장 지수 OHLCV 조회

    - 시장 지수·섹터 분류: _get_shared_market_data 캐시 재사용
    - KOSPI/KOSDAQ 자동 감지 후 각각의 시장 지수(1001/2001)를 벤치마크로 사용
    - 업종 지수: 종목마다 다르므로 개별 조회 (1 API/종목)

    Args:
        code:   종목 코드
        market: "KR"만 지원 (US는 빈 dict 반환)
        days:   조회 기간

    Returns:
        {"sector_ohlcv": DataFrame|None, "market_ohlcv": DataFrame|None}
    """
    if market != "KR":
        return {"sector_ohlcv": None, "market_ohlcv": None}

    # KOSPI/KOSDAQ 감지 → 적절한 벤치마크 선택
    krx_market = await _detect_stock_market(code)

    # 공유 데이터 캐시에서 가져오기 (캐시 히트 시 API 호출 없음)
    shared = await _get_shared_market_data(days=days, market=krx_market)
    market_ohlcv = shared["market_ohlcv"]
    sector_df = shared["sector_df"]
    from_str = shared["from_str"]
    to_str = shared["to_str"]
    col_map = shared["col_map"]

    # 종목별 업종 지수 조회 (캐시 불가 — 종목마다 업종이 다름)
    sector_ohlcv = None
    if sector_df is not None:
        try:
            code_col = next(
                (c for c in sector_df.columns if "코드" in str(c) or "code" in str(c).lower()), None
            )
            if code_col and code in sector_df[code_col].values:
                row = sector_df[sector_df[code_col] == code].iloc[0]
            elif code in sector_df.index:
                row = sector_df.loc[code]
            else:
                row = None

            if row is not None:
                sector_name_col = next(
                    (c for c in sector_df.columns if "섹터" in str(c) or "업종" in str(c)), None
                )
                if sector_name_col:
                    sector_name = str(row[sector_name_col])
                    # _KRX_SECTOR_INDEX 는 List[Tuple] — 구체 키워드가 앞에 있어 첫 번째 매칭 우선
                    sector_ticker = next(
                        (ticker for keyword, ticker in _KRX_SECTOR_INDEX
                         if keyword in sector_name), None
                    )
                    if sector_ticker:
                        _t = sector_ticker  # lambda late-binding 방지
                        raw_s = await _run_sync(
                            lambda: pykrx_stock.get_index_ohlcv_by_date(from_str, to_str, _t)
                        )
                        if raw_s is not None and not raw_s.empty:
                            sector_ohlcv = raw_s.rename(columns=col_map)
        except Exception as e:
            logger.debug(f"[{code}] 업종 지수 조회 실패: {e}")

    return {"sector_ohlcv": sector_ohlcv, "market_ohlcv": market_ohlcv}


async def generate_entry_signal(code: str, market: str = "KR", strategy: str = "combined") -> Dict:
    """
    진입 신호 생성

    Args:
        code: 종목 코드
        market: "KR" | "US"
        strategy: "volume" | "technical" | "pattern" | "rsi_golden_cross" | "combined"

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
    # 전략별 필요 데이터 기간
    if strategy == "weekly_rsi_swing":
        days = 350   # 주봉 RSI(14주) + MA200 + 버퍼
    elif strategy == "rsi_golden_cross":
        days = 250   # MA200 + 버퍼
    elif strategy == "multi_tf_momentum_plus":
        days = 150   # MA60 + MACD(26+9) + RSI 14 + 여유
    else:
        days = 120

    # combined + KR 시장: OHLCV / 수급 / 섹터 데이터를 병렬 수집
    if strategy == "combined" and market == "KR":
        ohlcv_data, investor_data, sector_data = await asyncio.gather(
            collect_ohlcv_data(code, market, days=days),
            collect_investor_supply_data(code, market),
            collect_sector_momentum_data(code, market),
        )
    else:
        ohlcv_data = await collect_ohlcv_data(code, market, days=days)
        investor_data = None
        sector_data = None

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

    # 신호 생성 (combined+KR: 수급·섹터 보너스 포함)
    signal_manager = SignalManager()
    result = signal_manager.generate_entry_signal(
        ohlcv_data, strategy,
        investor_data=investor_data,
        sector_data=sector_data,
    )

    # 컵앤핸들 감지 여부 추출 (combined → breakdown.pattern, pattern → 직접)
    pattern_result = result.get("breakdown", {}).get("pattern") or result
    cup_handle_data = pattern_result.get("cup_handle", {})
    cup_handle_confirmed = bool(cup_handle_data.get("is_cup_handle", False))

    # 진입 시점 ATR 계산 — 손절가 사전 안내용 (entry-time 고정)
    entry_atr = None
    entry_atr_stop = None
    if len(ohlcv_data) >= 15:
        atr_s = IndicatorEngine.calculate_atr(
            ohlcv_data["High"], ohlcv_data["Low"], ohlcv_data["Close"], period=14
        ).dropna()
        if len(atr_s) > 0:
            entry_atr = float(atr_s.iloc[-1])
            current_price = float(ohlcv_data["Close"].iloc[-1])
            entry_atr_stop = round(_compute_atr_stop(current_price, entry_atr), 0)

    return {
        "code": code,
        "market": market,
        "signal": result["signal"],
        "strength": result["strength"],
        "score": result["score"],
        "reasons": result["reasons"],
        "timestamp": datetime.now().isoformat(),
        "current_price": float(ohlcv_data["Close"].iloc[-1]),
        "breakdown": result.get("breakdown", {}),
        "cup_handle_confirmed": cup_handle_confirmed,
        "cup_handle": cup_handle_data if cup_handle_data else None,
        # ATR 기반 동적 손절 사전 안내
        "atr": round(entry_atr, 0) if entry_atr else None,
        "atr_stop_price": entry_atr_stop,
    }


async def generate_entry_signals_bulk(codes: List[str], market: str = "KR",
                                      strategy: str = "combined",
                                      min_score: float = 50) -> List[Dict]:
    """
    여러 종목의 진입 신호 생성 (필터링) - 병렬 처리로 최적화

    Args:
        codes: 종목 코드 리스트
        market: "KR" | "US"
        strategy: 신호 전략
        min_score: 최소 점수 (이 이상만 반환)

    Returns:
        진입 신호 리스트 (점수 높은 순)
    """
    # Semaphore로 동시 실행 수 제한 (API rate limit 고려)
    semaphore = asyncio.Semaphore(5)  # 최대 5개 동시 실행

    async def _process_with_limit(code: str):
        async with semaphore:
            try:
                signal = await generate_entry_signal(code, market, strategy)

                # 필터링: BUY + 최소점수 이상 OR 컵앤핸들 감지 (점수 미달도 포함)
                passes_score = signal["signal"] == "BUY" and signal["score"] >= min_score
                is_cup_handle = signal.get("cup_handle_confirmed", False)
                if passes_score or is_cup_handle:
                    return signal

                return None

            except Exception as e:
                logger.error(f"[{code}] Signal generation failed: {e}")
                return None

    # 모든 종목을 병렬로 처리
    logger.info(f"Processing {len(codes)} stocks in parallel (max 5 concurrent)...")
    tasks = [_process_with_limit(code) for code in codes]
    all_results = await asyncio.gather(*tasks)

    # None 제거 및 결과 필터링
    results = [r for r in all_results if r is not None]

    # 점수 높은 순 정렬
    results.sort(key=lambda x: x["score"], reverse=True)

    logger.info(f"Found {len(results)} signals with score >= {min_score}")
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
    # 현재 가격 + ATR 계산을 위해 30일 데이터 수집 (기존 5일→30일)
    ohlcv_data = await collect_ohlcv_data(code, market, days=30)

    if ohlcv_data.empty:
        logger.warning(f"[{code}] Cannot get current price for exit signal")
        return {
            "code": code,
            "should_exit": False,
            "error": "no_price_data"
        }

    current_price = float(ohlcv_data["Close"].iloc[-1])
    current_time = datetime.now()

    # ATR(14) 계산 — 변동성 기반 동적 손절가 산출
    atr = None
    if len(ohlcv_data) >= 15:
        atr_series = IndicatorEngine.calculate_atr(
            ohlcv_data["High"], ohlcv_data["Low"], ohlcv_data["Close"], period=14
        ).dropna()
        if len(atr_series) > 0:
            atr = float(atr_series.iloc[-1])

    # 청산 신호 생성
    signal_manager = SignalManager()
    result = signal_manager.generate_exit_signal(
        entry_price=entry_price,
        entry_time=entry_time,
        current_price=current_price,
        current_time=current_time,
        position_size=1.0,
        atr=atr,
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
        "details": result.get("details", {}),
        # ATR 기반 동적 손절 정보 (적응형 배수 적용)
        "atr": round(atr, 0) if atr else None,
        "atr_stop_price": round(_compute_atr_stop(entry_price, atr), 0) if atr else None,
    }


async def scan_pullback_candidates(
    codes: List[str],
    market: str = "KR",
    min_score: int = 60,
) -> List[Dict]:
    """
    Track B: 눌림목/반등 스캐너
    관심종목 또는 지정 종목 풀에서 피보나치+MA20 기반 눌림목 후보 탐색

    Returns:
        is_pullback=True인 종목 리스트, score 내림차순
    """
    from .signals import PricePatternSignal

    scanner = PricePatternSignal()
    semaphore = asyncio.Semaphore(5)

    async def _check(code: str) -> Optional[Dict]:
        async with semaphore:
            try:
                ohlcv = await collect_ohlcv_data(code, market, days=70)
                if ohlcv.empty or len(ohlcv) < 60:
                    return None

                result = scanner.detect_pullback(ohlcv)
                if not result["is_pullback"] or result["score"] < min_score:
                    return None

                current_price = float(ohlcv["Close"].iloc[-1])
                fib = result.get("fib_levels", {})

                return {
                    "code": code,
                    "market": market,
                    "score": result["score"],
                    "reasons": result["reasons"],
                    "current_price": current_price,
                    "adjustment_days": result.get("adjustment_days", 0),
                    "fib_levels": {
                        k: round(v, 0) for k, v in fib.items()
                    } if fib else {},
                    "is_reversal_risk": result["is_reversal_risk"],
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"[TrackB] {code} error: {e}")
                return None

    tasks = [_check(code) for code in codes]
    results = [r for r in await asyncio.gather(*tasks) if r is not None]
    results.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"[TrackB] {len(results)}/{len(codes)} pullback candidates (min_score={min_score})")
    return results


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
        from ..kis.rest_client import get_kis_client
        surge_stocks = await get_kis_client().get_volume_rank(max_price=20000, limit=30)

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
