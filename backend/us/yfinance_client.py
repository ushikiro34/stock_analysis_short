"""
US stock data provider using yfinance.
Mirrors the Korean data flow (pykrx/KIS) with identical output shapes.
"""
import asyncio
import logging
from datetime import datetime

import pandas as pd
import yfinance as yf

from ..core.indicators import IndicatorEngine

logger = logging.getLogger(__name__)


async def _run_sync(fn):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn)


async def get_us_surge_stocks(limit: int = 100) -> list[dict]:
    """
    Yahoo Finance Screener로 미국 급등주 조회
    - day_gainers (상승률 높은 종목)
    - most_actives (거래량 많은 종목)
    두 스크리너를 합쳐서 중복 제거 후 반환
    """
    def _fetch():
        try:
            from yfinance.screener.screener import screen
            # day_gainers와 most_actives 모두 조회
            gainers = screen("day_gainers").get("quotes", [])
            actives = screen("most_actives").get("quotes", [])
            logger.info(f"Fetched {len(gainers)} gainers, {len(actives)} actives")
        except Exception as e:
            logger.warning(f"yf.screener.screen failed: {e}")
            gainers = []
            actives = []

        # 중복 제거 (symbol 기준으로 dict 사용)
        all_quotes = {}
        for q in gainers + actives:
            symbol = q.get("symbol", "")
            if symbol and symbol not in all_quotes:
                all_quotes[symbol] = q

        stocks = []
        for q in all_quotes.values():
            symbol = q.get("symbol", "")
            price = q.get("regularMarketPrice", 0) or 0
            change = q.get("regularMarketChange", 0) or 0
            change_pct = q.get("regularMarketChangePercent", 0) or 0
            vol = q.get("regularMarketVolume", 0) or 0
            name = q.get("shortName") or q.get("longName") or symbol

            if price <= 0:
                continue

            # 6자리 순수 숫자 코드는 한국 KOSDAQ/KOSPI 종목 — US 스크리너 결과에서 제외
            if symbol.isdigit() and len(symbol) == 6:
                logger.debug(f"Skipping KR-format code from US screener: {symbol}")
                continue

            stocks.append({
                "code": symbol,
                "name": name,
                "price": round(float(price), 2),
                "change_rate": round(float(change_pct), 2),
                "volume": int(vol),
                "change_price": round(float(change), 2),
            })

        # 상승률 높은 순으로 정렬
        stocks.sort(key=lambda x: abs(x["change_rate"]), reverse=True)

        logger.info(f"Total unique surge stocks: {len(stocks)}, returning top {limit}")
        return stocks[:limit]

    return await _run_sync(_fetch)


async def get_penny_stocks_with_volume_pattern(limit: int = 50) -> list[dict]:
    """
    1달러 미만 주식 중:
    - 당일 거래량 급증 (전일 대비 2배 이상)
    - 최근 2일(D-1, D-2) 거래량이 당일(D-3) 이전보다 작은 주식 필터링
    """
    def _fetch():
        try:
            from yfinance.screener.screener import screen
            # day_gainers와 most_actives 모두 조회
            gainers = screen("day_gainers").get("quotes", [])
            actives = screen("most_actives").get("quotes", [])
            # 중복 제거
            all_stocks = {q["symbol"]: q for q in gainers + actives}.values()
        except Exception as e:
            logger.warning(f"yf.screener.screen failed: {e}")
            all_stocks = []

        results = []

        for q in all_stocks:
            symbol = q.get("symbol", "")
            price = q.get("regularMarketPrice", 0) or 0

            # 1달러 미만 필터
            if price >= 1.0 or price <= 0:
                continue

            try:
                # 최근 5일 데이터 조회
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="5d", interval="1d")

                if df.empty or len(df) < 4:
                    continue

                # 최근 4일의 거래량
                volumes = df["Volume"].tail(4).tolist()

                if len(volumes) < 4:
                    continue

                # D-3 (3일 전), D-2 (2일 전), D-1 (전일), D-0 (당일)
                vol_d3 = volumes[0]
                vol_d2 = volumes[1]
                vol_d1 = volumes[2]
                vol_d0 = volumes[3]  # 당일

                # 조건 1: 당일 거래량이 전일 대비 2배 이상 급증
                if vol_d0 < vol_d1 * 2:
                    continue

                # 조건 2: D-2와 D-1의 거래량이 D-3보다 작아야 함
                if not (vol_d2 < vol_d3 and vol_d1 < vol_d3):
                    continue

                # 조건 통과한 주식 추가
                name = q.get("shortName") or q.get("longName") or symbol
                change = q.get("regularMarketChange", 0) or 0
                change_pct = q.get("regularMarketChangePercent", 0) or 0

                results.append({
                    "code": symbol,
                    "name": name,
                    "price": round(float(price), 2),
                    "change_rate": round(float(change_pct), 2),
                    "volume": int(vol_d0),
                    "change_price": round(float(change), 2),
                    "volume_pattern": {
                        "d0": int(vol_d0),
                        "d1": int(vol_d1),
                        "d2": int(vol_d2),
                        "d3": int(vol_d3),
                        "surge_ratio": round(vol_d0 / vol_d1, 2) if vol_d1 > 0 else 0,
                    }
                })

            except Exception as e:
                logger.debug(f"Volume pattern check failed for {symbol}: {e}")
                continue

        # 거래량 급증 비율 높은 순으로 정렬
        results.sort(key=lambda x: x["volume_pattern"]["surge_ratio"], reverse=True)

        return results[:limit]

    return await _run_sync(_fetch)


async def get_us_daily_chart(symbol: str, days: int = 90) -> list[dict]:
    """yfinance로 미국 일봉 OHLCV 조회"""
    def _fetch():
        from datetime import datetime, timedelta
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days)
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_dt.strftime("%Y-%m-%d"),
                            end=end_dt.strftime("%Y-%m-%d"),
                            interval="1d")
        results = []
        for date, row in df.iterrows():
            if int(row.get("Volume", 0)) == 0:
                continue
            results.append({
                "time": date.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return results

    try:
        return await _run_sync(_fetch)
    except Exception as e:
        logger.error(f"US daily chart error for {symbol}: {e}")
        return []


async def get_us_weekly_chart(symbol: str) -> list[dict]:
    """yfinance로 미국 주봉 OHLCV 조회 (1년)"""
    def _fetch():
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y", interval="1wk")
        results = []
        for date, row in df.iterrows():
            if int(row.get("Volume", 0)) == 0:
                continue
            results.append({
                "time": date.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return results

    try:
        return await _run_sync(_fetch)
    except Exception as e:
        logger.error(f"US weekly chart error for {symbol}: {e}")
        return []


async def get_us_minute_chart(symbol: str) -> list[dict]:
    """yfinance로 미국 5분봉 조회 (당일)"""
    def _fetch():
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1d", interval="5m")
        results = []
        for ts, row in df.iterrows():
            if int(row.get("Volume", 0)) == 0:
                continue
            results.append({
                "time": ts.strftime("%Y-%m-%dT%H:%M:%S"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return results

    try:
        return await _run_sync(_fetch)
    except Exception as e:
        logger.error(f"US minute chart error for {symbol}: {e}")
        return []


async def get_us_fundamental(symbol: str) -> dict:
    """yfinance ticker.info에서 펀더멘털 데이터 수집"""
    def _fetch():
        ticker = yf.Ticker(symbol)
        info = ticker.info

        per = info.get("trailingPE") or info.get("forwardPE") or 999
        pbr = info.get("priceToBook") or 999
        roe = info.get("returnOnEquity") or 0
        if roe and roe < 1:
            roe = roe * 100  # decimal → percent
        eps = info.get("trailingEps") or 0
        bps = info.get("bookValue") or 0
        eps_growth = (info.get("earningsGrowth") or 0) * 100
        debt_to_equity = info.get("debtToEquity") or 0

        return {
            "per": float(per),
            "pbr": float(pbr),
            "roe": float(roe),
            "eps": float(eps),
            "bps": float(bps),
            "eps_growth": float(eps_growth),
            "net_loss": bool(float(eps) < 0),
            "high_debt": bool(float(debt_to_equity) > 300),
        }

    try:
        return await _run_sync(_fetch)
    except Exception as e:
        logger.error(f"US fundamental error for {symbol}: {e}")
        return {}


async def get_us_technical(symbol: str) -> dict:
    """yfinance 200일 일봉으로 기술적 지표 계산"""
    def _fetch():
        ticker = yf.Ticker(symbol)
        return ticker.history(period="200d", interval="1d")

    try:
        df = await _run_sync(_fetch)
    except Exception as e:
        logger.error(f"US technical error for {symbol}: {e}")
        return {}

    if df.empty or len(df) < 20:
        return {}

    closes = df["Close"].astype(float)

    ma20 = IndicatorEngine.calculate_ma(closes, 20)
    ma60 = IndicatorEngine.calculate_ma(closes, 60)
    ma120 = IndicatorEngine.calculate_ma(closes, 120)
    rsi = IndicatorEngine.calculate_rsi(closes, 14)
    returns = closes.pct_change().dropna()
    volatility = IndicatorEngine.calculate_volatility(returns, 20)

    return_60d = 0
    if len(closes) >= 60:
        return_60d = (closes.iloc[-1] / closes.iloc[-60] - 1) * 100

    return {
        "ma20": float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else None,
        "ma60": float(ma60.iloc[-1]) if pd.notna(ma60.iloc[-1]) else None,
        "ma120": float(ma120.iloc[-1]) if pd.notna(ma120.iloc[-1]) else None,
        "rsi": float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50,
        "volatility": float(volatility.iloc[-1]) if pd.notna(volatility.iloc[-1]) else 0,
        "return_60d": float(return_60d),
    }
