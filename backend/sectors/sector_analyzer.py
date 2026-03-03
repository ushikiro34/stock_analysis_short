"""
Sector Analysis Engine
섹터별 실시간 분석 및 모니터링
"""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

import pandas as pd

from .sector_config import SectorType, get_sector_symbols, SECTOR_NAMES_KR
from ..us.yfinance_client import get_us_daily_chart
from ..core.indicators import IndicatorEngine

logger = logging.getLogger(__name__)


class SectorAnalyzer:
    """섹터 분석 엔진"""

    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = 300  # 5분

    async def analyze_sector(self, sector: SectorType, days: int = 30) -> Dict:
        """
        섹터 전체 분석

        Args:
            sector: 섹터 타입
            days: 분석 기간 (일)

        Returns:
            {
                "sector": 섹터명,
                "sector_name": 한글 섹터명,
                "analyzed_at": 분석 시각,
                "summary": {
                    "total_stocks": 종목 수,
                    "avg_return": 평균 수익률,
                    "avg_volume_ratio": 평균 거래량 비율,
                    "bullish_count": 상승 종목 수,
                    "bearish_count": 하락 종목 수
                },
                "stocks": [종목별 상세 정보],
                "sector_strength": "strong" | "moderate" | "weak",
                "top_performers": [상위 3개 종목],
                "rotation_signal": "rotating_in" | "rotating_out" | "neutral"
            }
        """
        cache_key = f"{sector.value}:{days}"
        now = datetime.now().timestamp()

        # 캐시 확인
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if now - cached["ts"] < self.cache_ttl:
                return cached["data"]

        logger.info(f"[Sector] Analyzing {sector.value}...")

        symbols = get_sector_symbols(sector)
        stock_data = await self._collect_sector_data(symbols, days)

        # 섹터 요약 통계
        summary = self._calculate_sector_summary(stock_data)

        # 섹터 강도 평가
        sector_strength = self._evaluate_sector_strength(summary, stock_data)

        # 상위 종목
        top_performers = sorted(
            stock_data,
            key=lambda x: x.get("return_pct", 0),
            reverse=True
        )[:3]

        # 로테이션 신호
        rotation_signal = self._detect_rotation(summary, stock_data)

        result = {
            "sector": sector.value,
            "sector_name": SECTOR_NAMES_KR.get(sector, sector.value),
            "analyzed_at": datetime.now().isoformat(),
            "summary": summary,
            "stocks": stock_data,
            "sector_strength": sector_strength,
            "top_performers": top_performers,
            "rotation_signal": rotation_signal,
            "period_days": days
        }

        # 캐싱
        self.cache[cache_key] = {"data": result, "ts": now}

        return result

    async def _collect_sector_data(self, symbols: List[str], days: int) -> List[Dict]:
        """섹터 내 모든 종목 데이터 수집"""
        async def fetch_stock(symbol: str):
            try:
                # 일봉 데이터 조회
                daily_data = await get_us_daily_chart(symbol, days=days)

                if not daily_data or len(daily_data) < 5:
                    return None

                # DataFrame 변환
                df = pd.DataFrame(daily_data)
                df["time"] = pd.to_datetime(df["time"])
                df = df.set_index("time")
                df = df.sort_index()

                # 기본 정보
                current_price = df["close"].iloc[-1]
                prev_price = df["close"].iloc[-2] if len(df) > 1 else current_price
                start_price = df["close"].iloc[0]

                # 수익률 계산
                daily_return = ((current_price - prev_price) / prev_price * 100) if prev_price > 0 else 0
                period_return = ((current_price - start_price) / start_price * 100) if start_price > 0 else 0

                # 거래량 변화
                current_volume = df["volume"].iloc[-1]
                avg_volume = df["volume"].mean()
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

                # 기술적 지표
                closes = df["close"]
                ma20 = IndicatorEngine.calculate_ma(closes, 20)
                ma60 = IndicatorEngine.calculate_ma(closes, 60) if len(closes) >= 60 else None
                rsi = IndicatorEngine.calculate_rsi(closes, 14)

                current_ma20 = ma20.iloc[-1] if len(ma20) > 0 else None
                current_ma60 = ma60.iloc[-1] if ma60 is not None and len(ma60) > 0 else None
                current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50

                # 추세 판단
                trend = "neutral"
                if current_ma20 and current_ma60:
                    if current_price > current_ma20 > current_ma60:
                        trend = "uptrend"
                    elif current_price < current_ma20 < current_ma60:
                        trend = "downtrend"

                # 변동성
                returns = closes.pct_change().dropna()
                volatility = IndicatorEngine.calculate_volatility(returns, 20)
                current_volatility = volatility.iloc[-1] if len(volatility) > 0 else 0

                return {
                    "symbol": symbol,
                    "price": round(current_price, 2),
                    "daily_return": round(daily_return, 2),
                    "period_return": round(period_return, 2),
                    "volume": int(current_volume),
                    "volume_ratio": round(volume_ratio, 2),
                    "ma20": round(current_ma20, 2) if current_ma20 else None,
                    "ma60": round(current_ma60, 2) if current_ma60 else None,
                    "rsi": round(current_rsi, 1),
                    "trend": trend,
                    "volatility": round(current_volatility * 100, 2),
                    "last_updated": datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"[Sector] Failed to fetch {symbol}: {e}")
                return None

        # 병렬 수집
        tasks = [fetch_stock(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)

        # None 제거
        return [r for r in results if r is not None]

    def _calculate_sector_summary(self, stock_data: List[Dict]) -> Dict:
        """섹터 요약 통계 계산"""
        if not stock_data:
            return {
                "total_stocks": 0,
                "avg_return": 0,
                "avg_volume_ratio": 0,
                "bullish_count": 0,
                "bearish_count": 0,
                "avg_rsi": 50,
                "uptrend_count": 0,
                "downtrend_count": 0
            }

        returns = [s["period_return"] for s in stock_data]
        volume_ratios = [s["volume_ratio"] for s in stock_data]
        rsi_values = [s["rsi"] for s in stock_data]

        bullish = sum(1 for s in stock_data if s["period_return"] > 0)
        bearish = sum(1 for s in stock_data if s["period_return"] < 0)

        uptrend = sum(1 for s in stock_data if s["trend"] == "uptrend")
        downtrend = sum(1 for s in stock_data if s["trend"] == "downtrend")

        return {
            "total_stocks": len(stock_data),
            "avg_return": round(sum(returns) / len(returns), 2),
            "avg_volume_ratio": round(sum(volume_ratios) / len(volume_ratios), 2),
            "bullish_count": bullish,
            "bearish_count": bearish,
            "avg_rsi": round(sum(rsi_values) / len(rsi_values), 1),
            "uptrend_count": uptrend,
            "downtrend_count": downtrend
        }

    def _evaluate_sector_strength(self, summary: Dict, stock_data: List[Dict]) -> str:
        """
        섹터 강도 평가

        Returns:
            "strong" | "moderate" | "weak"
        """
        total = summary["total_stocks"]
        if total == 0:
            return "weak"

        # 상승 비율
        bullish_ratio = summary["bullish_count"] / total
        uptrend_ratio = summary["uptrend_count"] / total

        # 평균 수익률
        avg_return = summary["avg_return"]

        # 평균 RSI
        avg_rsi = summary["avg_rsi"]

        # 강도 점수
        score = 0

        if avg_return > 3:
            score += 3
        elif avg_return > 0:
            score += 1

        if bullish_ratio > 0.7:
            score += 3
        elif bullish_ratio > 0.5:
            score += 1

        if uptrend_ratio > 0.6:
            score += 2
        elif uptrend_ratio > 0.4:
            score += 1

        if 45 < avg_rsi < 70:
            score += 2
        elif avg_rsi > 70:
            score += 1  # 과매수 경고

        # 강도 판정
        if score >= 7:
            return "strong"
        elif score >= 4:
            return "moderate"
        else:
            return "weak"

    def _detect_rotation(self, summary: Dict, stock_data: List[Dict]) -> str:
        """
        섹터 로테이션 감지

        Returns:
            "rotating_in" | "rotating_out" | "neutral"
        """
        avg_return = summary["avg_return"]
        avg_volume = summary["avg_volume_ratio"]
        uptrend_ratio = summary["uptrend_count"] / summary["total_stocks"] if summary["total_stocks"] > 0 else 0

        # Rotating In: 수익률 상승 + 거래량 증가 + 상승 추세 많음
        if avg_return > 2 and avg_volume > 1.2 and uptrend_ratio > 0.6:
            return "rotating_in"

        # Rotating Out: 수익률 하락 + 거래량 증가 (매도 압력)
        if avg_return < -2 and avg_volume > 1.3:
            return "rotating_out"

        return "neutral"

    async def compare_sectors(self, sectors: List[SectorType], days: int = 30) -> Dict:
        """
        여러 섹터 비교 분석

        Returns:
            {
                "compared_at": 분석 시각,
                "period_days": 분석 기간,
                "sectors": [섹터별 요약],
                "strongest_sector": 가장 강한 섹터,
                "weakest_sector": 가장 약한 섹터,
                "rotating_sectors": {
                    "in": [자금 유입 섹터],
                    "out": [자금 유출 섹터]
                }
            }
        """
        # 병렬로 모든 섹터 분석
        tasks = [self.analyze_sector(sector, days) for sector in sectors]
        results = await asyncio.gather(*tasks)

        sector_summaries = []
        rotating_in = []
        rotating_out = []

        for result in results:
            sector_summaries.append({
                "sector": result["sector"],
                "sector_name": result["sector_name"],
                "avg_return": result["summary"]["avg_return"],
                "strength": result["sector_strength"],
                "rotation_signal": result["rotation_signal"]
            })

            if result["rotation_signal"] == "rotating_in":
                rotating_in.append(result["sector_name"])
            elif result["rotation_signal"] == "rotating_out":
                rotating_out.append(result["sector_name"])

        # 강도 순 정렬
        sorted_sectors = sorted(sector_summaries, key=lambda x: x["avg_return"], reverse=True)

        return {
            "compared_at": datetime.now().isoformat(),
            "period_days": days,
            "sectors": sorted_sectors,
            "strongest_sector": sorted_sectors[0] if sorted_sectors else None,
            "weakest_sector": sorted_sectors[-1] if sorted_sectors else None,
            "rotating_sectors": {
                "in": rotating_in,
                "out": rotating_out
            }
        }
