"""
Trading signals for day trading strategies.
진입/청산 신호 로직 구현
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import pandas as pd
import logging

from .indicators import IndicatorEngine

logger = logging.getLogger(__name__)


class SignalStrength:
    """신호 강도"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SignalType:
    """신호 타입"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


# ═══════════════════════════════════════════════════════════════
# 진입 신호 (Entry Signals)
# ═══════════════════════════════════════════════════════════════

class VolumeBreakoutSignal:
    """거래량 돌파 진입 신호"""

    def __init__(self, volume_surge_ratio: float = 2.0, price_increase_ratio: float = 0.02):
        self.volume_surge_ratio = volume_surge_ratio
        self.price_increase_ratio = price_increase_ratio

    def check_signal(self, ohlcv_data: pd.DataFrame) -> Dict:
        """
        거래량 돌파 신호 체크

        Args:
            ohlcv_data: OHLCV 데이터 (최소 6일 이상)
                       컬럼: Open, High, Low, Close, Volume

        Returns:
            {
                "signal": "BUY" | "HOLD",
                "strength": "high" | "medium" | "low",
                "score": 0-100,
                "reasons": [...]
            }
        """
        if len(ohlcv_data) < 6:
            return {"signal": SignalType.HOLD, "strength": SignalStrength.LOW, "score": 0, "reasons": []}

        # 최근 데이터
        latest = ohlcv_data.iloc[-1]
        prev = ohlcv_data.iloc[-2]

        current_volume = latest["Volume"]
        prev_volume = prev["Volume"]
        current_price = latest["Close"]
        prev_close = prev["Close"]

        # 거래량 5일 이동평균
        volume_ma5 = ohlcv_data["Volume"].tail(6).head(5).mean()

        reasons = []
        score = 0

        # 조건 1: 거래량 급증 (전일 대비)
        volume_surge = prev_volume > 0 and current_volume >= prev_volume * self.volume_surge_ratio
        if volume_surge:
            reasons.append(f"거래량 급증 ({current_volume / prev_volume:.2f}배)")
            score += 30

        # 조건 2: 가격 상승
        price_increase = prev_close > 0 and current_price > prev_close * (1 + self.price_increase_ratio)
        if price_increase:
            change_pct = (current_price - prev_close) / prev_close * 100
            reasons.append(f"가격 상승 (+{change_pct:.2f}%)")
            score += 25

        # 조건 3: 거래량 MA5 대비 급증
        volume_ma5_breakout = volume_ma5 > 0 and current_volume >= volume_ma5 * 3
        if volume_ma5_breakout:
            reasons.append(f"거래량 MA5 돌파 ({current_volume / volume_ma5:.2f}배)")
            score += 25

        # 조건 4: 전일 대비 거래대금 증가
        prev_amount = prev_volume * prev_close
        current_amount = current_volume * current_price
        if current_amount > prev_amount * 2:
            reasons.append("거래대금 2배 이상 증가")
            score += 20

        # ── Case 2: 전고점 돌파 시 거래량 확인 (일봉 가짜 돌파 감지) ──────
        # 최근 20일 고점 돌파 여부 판단, 돌파했다면 그날의 거래량과 비교
        if len(ohlcv_data) >= 21:
            recent_window = ohlcv_data.iloc[-21:-1]   # 당일 제외 20일
            recent_high_val = float(recent_window["High"].max())
            if current_price > recent_high_val:
                high_day_idx = recent_window["High"].idxmax()
                high_day_volume = float(recent_window.loc[high_day_idx, "Volume"])
                vol_vs_high = current_volume / high_day_volume if high_day_volume > 0 else 1.0
                if vol_vs_high < 0.8:
                    # 거래량이 전고점 날보다 적음 → 가짜 돌파 의심
                    reasons.append(
                        f"[가짜돌파 의심] 20일 고점 돌파 但 거래량 {vol_vs_high:.2f}배 미달"
                    )
                    score = max(0, score - 25)
                else:
                    # 거래량 확인된 진짜 돌파
                    reasons.append(f"전고점 돌파 + 거래량 확인 ({vol_vs_high:.2f}배)")
                    score = min(100, score + 10)

        # ── Case 1: 당일 급등 추격 방지 게이트 (≥5% 차단) ──────────────
        price_change_pct = (current_price - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
        chase_blocked = bool(price_change_pct >= 5.0)

        # 신호 강도 결정
        if chase_blocked:
            # 이미 급등 완료된 종목 — 추격 진입 차단
            reasons.append(f"[추격차단] 당일 +{price_change_pct:.1f}% 급등 (≥5%, 고점 진입 위험)")
            strength = SignalStrength.LOW
            signal = SignalType.HOLD
        elif score >= 70:
            strength = SignalStrength.HIGH
            signal = SignalType.BUY
        elif score >= 50:
            strength = SignalStrength.MEDIUM
            signal = SignalType.BUY
        else:
            strength = SignalStrength.LOW
            signal = SignalType.HOLD

        return {
            "signal": signal,
            "strength": strength,
            "score": score,
            "reasons": reasons,
            "volume_ratio": current_volume / prev_volume if prev_volume > 0 else 0,
            "price_change": price_change_pct / 100,
            "chase_blocked": chase_blocked,
        }


class TechnicalBreakoutSignal:
    """기술적 지표 돌파 진입 신호"""

    def check_signal(self, ohlcv_data: pd.DataFrame) -> Dict:
        """
        기술적 지표 돌파 신호 체크

        Args:
            ohlcv_data: OHLCV 데이터 (최소 120일 이상 권장)

        Returns:
            신호 정보 딕셔너리
        """
        if len(ohlcv_data) < 30:
            return {"signal": SignalType.HOLD, "strength": SignalStrength.LOW, "score": 0, "reasons": []}

        closes = ohlcv_data["Close"]
        highs = ohlcv_data["High"]
        lows = ohlcv_data["Low"]

        current_price = closes.iloc[-1]

        reasons = []
        score = 0

        # MA 계산
        ma20 = IndicatorEngine.calculate_ma(closes, 20)
        ma60 = IndicatorEngine.calculate_ma(closes, 60) if len(closes) >= 60 else None

        # 조건 1: 가격이 MA20 상향 돌파
        if len(ma20) > 1:
            prev_ma20 = ma20.iloc[-2]
            current_ma20 = ma20.iloc[-1]
            prev_price = closes.iloc[-2]

            ma20_breakout = current_price > current_ma20 and prev_price <= prev_ma20
            if ma20_breakout:
                reasons.append("MA20 상향 돌파")
                score += 25

            # MA 정배열
            if ma60 is not None and len(ma60) > 0:
                current_ma60 = ma60.iloc[-1]
                if current_ma20 > current_ma60:
                    reasons.append("MA20 > MA60 정배열")
                    score += 15

        # 조건 2: RSI 적정 범위 (30~70)
        rsi = IndicatorEngine.calculate_rsi(closes, 14)
        if len(rsi) > 0:
            current_rsi = rsi.iloc[-1]
            if 30 < current_rsi < 70:
                reasons.append(f"RSI 적정 범위 ({current_rsi:.1f})")
                score += 15

                # RSI 상승 추세
                if len(rsi) > 1:
                    prev_rsi = rsi.iloc[-2]
                    if current_rsi > prev_rsi:
                        reasons.append("RSI 상승 추세")
                        score += 10

        # 조건 3: MACD 골든크로스
        macd_data = IndicatorEngine.calculate_macd(closes)
        if len(macd_data["macd"]) > 1:
            macd = macd_data["macd"].iloc[-1]
            signal = macd_data["signal"].iloc[-1]
            prev_macd = macd_data["macd"].iloc[-2]
            prev_signal = macd_data["signal"].iloc[-2]

            golden_cross = macd > signal and prev_macd <= prev_signal
            if golden_cross:
                reasons.append("MACD 골든크로스")
                score += 30

        # 조건 4: 볼린저밴드 하단 터치 후 반등
        bb = IndicatorEngine.calculate_bollinger_bands(closes, 20)
        if len(bb["lower"]) > 1:
            bb_lower = bb["lower"].iloc[-1]
            bb_middle = bb["middle"].iloc[-1]
            prev_price = closes.iloc[-2]

            # 전일 하단 근접, 당일 중간선 향해 반등
            if prev_price <= bb_lower * 1.02 and current_price > bb_lower and current_price < bb_middle:
                reasons.append("볼린저밴드 하단 반등")
                score += 20

        # 조건 5: 스토캐스틱 모멘텀 방향 확인 (보너스 +10)
        # 과매도 탈출 여부가 아닌 "모멘텀이 살아있는 돌파"를 구분하는 용도
        # %K > %D (상승 방향) AND 20 < %K < 70 (극단 구간 제외)
        try:
            stoch = IndicatorEngine.calculate_stochastic(highs, lows, closes)
            stoch_k_series = stoch["k"].dropna()
            stoch_d_series = stoch["d"].dropna()
            if len(stoch_k_series) >= 2 and len(stoch_d_series) >= 1:
                stoch_k = float(stoch_k_series.iloc[-1])
                stoch_d = float(stoch_d_series.iloc[-1])
                if 20 < stoch_k < 70 and stoch_k > stoch_d:
                    reasons.append(f"스토캐스틱 상승 모멘텀 (%K {stoch_k:.1f} > %D {stoch_d:.1f})")
                    score += 10
        except Exception:
            pass

        # 신호 강도 결정
        if score >= 70:
            strength = SignalStrength.HIGH
            signal_type = SignalType.BUY
        elif score >= 50:
            strength = SignalStrength.MEDIUM
            signal_type = SignalType.BUY
        else:
            strength = SignalStrength.LOW
            signal_type = SignalType.HOLD

        return {
            "signal": signal_type,
            "strength": strength,
            "score": score,
            "reasons": reasons
        }


class RSIGoldenCrossSignal:
    """RSI 30 돌파 + MA50/200 골든크로스 진입 신호"""

    def check_signal(self, ohlcv_data: pd.DataFrame) -> Dict:
        """
        RSI 30 돌파 + 골든크로스 신호 체크

        조건:
        1. RSI가 30을 상향 돌파 (최근 5일 이내)
        2. MA50 > MA200 (골든크로스 상태)
        3. 거래량 증가 (평균 대비 1.2배 이상)

        점수 배분:
        - 골든크로스 유지: +40
        - RSI 30 돌파: +30
        - 거래량 급증: +20
        - MA50 상승 추세: +10
        - BUY 신호: 70점 이상

        Args:
            ohlcv_data: OHLCV 데이터 (최소 200일 이상 권장)

        Returns:
            {
                "signal": "BUY" | "HOLD",
                "strength": "high" | "medium" | "low",
                "score": 0-100,
                "reasons": [...]
            }
        """
        if len(ohlcv_data) < 200:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": 0,
                "reasons": ["데이터 부족 (최소 200일 필요)"]
            }

        closes = ohlcv_data["Close"]
        volumes = ohlcv_data["Volume"]

        current_price = closes.iloc[-1]
        current_volume = volumes.iloc[-1]

        reasons = []
        score = 0

        # 1. MA50, MA200 계산
        ma50 = IndicatorEngine.calculate_ma(closes, 50)
        ma200 = IndicatorEngine.calculate_ma(closes, 200)

        if len(ma50) == 0 or len(ma200) == 0:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": 0,
                "reasons": ["이동평균 계산 실패"]
            }

        current_ma50 = ma50.iloc[-1]
        current_ma200 = ma200.iloc[-1]

        # 조건 1: 골든크로스 확인 (MA50 > MA200)
        if current_ma50 > current_ma200:
            golden_cross_pct = (current_ma50 - current_ma200) / current_ma200 * 100 if current_ma200 > 0 else 0.0
            reasons.append(f"골든크로스 유지 (MA50 > MA200, +{golden_cross_pct:.2f}%)")
            score += 40

            # 골든크로스 발생 시점 확인 (최근 20일 이내)
            if len(ma50) > 20 and len(ma200) > 20:
                for i in range(1, min(21, len(ma50))):
                    if ma50.iloc[-i] > ma200.iloc[-i] and ma50.iloc[-i-1] <= ma200.iloc[-i-1]:
                        reasons.append(f"최근 골든크로스 발생 ({i}일 전)")
                        score += 10
                        break
        else:
            reasons.append("골든크로스 미발생 (MA50 < MA200)")
            # 골든크로스가 없으면 신호 약함
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": score,
                "reasons": reasons
            }

        # 2. RSI 30 돌파 확인
        rsi = IndicatorEngine.calculate_rsi(closes, 14)

        if len(rsi) < 5:
            reasons.append("RSI 데이터 부족")
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": score,
                "reasons": reasons
            }

        current_rsi = rsi.iloc[-1]

        # RSI가 30을 상향 돌파했는지 확인 (최근 5일 이내)
        rsi_breakout = False

        for i in range(1, min(6, len(rsi))):
            prev_rsi = rsi.iloc[-i]
            prev_prev_rsi = rsi.iloc[-i-1] if len(rsi) > i+1 else None

            # RSI가 30 아래에서 30 위로 돌파
            if prev_prev_rsi is not None and prev_prev_rsi <= 30 and prev_rsi > 30:
                rsi_breakout = True
                reasons.append(f"RSI 30 상향 돌파 ({i}일 전, 현재 RSI: {current_rsi:.1f})")
                score += 30
                break

        if not rsi_breakout:
            # RSI가 현재 30~50 사이에 있으면 부분 점수
            if 30 < current_rsi < 50:
                reasons.append(f"RSI 과매도 탈출 구간 (RSI: {current_rsi:.1f})")
                score += 15
            elif current_rsi >= 50:
                reasons.append(f"RSI 정상 범위 (RSI: {current_rsi:.1f})")
                score += 5
            else:
                reasons.append(f"RSI 과매도 구간 (RSI: {current_rsi:.1f})")

        # 3. 거래량 증가 확인
        volume_ma20 = volumes.tail(20).mean()
        volume_ratio = current_volume / volume_ma20 if volume_ma20 > 0 else 0

        if volume_ratio >= 2.0:
            reasons.append(f"거래량 급증 ({volume_ratio:.2f}배)")
            score += 20
        elif volume_ratio >= 1.2:
            reasons.append(f"거래량 증가 ({volume_ratio:.2f}배)")
            score += 10
        else:
            reasons.append(f"거래량 보통 ({volume_ratio:.2f}배)")

        # 4. MA50 상승 추세 확인
        if len(ma50) > 5:
            ma50_5days_ago = ma50.iloc[-6]
            if current_ma50 > ma50_5days_ago and ma50_5days_ago > 0:
                ma50_trend = (current_ma50 - ma50_5days_ago) / ma50_5days_ago * 100
                reasons.append(f"MA50 상승 추세 (+{ma50_trend:.2f}% 5일)")
                score += 10

        # 5. 현재 가격 위치 확인
        if current_price > current_ma50 and current_ma50 > 0:
            price_above_ma50 = (current_price - current_ma50) / current_ma50 * 100
            reasons.append(f"가격 MA50 상단 (+{price_above_ma50:.2f}%)")
            score += 5

        # 신호 강도 결정
        if score >= 70:
            strength = SignalStrength.HIGH
            signal_type = SignalType.BUY
        elif score >= 50:
            strength = SignalStrength.MEDIUM
            signal_type = SignalType.BUY
        else:
            strength = SignalStrength.LOW
            signal_type = SignalType.HOLD

        return {
            "signal": signal_type,
            "strength": strength,
            "score": score,
            "reasons": reasons,
            "rsi": current_rsi,
            "ma50": current_ma50,
            "ma200": current_ma200,
            "volume_ratio": volume_ratio
        }


class PricePatternSignal:
    """가격 패턴 진입 신호"""

    def detect_higher_lows(self, closes: pd.Series, window: int = 5) -> bool:
        """저점 높이기 패턴 감지"""
        if len(closes) < window * 2:
            return False

        # 최근 두 저점 찾기
        recent_data = closes.tail(window * 2)
        first_half = recent_data.head(window)
        second_half = recent_data.tail(window)

        first_low = first_half.min()
        second_low = second_half.min()

        return second_low > first_low

    def detect_pullback(self, ohlcv_data: pd.DataFrame) -> Dict:
        """
        눌림목(Pullback) 패턴 감지 — Fibonacci + MA20 소프트 채점 통합

        하드 게이트:
            1. MA20 > MA60 (상승 추세 필수)
            2. 조정 기간 감지 (2~10일 중 60% 이상 하락일)

        소프트 채점 (Phase 2 통합):
            3. 지지 구간 접촉: Fibonacci 38.2/50% 우선, MA20 fallback
               - near_fib + near_ma20 동시: +50 (강한 지지 수렴)
               - near_fib 단독:             +40 (피보나치 지지)
               - near_ma20 단독:            +25 (MA20 지지 fallback)
               - 둘 다 없음:               점수 미부여 (패턴 제외 안 함)
            4. 조정 거래량 감소: +20
            5. 반등 신호 (양봉 + 거래량 증가): +25
            6. 추세전환 위험 플래그 (이전 저점 하회)

        RSI < 30 처리 (Phase 2 수정):
            - 피보나치 61.8% 근처이면 반등 기대로 재해석 (+15)
            - 피보나치 지지 없으면 기존대로 위험 플래그

        Returns:
            {
                "is_pullback": bool,
                "score": int,
                "reasons": list,
                "is_reversal_risk": bool,
                "fib_levels": dict  # 계산된 피보나치 레벨
            }
        """
        if len(ohlcv_data) < 60:
            return {"is_pullback": False, "score": 0, "reasons": [], "is_reversal_risk": False}

        closes = ohlcv_data["Close"]
        volumes = ohlcv_data["Volume"]

        current = ohlcv_data.iloc[-1]
        current_price = float(current["Close"])
        current_volume = float(current["Volume"])

        reasons = []
        score = 0
        is_reversal_risk = False

        # ── 하드 게이트 1: 상승 추세 (MA20 > MA60) ─────────────────────────
        ma20 = IndicatorEngine.calculate_ma(closes, 20)
        ma60 = IndicatorEngine.calculate_ma(closes, 60)

        if len(ma20) == 0 or len(ma60) == 0:
            return {"is_pullback": False, "score": 0, "reasons": [], "is_reversal_risk": False}

        current_ma20 = float(ma20.iloc[-1])
        current_ma60 = float(ma60.iloc[-1])

        if current_ma20 <= current_ma60:
            return {
                "is_pullback": False, "score": 0,
                "reasons": ["MA20 < MA60: 상승 추세 미형성"],
                "is_reversal_risk": True,
            }

        reasons.append("상승 추세 유지 (MA20 > MA60)")
        score += 20

        # ── 하드 게이트 2: 조정 기간 감지 (2~10일) ──────────────────────────
        adjustment_detected = False
        adjustment_days = 0

        for lookback in range(2, 11):
            if len(closes) < lookback + 1:
                continue
            recent_closes = closes.tail(lookback + 1)
            declining_days = sum(
                1 for i in range(1, len(recent_closes))
                if recent_closes.iloc[i] < recent_closes.iloc[i - 1]
            )
            if declining_days >= lookback * 0.6:
                adjustment_detected = True
                adjustment_days = lookback
                break

        if not adjustment_detected:
            return {
                "is_pullback": False, "score": 0,
                "reasons": ["조정 패턴 없음"],
                "is_reversal_risk": False,
            }

        reasons.append(f"{adjustment_days}일 조정 기간 감지")
        score += 15

        # ── Phase 2: 피보나치 레벨 계산 (최근 60일 스윙 고/저점 기준) ─────
        fib_window = closes.tail(60)
        fib_high = float(fib_window.max())
        fib_low = float(fib_window.min())
        fib_range = fib_high - fib_low
        fib_levels = {}

        if fib_range > 0:
            fib_levels = {
                "382": fib_high - fib_range * 0.382,
                "500": fib_high - fib_range * 0.500,
                "618": fib_high - fib_range * 0.618,
            }

        # ── 소프트 채점 3: 지지 구간 접촉 (Fib 우선, MA20 fallback) ─────────
        PROXIMITY = 0.03  # ±3% 이내를 "터치"로 판단

        near_fib382 = fib_levels and abs(current_price - fib_levels["382"]) / current_price < PROXIMITY
        near_fib500 = fib_levels and abs(current_price - fib_levels["500"]) / current_price < PROXIMITY
        near_fib = near_fib382 or near_fib500
        near_ma20 = abs(current_price - current_ma20) / current_ma20 < PROXIMITY

        # MA20 10% 이상 이탈 시 추세전환 위험 (유일하게 남겨둔 하드 체크)
        if current_price < current_ma20 * 0.90 and not near_fib:
            return {
                "is_pullback": False, "score": 0,
                "reasons": ["MA20 10% 이상 이탈 + 피보나치 지지 없음: 추세전환 위험"],
                "is_reversal_risk": True,
                "fib_levels": fib_levels,
            }

        if near_fib and near_ma20:
            fib_label = "38.2%" if near_fib382 else "50.0%"
            reasons.append(f"피보나치 {fib_label} + MA20 지지 수렴 (강한 지지)")
            score += 50
        elif near_fib:
            fib_label = "38.2%" if near_fib382 else "50.0%"
            reasons.append(f"피보나치 {fib_label} 지지 구간 접촉")
            score += 40
        elif near_ma20 and current_ma20 > 0:
            dist = abs(current_price - current_ma20) / current_ma20 * 100
            reasons.append(f"MA20 지지선 터치 (거리: {dist:.1f}%)")
            score += 25

        # ── 소프트 채점 4: 조정 기간 거래량 감소 ────────────────────────────
        adj_period = ohlcv_data.tail(adjustment_days + 1).head(adjustment_days)
        before_period = ohlcv_data.tail(adjustment_days * 2 + 1).head(adjustment_days)
        adj_avg_vol = float(adj_period["Volume"].mean())
        before_avg_vol = float(before_period["Volume"].mean())

        if before_avg_vol > 0 and adj_avg_vol < before_avg_vol:
            reasons.append(f"조정 기간 거래량 감소 ({adj_avg_vol / before_avg_vol:.2f}배)")
            score += 20

        # ── 소프트 채점 5: 반등 신호 (양봉 + 거래량 증가) ──────────────────
        is_bullish_candle = current_price > float(current["Open"])
        if is_bullish_candle:
            reasons.append("당일 양봉")
            score += 10

        prev_volume = float(volumes.iloc[-2])
        if current_volume > prev_volume:
            reasons.append(f"거래량 증가 ({current_volume / prev_volume:.2f}배)")
            score += 15

        # ── 추세전환 위험 체크 ───────────────────────────────────────────────
        # 이전 저점 하회
        recent_low = float(ohlcv_data.tail(20)["Low"].iloc[:-1].min())
        if current_price < recent_low:
            is_reversal_risk = True
            reasons.append("⚠️ 이전 저점 하회: 추세전환 위험")

        # RSI < 30 처리 — 피보나치 61.8% 근처이면 반등 기대로 재해석
        rsi = IndicatorEngine.calculate_rsi(closes, 14)
        if len(rsi) > 0:
            current_rsi = float(rsi.iloc[-1])
            if current_rsi < 30:
                near_fib618 = (
                    fib_levels and
                    abs(current_price - fib_levels["618"]) / current_price < PROXIMITY
                )
                if near_fib618:
                    reasons.append(f"피보나치 61.8% + RSI 극과매도 ({current_rsi:.1f}) → 강한 반등 기대")
                    score += 15
                else:
                    is_reversal_risk = True
                    reasons.append(f"⚠️ RSI 과매도 ({current_rsi:.1f}): 추세전환 위험")

        is_pullback = score >= 60 and not is_reversal_risk

        return {
            "is_pullback": is_pullback,
            "score": score,
            "reasons": reasons,
            "is_reversal_risk": is_reversal_risk,
            "adjustment_days": adjustment_days,
            "fib_levels": fib_levels,
        }

    def detect_consolidation_breakout(self, ohlcv_data: pd.DataFrame, consolidation_days: int = 5) -> bool:
        """횡보 후 돌파 패턴 감지"""
        if len(ohlcv_data) < consolidation_days + 1:
            return False

        # 횡보 구간 (최근 N일)
        consolidation = ohlcv_data.tail(consolidation_days + 1).head(consolidation_days)
        current = ohlcv_data.iloc[-1]

        # 횡보 구간의 고가/저가 범위
        consolidation_high = consolidation["High"].max()
        consolidation_low = consolidation["Low"].min()
        if consolidation_low <= 0:
            return False
        consolidation_range = (consolidation_high - consolidation_low) / consolidation_low

        # 횡보 조건: 변동폭 5% 이내
        if consolidation_range > 0.05:
            return False

        # 돌파 조건: 당일 종가가 횡보 고가 돌파
        if current["Close"] <= consolidation_high * 1.02:
            return False

        # Case 2: 횡보 돌파 거래량 확인 — 평균 거래량 미달 시 가짜 돌파
        consolidation_avg_vol = consolidation["Volume"].mean()
        if consolidation_avg_vol > 0 and current["Volume"] < consolidation_avg_vol:
            return False  # 거래량 미확인 → 가짜 돌파 의심

        return True

    def detect_cup_and_handle(self, ohlcv_data: pd.DataFrame) -> Dict:
        """컵앤핸들(Cup & Handle) 패턴 감지

        구조:
            좌측 림 → U자 바닥 → 우측 림 (컵, 15~70일)
                    → 소폭 눌림 (핸들, 5~15일) → 우측 림 돌파 (진입 신호)

        조건:
            1. 컵 깊이: 15~50% (너무 얕거나 깊은 것 제외)
            2. 우측 림: 좌측 림의 90~115% 수준 회복
            3. 핸들 조정: 컵 깊이의 50% 이내 (소폭 눌림)
            4. 핸들 거래량: 컵 구간 대비 감소 (조용한 조정)
            5. 돌파: 현재가 ≥ 우측 림 × 0.99 + 거래량 급증

        점수 구조:
            컵 형성:           +25
            핸들 형성:         +20
            핸들 거래량 감소:   +15
            U자 바닥 형태:     +10
            우측 림 돌파:      +25
            돌파 거래량 확인:   +20
            is_cup_handle: True → score >= 60

        Returns:
            {"is_cup_handle": bool, "score": int, "reasons": list, ...}
        """
        if len(ohlcv_data) < 60:
            return {"is_cup_handle": False, "score": 0, "reasons": ["데이터 부족 (최소 60일)"]}

        closes = ohlcv_data["Close"].values
        volumes = ohlcv_data["Volume"].values
        n = len(closes)

        # 최근 90일로 제한 (오래된 패턴은 신뢰도 낮음)
        start = max(0, n - 90)
        c = closes[start:]
        v = volumes[start:]
        total = len(c)

        best: Optional[Dict] = None

        for handle_days in range(5, 16):
            cup_end = total - handle_days
            if cup_end < 15:
                continue

            cup = c[:cup_end]
            handle = c[cup_end:]
            handle_vol = v[cup_end:]
            cup_n = len(cup)

            # ── 좌측 림: 전반부 1/3의 최고점 ──────────────────────────
            left_n = max(1, cup_n // 3)
            left_rim = float(cup[:left_n].max())
            left_rim_pos = int(cup[:left_n].argmax())

            # ── 바닥: 좌측 림 이후 최저점 ──────────────────────────────
            after_left = cup[left_rim_pos:]
            if len(after_left) < 5:
                continue
            bottom = float(after_left.min())
            bottom_rel = int(after_left.argmin())
            bottom_pos = left_rim_pos + bottom_rel

            # ── 우측 림: 바닥 이후 최고점 ──────────────────────────────
            after_bottom = cup[bottom_pos:]
            if len(after_bottom) < 3:
                continue
            right_rim = float(after_bottom.max())

            # ── 컵 깊이 검증 (15~50%) ──────────────────────────────────
            cup_depth = (left_rim - bottom) / left_rim if left_rim > 0 else 0
            if not (0.15 <= cup_depth <= 0.50):
                continue

            # ── 우측 림 높이 검증 (좌측 림의 90~115%) ──────────────────
            rim_ratio = right_rim / left_rim if left_rim > 0 else 0
            if not (0.90 <= rim_ratio <= 1.15):
                continue

            # ── 핸들 조정폭 검증 (컵 깊이의 50% 이내) ──────────────────
            if len(handle) < 3:
                continue
            handle_low = float(handle.min())
            handle_retrace = (right_rim - handle_low) / (right_rim - bottom) if (right_rim - bottom) > 0 else 1.0
            if handle_retrace > 0.50:
                continue

            # ── 점수 계산 ───────────────────────────────────────────────
            this_score = 0
            this_reasons = []

            # 1. 컵 형성 (+25)
            this_score += 25
            this_reasons.append(f"컵 형성 (깊이 {cup_depth*100:.1f}%, 우측 림 {rim_ratio*100:.1f}%)")

            # 2. 핸들 형성 (+20)
            this_score += 20
            this_reasons.append(f"핸들 형성 ({handle_days}일, 조정 {handle_retrace*100:.1f}%)")

            # 3. 핸들 거래량 감소 (+15)
            cup_avg_vol = float(v[left_rim_pos:cup_end].mean()) if cup_end > left_rim_pos else 1.0
            handle_avg_vol = float(handle_vol.mean()) if len(handle_vol) > 0 else 0.0
            if handle_avg_vol < cup_avg_vol:
                this_score += 15
                this_reasons.append("핸들 거래량 감소 (조용한 눌림)")

            # 4. U자 바닥 형태 (+10): 바닥 전후 5봉 변동폭 < 5%
            b0 = max(0, bottom_pos - 5)
            b1 = min(cup_n, bottom_pos + 6)
            bottom_region = cup[b0:b1]
            if len(bottom_region) >= 3:
                br = (float(bottom_region.max()) - float(bottom_region.min())) / left_rim
                if br < 0.05:
                    this_score += 10
                    this_reasons.append("U자 바닥 형태 확인")

            # 5. 돌파 상태 판단 (신선도 포함)
            current_price = float(closes[-1])
            current_vol = float(volumes[-1])
            vol_ma20 = float(volumes[-20:].mean()) if n >= 20 else float(volumes.mean())
            vol_ratio = current_vol / vol_ma20 if vol_ma20 > 0 else 0

            if current_price > right_rim * 1.15:
                # 우측 림 대비 15% 초과 상승 → 돌파 완료 후 한참 지남
                breakout_status = "expired"
                expired_pct = (current_price / right_rim - 1) * 100
                this_reasons.append(f"⚠️ 진입 기회 소멸 (우측 림 {right_rim:,.0f}원 대비 현재 +{expired_pct:.0f}%)")
            elif current_price >= right_rim * 0.99:
                # 신선한 돌파 (우측 림 ~ +15%)
                breakout_status = "fresh"
                this_score += 25
                this_reasons.append(f"우측 림 돌파 ({right_rim:,.0f}원)")
                if vol_ratio >= 1.5:
                    this_score += 20
                    this_reasons.append(f"돌파 거래량 확인 ({vol_ratio:.1f}배)")
            elif current_price >= right_rim * 0.95:
                # 돌파 임박 (우측 림 -5% 이내 접근)
                breakout_status = "pre"
                approach_pct = (current_price / right_rim - 1) * 100
                this_score += 15
                this_reasons.append(f"우측 림 접근 중 ({right_rim:,.0f}원, {approach_pct:.1f}%)")
            elif current_price < right_rim * 0.88:
                # 우측 림보다 12% 이상 하락 → 핸들 지지선 이탈, 패턴 소멸
                breakout_status = "failed"
                decline_pct = (1 - current_price / right_rim) * 100
                this_reasons.append(
                    f"⚠️ 컵앤핸들 패턴 소멸 (우측 림 {right_rim:,.0f}원 대비 -{decline_pct:.1f}% 이탈)"
                )
            else:
                # 패턴 형성 중 (우측 림 -12% ~ -5% 구간)
                breakout_status = "forming"

            if best is None or this_score > best["score"]:
                best = {
                    "score": this_score,
                    "reasons": this_reasons,
                    "handle_days": handle_days,
                    "left_rim": left_rim,
                    "right_rim": right_rim,
                    "bottom": bottom,
                    "cup_depth": cup_depth,
                    "breakout_status": breakout_status,
                    "vol_ratio": vol_ratio,
                }

        if best is None or best["score"] < 40:
            return {
                "is_cup_handle": False,
                "score": best["score"] if best else 0,
                "reasons": ["컵앤핸들 패턴 미감지"],
            }

        breakout_status = best["breakout_status"]
        # fresh(신선 돌파) 또는 pre(임박) 상태만 유효한 진입 패턴으로 인정
        is_valid_entry = breakout_status in ("fresh", "pre")
        return {
            "is_cup_handle": best["score"] >= 60 and is_valid_entry,
            "score": best["score"],
            "reasons": [f"☕ 컵앤핸들 패턴 ({best['handle_days']}일 핸들)"] + best["reasons"],
            "left_rim": round(best["left_rim"]),
            "right_rim": round(best["right_rim"]),
            "bottom": round(best["bottom"]),
            "cup_depth_pct": round(best["cup_depth"] * 100, 1),
            "handle_days": best["handle_days"],
            "breakout_status": breakout_status,
        }

    # ──────────────────────────────────────────────────────────────
    # 급등 전 시그널 감지 (Pre-Surge Detection)
    # ──────────────────────────────────────────────────────────────

    def detect_volume_dryup_recovery(self, ohlcv_data: pd.DataFrame,
                                      dryup_ratio: float = 0.5,
                                      recovery_ratio: float = 0.8,
                                      min_dryup_days: int = 5) -> Dict:
        """거래량 건조 후 첫 회복일 감지

        패턴: N일 연속 거래량 건조(vol < MA20×dryup_ratio) 후
              최근 1~3일 내 첫 거래량 회복(vol ≥ MA20×recovery_ratio)

        Args:
            dryup_ratio:    건조 판정 임계값 (기본 0.5 = MA20의 50%)
            recovery_ratio: 회복 판정 임계값 (기본 0.8 = MA20의 80%)
            min_dryup_days: 최소 건조 연속 일수 (기본 5일)

        Returns:
            {
                "detected": bool,
                "score": int,
                "reasons": list,
                "dryup_days": int,       # 건조 지속 일수
                "vol_ratio_at_recovery": float,  # 회복일 거래량/MA20
                "extreme_dryup": bool,   # 극단 건조 여부 (vol < MA20×0.3)
            }
        """
        result = {"detected": False, "score": 0, "reasons": [], "dryup_days": 0,
                  "vol_ratio_at_recovery": 0.0, "extreme_dryup": False}

        if len(ohlcv_data) < 30:
            return result

        volumes = ohlcv_data["Volume"].values
        n = len(volumes)

        # 기준선: MA60 (없으면 전체 평균) — 건조 구간에 의해 왜곡되지 않는 장기 평균
        vol_series = pd.Series(volumes)
        vol_ma60 = vol_series.rolling(60, min_periods=20).mean().values

        def _baseline(idx: int) -> float:
            """해당 시점의 거래량 기준선 (MA60 or fallback)"""
            ma = vol_ma60[idx]
            if pd.isna(ma) or ma == 0:
                return float(vol_series.iloc[:idx + 1].mean())
            return float(ma)

        # 최근 3일 이내 회복일이 있는지 확인 (인덱스 -3, -2, -1)
        recovery_idx = None
        for offset in range(1, 4):
            idx = n - offset
            if idx < 20:
                break
            base = _baseline(idx)
            if base == 0:
                continue
            ratio = volumes[idx] / base
            if ratio >= recovery_ratio:
                recovery_idx = idx
                result["vol_ratio_at_recovery"] = round(ratio, 2)
                break

        if recovery_idx is None:
            return result

        # 회복일 직전에 N일 연속 건조 구간이 있는지 확인
        dryup_count = 0
        extreme_count = 0
        for i in range(recovery_idx - 1, max(recovery_idx - 40, 19), -1):
            base = _baseline(i)
            if base == 0:
                break
            ratio_i = volumes[i] / base
            if ratio_i < dryup_ratio:
                dryup_count += 1
                if ratio_i < 0.3:
                    extreme_count += 1
            else:
                break  # 건조 구간 끊김

        if dryup_count < min_dryup_days:
            return result

        result["detected"] = True
        result["dryup_days"] = dryup_count
        result["extreme_dryup"] = extreme_count >= 3

        # 점수 산정
        score = 30  # 기본: 건조 후 첫 회복
        if dryup_count >= 10:
            score += 15
            result["reasons"].append(f"장기 거래량 건조 ({dryup_count}일) 후 첫 회복")
        elif dryup_count >= 7:
            score += 10
            result["reasons"].append(f"중기 거래량 건조 ({dryup_count}일) 후 첫 회복")
        else:
            result["reasons"].append(f"거래량 건조 ({dryup_count}일) 후 첫 회복")

        if result["extreme_dryup"]:
            score += 15
            result["reasons"].append(f"극단 거래량 건조 포함 (< MA20×0.3, {extreme_count}일)")

        if result["vol_ratio_at_recovery"] >= 1.5:
            score += 10
            result["reasons"].append(f"강한 거래량 회복 (×{result['vol_ratio_at_recovery']:.2f})")
        elif result["vol_ratio_at_recovery"] >= 1.0:
            score += 5
            result["reasons"].append(f"거래량 회복 (×{result['vol_ratio_at_recovery']:.2f})")

        result["score"] = min(score, 70)
        return result

    def detect_seoryuk_accumulation(self, ohlcv_data: pd.DataFrame,
                                     extreme_ratio: float = 0.3,
                                     spike_ratio: float = 2.0,
                                     lookback: int = 20) -> Dict:
        """세력 매집 패턴 감지: 극단 건조 후 갑작스러운 거래량 폭발

        패턴: lookback일 내 극단 건조(vol < MA20×extreme_ratio) 구간이 존재하고,
              최근 1~2일 내 거래량 폭발(vol ≥ MA20×spike_ratio)

        Returns:
            {
                "detected": bool,
                "score": int,
                "reasons": list,
                "spike_ratio": float,   # 최근 거래량 폭발 배율
                "dryup_min_ratio": float,  # 건조 구간 최저 배율
            }
        """
        result = {"detected": False, "score": 0, "reasons": [],
                  "spike_ratio": 0.0, "dryup_min_ratio": 0.0}

        if len(ohlcv_data) < 30:
            return result

        volumes = ohlcv_data["Volume"].values
        closes  = ohlcv_data["Close"].values
        n = len(volumes)

        # 기준선: MA60 — 건조 구간에 의해 왜곡되지 않는 장기 평균
        vol_series = pd.Series(volumes)
        vol_ma60 = vol_series.rolling(60, min_periods=20).mean().values

        def _baseline(idx: int) -> float:
            ma = vol_ma60[idx]
            if pd.isna(ma) or ma == 0:
                return float(vol_series.iloc[:idx + 1].mean())
            return float(ma)

        # 1) 최근 1~2일 내 거래량 폭발 확인
        spike_idx = None
        actual_spike_ratio = 0.0
        for offset in range(1, 3):
            idx = n - offset
            if idx < 20:
                break
            base = _baseline(idx)
            if base == 0:
                continue
            r = volumes[idx] / base
            if r >= spike_ratio:
                spike_idx = idx
                actual_spike_ratio = round(r, 2)
                break

        if spike_idx is None:
            return result

        # spike 당일 등락률 확인
        if spike_idx >= 1 and closes[spike_idx - 1] != 0:
            spike_chg = (closes[spike_idx] - closes[spike_idx - 1]) / closes[spike_idx - 1]
            # +5% 이상 급등일 → 이미 급등 완료, 추격 차단
            if spike_chg >= 0.05:
                return result
            # 하락일(-1% 이하) 고거래량 → 분산/매도세, 매집 아님
            if spike_chg <= -0.01:
                return result

        # 최근 15일 내 +15% 이상 급등일이 있으면 → 이미 급등 사이클 완료
        lookback_start = max(spike_idx - 15, 1)
        for i in range(lookback_start, spike_idx + 1):
            if closes[i - 1] == 0:
                continue
            if (closes[i] - closes[i - 1]) / closes[i - 1] >= 0.15:
                return result

        # 2) 폭발 직전 lookback일 내 극단 건조 구간 존재 확인
        search_start = max(spike_idx - lookback, 20)
        extreme_days = []
        for i in range(search_start, spike_idx):
            base = _baseline(i)
            if base == 0:
                continue
            r = volumes[i] / base
            if r < extreme_ratio:
                extreme_days.append(r)

        if len(extreme_days) < 3:
            return result

        dryup_min = min(extreme_days)
        result["detected"] = True
        result["spike_ratio"] = actual_spike_ratio
        result["dryup_min_ratio"] = round(dryup_min, 3)

        # 폭발일 가격 변화
        if spike_idx >= 1 and closes[spike_idx - 1] != 0:
            price_chg = (closes[spike_idx] - closes[spike_idx - 1]) / closes[spike_idx - 1] * 100
        else:
            price_chg = 0.0

        score = 35
        if actual_spike_ratio >= 5.0:
            score += 20
            result["reasons"].append(f"극단 거래량 폭발 (MA20×{actual_spike_ratio:.1f}배)")
        elif actual_spike_ratio >= 3.0:
            score += 10
            result["reasons"].append(f"거래량 폭발 (MA20×{actual_spike_ratio:.1f}배)")
        else:
            result["reasons"].append(f"거래량 급증 (MA20×{actual_spike_ratio:.1f}배)")

        if len(extreme_days) >= 7:
            score += 15
            result["reasons"].append(f"세력 매집 의심: 장기 극단 건조({len(extreme_days)}일) 후 폭발")
        else:
            result["reasons"].append(f"세력 매집 의심: 극단 건조({len(extreme_days)}일) 후 폭발")

        if price_chg > 0:
            result["reasons"].append(f"폭발일 가격 상승 (+{price_chg:.1f}%)")
            if price_chg >= 3:
                score += 10

        result["score"] = min(score, 80)
        return result

    def detect_tight_consolidation(self, ohlcv_data: pd.DataFrame,
                                    window: int = 10,
                                    range_pct_threshold: float = 0.08) -> Dict:
        """타이트 횡보(에너지 압축) 감지

        패턴: 최근 window일 가격 범위 < range_pct_threshold (기본 8%) + 거래량 감소

        Returns:
            {
                "detected": bool,
                "score": int,
                "reasons": list,
                "range_pct": float,     # 횡보 구간 변동폭 (%)
                "vol_trend": str,       # "shrinking" | "flat" | "expanding"
            }
        """
        result = {"detected": False, "score": 0, "reasons": [], "range_pct": 0.0, "vol_trend": "flat"}

        if len(ohlcv_data) < window + 20:
            return result

        recent = ohlcv_data.tail(window)
        high = float(recent["High"].max())
        low  = float(recent["Low"].min())

        if low <= 0:
            return result

        range_pct = (high - low) / low
        result["range_pct"] = round(range_pct * 100, 2)

        if range_pct > range_pct_threshold:
            return result

        # 거래량 추세: 전반부 vs 후반부
        half = window // 2
        vol_first = float(recent["Volume"].head(half).mean())
        vol_last  = float(recent["Volume"].tail(half).mean())

        if vol_first > 0:
            vol_ratio = vol_last / vol_first
            if vol_ratio < 0.85:
                result["vol_trend"] = "shrinking"
            elif vol_ratio > 1.15:
                result["vol_trend"] = "expanding"
            else:
                result["vol_trend"] = "flat"
        else:
            vol_ratio = 1.0

        result["detected"] = True
        score = 25
        result["reasons"].append(
            f"에너지 압축 횡보: {window}일 가격 범위 {result['range_pct']:.1f}% (< {range_pct_threshold*100:.0f}%)"
        )

        if result["vol_trend"] == "shrinking":
            score += 20
            result["reasons"].append(f"횡보 중 거래량 감소 (후반/전반 {vol_ratio:.2f}배)")
        elif result["vol_trend"] == "flat":
            score += 5
            result["reasons"].append("횡보 중 거래량 유지")

        if range_pct < 0.04:
            score += 15
            result["reasons"].append(f"초타이트 횡보 (범위 {result['range_pct']:.1f}%)")

        result["score"] = min(score, 60)
        return result

    # ──────────────────────────────────────────────────────────────
    # 캔들 해부 + 거래량 조합 분석 (Candle-Volume Analysis)
    # ──────────────────────────────────────────────────────────────

    def detect_candle_volume_resistance(self, ohlcv_data: pd.DataFrame,
                                         lookback: int = 10) -> Dict:
        """저항 캔들 식별 + 버팀 진입 신호 감지

        이미지 기반 로직:
          ① 윗꼬리 비율 높은 캔들 + 강한 거래량 = 저항 구간 (상방 힘 부족)
          ② 밑꼬리 + 긴 몸통(버팀) 캔들에서 저항 거래량 돌파 = 진입 신호
          ⑤ 저항 거래량 미달 상태로 저항가 근처 도달 = 익절/관망 신호

        Returns:
            {
                "resistance_candles": [{"index": int, "price": float, "volume": float,
                                        "upper_shadow_ratio": float}],
                "max_resistance_volume": float,   # 저항 캔들 중 최대 거래량 (기준값)
                "resistance_price": float,        # 저항 가격대
                "entry_signal": bool,             # 버팀 캔들 + 저항 거래량 돌파 여부
                "entry_strength": str,            # "strong" | "normal" | "none"
                "fake_breakout_risk": bool,       # 저항가 근처 but 거래량 미달
                "score": int,
                "reasons": list,
            }
        """
        result = {
            "resistance_candles": [],
            "max_resistance_volume": 0.0,
            "resistance_price": 0.0,
            "entry_signal": False,
            "entry_strength": "none",
            "fake_breakout_risk": False,
            "score": 0,
            "reasons": [],
        }

        if len(ohlcv_data) < max(lookback + 2, 10):
            return result

        # 현재 캔들 (진입 판단 대상)
        cur = ohlcv_data.iloc[-1]
        cur_o = float(cur["Open"])
        cur_h = float(cur["High"])
        cur_l = float(cur["Low"])
        cur_c = float(cur["Close"])
        cur_v = float(cur["Volume"])

        cur_range = cur_h - cur_l
        if cur_range <= 0:
            return result

        # 현재 캔들 해부
        cur_body      = abs(cur_c - cur_o)
        cur_upper     = cur_h - max(cur_o, cur_c)
        cur_lower     = min(cur_o, cur_c) - cur_l
        cur_body_r    = cur_body / cur_range          # 몸통 비율
        cur_upper_r   = cur_upper / cur_range         # 윗꼬리 비율
        cur_lower_r   = cur_lower / cur_range         # 밑꼬리 비율
        cur_is_bull   = cur_c > cur_o                 # 양봉 여부

        # 거래량 기준: 직전 lookback일 평균
        window = ohlcv_data.iloc[-(lookback + 1):-1]
        vol_avg = float(window["Volume"].mean()) if len(window) > 0 else 1.0

        # ── ① 저항 캔들 탐색 (lookback 봉 내에서) ──────────────────
        resistance_candles = []
        for i in range(-(lookback + 1), -1):
            row = ohlcv_data.iloc[i]
            o, h, l, c, v = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"]), float(row["Volume"])
            rng = h - l
            if rng <= 0 or v <= 0:
                continue
            upper = h - max(o, c)
            body  = abs(c - o)
            upper_r = upper / rng
            body_r  = body / rng

            # 저항 캔들 조건: 윗꼬리 비율 40% 이상 + 거래량 평균 이상
            if upper_r >= 0.40 and v >= vol_avg * 0.8:
                resistance_candles.append({
                    "index": i,
                    "price": float(h),            # 저항 고점
                    "close": float(c),
                    "volume": float(v),
                    "upper_shadow_ratio": round(upper_r, 3),
                    "body_ratio": round(body_r, 3),
                })

        result["resistance_candles"] = resistance_candles

        if not resistance_candles:
            # 저항 캔들 없음 → 캔들 해부 스코어만 부여
            if cur_is_bull and cur_lower_r >= 0.25 and cur_body_r >= 0.35:
                result["reasons"].append(
                    f"버팀 양봉 확인 (몸통 {cur_body_r:.0%}, 밑꼬리 {cur_lower_r:.0%})"
                )
                result["entry_signal"] = True
                result["entry_strength"] = "normal"
                result["score"] = 20
            return result

        # 최대 저항 거래량 + 저항 가격
        max_res_vol   = max(rc["volume"] for rc in resistance_candles)
        res_price_ref = max(rc["price"]  for rc in resistance_candles)
        result["max_resistance_volume"] = max_res_vol
        result["resistance_price"]      = res_price_ref

        # ── ⑤ 가짜 돌파 위험: 현재가가 저항가 ±3% 내인데 거래량 미달 ──
        near_resistance = abs(cur_c - res_price_ref) / res_price_ref < 0.03
        vol_below_resistance = cur_v < max_res_vol * 0.8

        if near_resistance and vol_below_resistance:
            result["fake_breakout_risk"] = True
            result["reasons"].append(
                f"[가짜돌파 위험] 저항가 {res_price_ref:,.0f} 근처 + "
                f"거래량 미달 ({cur_v/max_res_vol:.1%})"
            )
            result["score"] = -15   # 페널티

        # ── ② 버팀 진입 신호: 밑꼬리+긴몸통 양봉 + 저항 거래량 돌파 ──
        is_persistence_candle = (
            cur_is_bull
            and cur_lower_r >= 0.25    # 밑꼬리 25% 이상 (버팀)
            and cur_body_r  >= 0.35    # 몸통 35% 이상 (결정력)
        )

        if is_persistence_candle:
            vol_vs_resistance = cur_v / max_res_vol if max_res_vol > 0 else 0
            if vol_vs_resistance >= 1.0:
                result["entry_signal"] = True
                result["entry_strength"] = "strong" if vol_vs_resistance >= 1.3 else "normal"
                result["reasons"].append(
                    f"버팀 양봉 + 저항 거래량 돌파 "
                    f"({vol_vs_resistance:.1%}, 저항가 {res_price_ref:,.0f})"
                )
                result["score"] = max(result["score"], 0) + (40 if result["entry_strength"] == "strong" else 25)
            elif vol_vs_resistance >= 0.7:
                result["entry_signal"] = False
                result["entry_strength"] = "none"
                result["reasons"].append(
                    f"버팀 양봉 but 저항 거래량 미달 ({vol_vs_resistance:.1%}) — 관망"
                )
                result["score"] = max(result["score"], 0) + 10
        elif cur_upper_r >= 0.50:
            result["reasons"].append(
                f"[저항] 윗꼬리 강한 캔들 ({cur_upper_r:.0%}) + "
                f"거래량 {cur_v/vol_avg:.1f}배 — 관망"
            )
            result["score"] = max(result["score"], 0) - 10  # 음수 방지 후 감점

        return result

    def detect_bb_squeeze(self, ohlcv: pd.DataFrame, period: int = 20, squeeze_lookback: int = 120) -> Dict:
        """볼린저 밴드 스퀴즈 감지

        스퀴즈: 현재 BB폭이 최근 N일 BB폭의 최솟값 근처 (상대 기준)
        돌파: 스퀴즈 상태에서 현재가가 상단 밴드 위

        Returns:
            {"detected": bool, "breakout": bool, "score": int, "bb_width": float, "reasons": list}
        """
        if len(ohlcv) < max(period, 40):
            return {"detected": False, "breakout": False, "score": 0, "bb_width": 0.0, "reasons": []}

        bb = IndicatorEngine.calculate_bollinger_bands(ohlcv["Close"], period=period)
        upper, middle, lower = bb["upper"], bb["middle"], bb["lower"]

        # BB폭 = (상단 - 하단) / 중간 (상대 변동성)
        bb_width = ((upper - lower) / middle).dropna()
        if len(bb_width) < 20:
            return {"detected": False, "breakout": False, "score": 0, "bb_width": 0.0, "reasons": []}

        current_width = float(bb_width.iloc[-1])
        lookback_min = float(bb_width.tail(squeeze_lookback).min())

        # 스퀴즈: 현재 BB폭이 lookback 기간 최솟값의 120% 이내
        squeeze = current_width <= lookback_min * 1.2

        # 돌파: 스퀴즈 상태에서 현재가가 상단 밴드 위
        curr_price = float(ohlcv["Close"].iloc[-1])
        upper_val = float(upper.iloc[-1])
        breakout = squeeze and curr_price > upper_val

        score = 0
        reasons = []
        if squeeze:
            score += 10
            reasons.append("BB 스퀴즈 (변동성 압축 — 폭발 대기)")
        if breakout:
            score += 15
            reasons.append(f"BB 스퀴즈 돌파 ({curr_price:,.0f} > 상단 {upper_val:,.0f})")

        return {
            "detected": squeeze,
            "breakout": breakout,
            "score": score,
            "bb_width": round(current_width, 4),
            "reasons": reasons,
        }

    def check_signal(self, ohlcv_data: pd.DataFrame) -> Dict:
        """가격 패턴 신호 체크 (눌림목 포함)"""
        if len(ohlcv_data) < 15:
            return {"signal": SignalType.HOLD, "strength": SignalStrength.LOW, "score": 0, "reasons": []}

        closes = ohlcv_data["Close"]
        reasons = []
        score = 0
        pullback_info = None

        # ── early return 이후에도 포함할 분석을 미리 계산 ─────────────────
        dryup_recovery_result = self.detect_volume_dryup_recovery(ohlcv_data)
        seoryuk_result        = self.detect_seoryuk_accumulation(ohlcv_data)
        tight_result          = self.detect_tight_consolidation(ohlcv_data)

        pre_surge_info = {
            "dryup_recovery": dryup_recovery_result,
            "seoryuk":        seoryuk_result,
            "tight_consol":   tight_result,
        }

        # 컵앤핸들 — reversal_risk early return에도 포함해야 하므로 먼저 계산
        cup_handle_result: Optional[Dict] = None
        if len(ohlcv_data) >= 60:
            cup_handle_result = self.detect_cup_and_handle(ohlcv_data)

        # 패턴 1: 눌림목 (Pullback) ⭐ 우선 순위
        pullback_result = self.detect_pullback(ohlcv_data)

        if pullback_result["is_reversal_risk"]:
            # 추세전환 위험이 있으면 HOLD 신호 (단, pre_surge / candle_volume / cup_handle 은 포함)
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": 0,
                "reasons": pullback_result["reasons"],
                "pullback": pullback_result,
                "pre_surge": pre_surge_info,
                "cup_handle": cup_handle_result,
                "candle_volume": self.detect_candle_volume_resistance(ohlcv_data),
            }

        if pullback_result["is_pullback"]:
            reasons.extend(["🎯 눌림목 패턴"] + pullback_result["reasons"])
            score += pullback_result["score"]
            pullback_info = pullback_result

        # 패턴 2: 저점 높이기
        higher_lows = self.detect_higher_lows(closes, 5)
        if higher_lows:
            reasons.append("저점 높이기 패턴")
            score += 30

        # 패턴 3: 횡보 후 돌파
        consolidation_breakout = self.detect_consolidation_breakout(ohlcv_data, 5)
        if consolidation_breakout:
            reasons.append("횡보 후 돌파")
            score += 40

        # 패턴 4: 상승 추세 (20일 수익률 > 0)
        if len(closes) >= 20:
            returns_20d = (closes.iloc[-1] - closes.iloc[-20]) / closes.iloc[-20]
            if returns_20d > 0:
                reasons.append(f"20일 상승 추세 (+{returns_20d*100:.1f}%)")
                score += 15

        # 패턴 5: 컵앤핸들 (점수에 반영하지 않고 별도 필드로 반환) — 상단에서 이미 계산됨

        # ── 급등 전 시그널 (Pre-Surge Signals) ──────────────────────────
        # 패턴 6: 거래량 건조 후 첫 회복일
        if dryup_recovery_result["detected"]:
            reasons.extend(["📊 거래량 건조 회복"] + dryup_recovery_result["reasons"])
            score += dryup_recovery_result["score"]

        # 패턴 7: 세력 매집 (극단 건조 후 거래량 폭발)
        if seoryuk_result["detected"]:
            reasons.extend(["🔥 세력 매집 의심"] + seoryuk_result["reasons"])
            score += seoryuk_result["score"]

        # 패턴 8: 타이트 횡보 (에너지 압축)
        if tight_result["detected"]:
            reasons.extend(["🗜️ 에너지 압축 횡보"] + tight_result["reasons"])
            score += tight_result["score"]

        # ── 패턴 9: 캔들 해부 + 거래량 조합 분석 ──────────────────────
        candle_vol_result = self.detect_candle_volume_resistance(ohlcv_data)

        if candle_vol_result["fake_breakout_risk"]:
            # 가짜 돌파 위험 → 점수 감점 + 이유 기록
            reasons.extend(candle_vol_result["reasons"])
            score = max(0, score + candle_vol_result["score"])  # score는 음수일 수 있음

        elif candle_vol_result["entry_signal"]:
            # 버팀 진입 신호 → 점수 가산
            reasons.extend(["🕯️ 캔들 버팀 진입"] + candle_vol_result["reasons"])
            score += candle_vol_result["score"]

        elif candle_vol_result["reasons"]:
            # 관망 이유만 기록 (점수 미반영)
            reasons.extend(candle_vol_result["reasons"])

        # ── 패턴 10: BB 스퀴즈 ──────────────────────────────────────────
        bb_squeeze_result = self.detect_bb_squeeze(ohlcv_data)
        if bb_squeeze_result["detected"]:
            score = min(100, score + bb_squeeze_result["score"])
            reasons.extend(bb_squeeze_result["reasons"])

        # 신호 강도 결정
        if score >= 70:
            strength = SignalStrength.HIGH
            signal_type = SignalType.BUY
        elif score >= 50:
            strength = SignalStrength.MEDIUM
            signal_type = SignalType.BUY
        else:
            strength = SignalStrength.LOW
            signal_type = SignalType.HOLD

        result = {
            "signal": signal_type,
            "strength": strength,
            "score": score,
            "reasons": reasons
        }

        # 눌림목 정보 추가
        if pullback_info:
            result["pullback"] = pullback_info

        # 컵앤핸들 별도 필드 (점수 미반영, 독립 판단용)
        if cup_handle_result is not None:
            result["cup_handle"] = cup_handle_result

        # 급등 전 시그널 별도 필드
        result["pre_surge"] = pre_surge_info

        # 캔들+거래량 분석 결과 별도 필드 (저항 거래량 → 2순위 익절에 활용)
        result["candle_volume"] = candle_vol_result

        # BB 스퀴즈 결과 별도 필드
        result["bb_squeeze"] = bb_squeeze_result

        return result


# ═══════════════════════════════════════════════════════════════
# 청산 신호 (Exit Signals)
# ═══════════════════════════════════════════════════════════════

class TakeProfitStrategy:
    """익절 전략 (분할 익절)"""

    def __init__(self, entry_price: float, targets: Optional[List[Dict]] = None):
        """
        Args:
            entry_price: 진입 가격
            targets: 익절 목표 리스트
                     [{"ratio": 0.03, "volume_pct": 0.5}, ...]
        """
        self.entry_price = entry_price
        self.targets = targets or [
            {"ratio": 0.03, "volume_pct": 0.33, "name": "1차 익절 +3%"},
            {"ratio": 0.07, "volume_pct": 0.50, "name": "2차 익절 +7%"},
            {"ratio": 0.15, "volume_pct": 1.00, "name": "3차 익절 +15%"},
        ]
        self.executed_targets = set()

    def check_exit(self, current_price: float, _position_size: float = 1.0) -> Tuple[bool, Optional[Dict]]:
        """
        익절 조건 체크

        Returns:
            (should_exit, exit_info)
            exit_info: {
                "volume_pct": 매도 비율,
                "reason": 익절 사유,
                "profit_ratio": 수익률
            }
        """
        profit_ratio = (current_price - self.entry_price) / self.entry_price

        for i, target in enumerate(self.targets):
            if i in self.executed_targets:
                continue

            if profit_ratio >= target["ratio"]:
                self.executed_targets.add(i)
                return True, {
                    "volume_pct": target["volume_pct"],
                    "reason": target["name"],
                    "profit_ratio": profit_ratio,
                    "target_ratio": target["ratio"]
                }

        return False, None


class StopLossStrategy:
    """손절 전략 — 고정/트레일링/ATR 동적 손절 지원"""

    def __init__(self, entry_price: float, stop_loss_ratio: float = -0.02,
                 trailing_stop: bool = True, trailing_ratio: float = -0.03,
                 atr: Optional[float] = None, atr_multiplier: Optional[float] = None,
                 max_loss_ratio: float = 0.08):
        """
        Args:
            entry_price:     진입 가격
            stop_loss_ratio: 고정 손절 비율 (예: -0.02 = -2%)
            trailing_stop:   트레일링 스톱 사용 여부
            trailing_ratio:  트레일링 스톱 비율 (최고가 대비)
            atr:             ATR 값 (IndicatorEngine.calculate_atr 결과)
                             None이면 ATR 손절 비활성화
            atr_multiplier:  ATR 배수 (None=자동, 명시 시 고정 사용)
                             자동 결정 기준: ATR% < 2% → 1.2, 2~4% → 1.5, > 4% → 2.0
            max_loss_ratio:  최대 손실 허용 비율 (ATR 손절가 하한선, 기본 8%)
                             hard floor = entry_price × (1 - max_loss_ratio)
        """
        self.entry_price = entry_price
        self.stop_loss_ratio = stop_loss_ratio
        self.trailing_stop = trailing_stop
        self.trailing_ratio = trailing_ratio
        self.highest_price = entry_price
        self.atr = atr

        # ATR% 기반 배수 자동 결정 (명시적 배수 없을 때)
        if atr and atr > 0 and entry_price > 0:
            if atr_multiplier is None:
                atr_pct = atr / entry_price
                if atr_pct < 0.02:
                    atr_multiplier = 1.2   # 안정적 종목 — 타이트한 손절
                elif atr_pct < 0.04:
                    atr_multiplier = 1.5   # 표준
                else:
                    atr_multiplier = 2.0   # 고변동 종목 — 넓은 손절 여유
            self.atr_multiplier = atr_multiplier

            raw_stop = entry_price - atr * atr_multiplier
            hard_floor = entry_price * (1 - max_loss_ratio)
            # hard floor: ATR 손절가가 최대 허용 손실보다 깊으면 hard floor 로 제한
            self.atr_stop_price = max(raw_stop, hard_floor)
        else:
            self.atr_multiplier = atr_multiplier or 1.5
            self.atr_stop_price = None

    def update_highest_price(self, current_price: float):
        """최고가 업데이트"""
        if current_price > self.highest_price:
            self.highest_price = current_price

    def check_exit(self, current_price: float) -> Tuple[bool, Optional[Dict]]:
        """
        손절 조건 체크

        우선순위: ATR 동적 손절 → 고정 손절 → 트레일링 스톱

        Returns:
            (should_exit, exit_info)
        """
        self.update_highest_price(current_price)

        # 0. ATR 기반 동적 손절 (변동성 반영, 고정 손절보다 우선)
        if self.atr_stop_price is not None and current_price <= self.atr_stop_price:
            return True, {
                "reason": "atr_stop_loss",
                "atr": round(self.atr, 0),
                "atr_multiplier": self.atr_multiplier,
                "stop_price": round(self.atr_stop_price, 0),
                "loss_ratio": (current_price - self.entry_price) / self.entry_price,
            }

        # 1. 고정 손절
        loss_ratio = (current_price - self.entry_price) / self.entry_price
        if loss_ratio <= self.stop_loss_ratio:
            return True, {
                "reason": "fixed_stop_loss",
                "loss_ratio": loss_ratio,
                "stop_price": self.entry_price * (1 + self.stop_loss_ratio)
            }

        # 2. 트레일링 스톱 (최고가가 진입가를 초과한 이후에만 작동)
        if self.trailing_stop and self.highest_price > self.entry_price:
            trailing_threshold = self.highest_price * (1 + self.trailing_ratio)
            if current_price <= trailing_threshold:
                return True, {
                    "reason": "trailing_stop",
                    "highest_price": self.highest_price,
                    "threshold": trailing_threshold,
                    "loss_from_peak": (current_price - self.highest_price) / self.highest_price
                }

        return False, None


class TimeBasedExit:
    """시간 기반 청산 (단타 특화)"""

    def __init__(self, entry_time: datetime, holding_limit_minutes: int = 30,
                 market_close_time: Optional[str] = None):
        """
        Args:
            entry_time: 진입 시각
            holding_limit_minutes: 최대 보유 시간 (분)
            market_close_time: 장 마감 시각 (HH:MM 형식, 예: "15:20")
        """
        self.entry_time = entry_time
        self.holding_limit_minutes = holding_limit_minutes
        self.market_close_time = market_close_time

    def is_near_market_close(self, current_time: datetime, minutes_before: int = 10) -> bool:
        """장 마감 N분 전 체크"""
        if not self.market_close_time:
            return False

        close_hour, close_minute = map(int, self.market_close_time.split(":"))
        close_time = current_time.replace(hour=close_hour, minute=close_minute, second=0)
        threshold_time = close_time - timedelta(minutes=minutes_before)

        return current_time >= threshold_time

    def check_exit(self, current_time: datetime) -> Tuple[bool, Optional[Dict]]:
        """
        시간 기반 청산 체크

        Returns:
            (should_exit, exit_info)
        """
        holding_minutes = (current_time - self.entry_time).total_seconds() / 60

        # 1. 최대 보유 시간 초과
        if holding_minutes >= self.holding_limit_minutes:
            return True, {
                "reason": f"time_limit_{self.holding_limit_minutes}min",
                "holding_minutes": holding_minutes
            }

        # 2. 장 마감 임박
        if self.is_near_market_close(current_time, 10):
            return True, {
                "reason": "market_close",
                "holding_minutes": holding_minutes
            }

        return False, None


# ═══════════════════════════════════════════════════════════════
# 주봉 RSI 스윙 전략 (신규)
# ═══════════════════════════════════════════════════════════════

class WeeklyRSISwingSignal:
    """
    주봉 RSI 30 돌파 + 일봉 MA50/200 골든크로스 스윙 전략

    기존 RSIGoldenCrossSignal과의 핵심 차이:
    - RSI 기준: 주봉(weekly) vs 기존 일봉(daily)
    - 진입 순서: RSI 30 돌파 먼저 → 골든크로스는 이후 확인 조건
    - 골든크로스 없을 때: 방어 모드(MEDIUM) vs 기존은 HOLD 반환
    - 보유 성격: 스윙/중기 vs 단타

    진입 흐름:
        주봉 RSI 30 상향 돌파 → 진입
            └─ 골든크로스 있음 → HIGH (추가 매수/홀딩)
            └─ 골든크로스 없음 → MEDIUM (하락 대비, 방어적 홀딩)
    """

    MIN_BARS = 310  # 200일 MA + 주봉 RSI 14 × 5일 + 여유

    def check_signal(self, ohlcv_data: pd.DataFrame) -> Dict:
        if len(ohlcv_data) < self.MIN_BARS:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": 0,
                "reasons": [f"데이터 부족 (최소 {self.MIN_BARS}일, 현재 {len(ohlcv_data)}일)"],
            }

        closes = ohlcv_data["Close"]
        volumes = ohlcv_data["Volume"]
        score = 0
        reasons = []

        # ── 1. 주봉 RSI 계산 ────────────────────────────────────
        try:
            weekly_closes = closes.resample("W").last().dropna()
            weekly_rsi = IndicatorEngine.calculate_rsi(weekly_closes, 14).dropna()
        except Exception as e:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": 0,
                "reasons": [f"주봉 RSI 계산 실패: {e}"],
            }

        if len(weekly_rsi) < 6:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": 0,
                "reasons": ["주봉 데이터 부족"],
            }

        curr_w_rsi = float(weekly_rsi.iloc[-1])

        # 주봉 RSI 30 돌파: 최근 3주 이내
        rsi_crossed = False
        for i in range(1, min(4, len(weekly_rsi))):
            if float(weekly_rsi.iloc[-i - 1]) < 30 <= float(weekly_rsi.iloc[-i]):
                rsi_crossed = True
                reasons.append(f"주봉 RSI 30 상향 돌파 ({i}주 전, 현재 {curr_w_rsi:.1f})")
                score += 50
                break

        if not rsi_crossed:
            recent_min = float(weekly_rsi.iloc[-5:].min())
            if 30 <= curr_w_rsi < 50 and recent_min < 30:
                # 5주 내 30 하회 후 회복 중
                reasons.append(f"주봉 RSI 30 회복 중 ({curr_w_rsi:.1f}, 최근 저점 {recent_min:.1f})")
                score += 35
            elif 30 <= curr_w_rsi < 50:
                reasons.append(f"주봉 RSI 30~50 구간 ({curr_w_rsi:.1f})")
                score += 20
            else:
                return {
                    "signal": SignalType.HOLD,
                    "strength": SignalStrength.LOW,
                    "score": 0,
                    "reasons": [f"주봉 RSI 조건 미충족 ({curr_w_rsi:.1f})"],
                    "weekly_rsi": curr_w_rsi,
                }

        # ── 2. 일봉 MA50/MA200 골든크로스 확인 ─────────────────
        ma50 = IndicatorEngine.calculate_ma(closes, 50)
        ma200 = IndicatorEngine.calculate_ma(closes, 200)
        has_golden_cross = float(ma50.iloc[-1]) > float(ma200.iloc[-1])

        if has_golden_cross:
            _ma200_val = float(ma200.iloc[-1])
            gc_pct = (float(ma50.iloc[-1]) - _ma200_val) / _ma200_val * 100 if _ma200_val > 0 else 0.0
            reasons.append(f"골든크로스 확인 → 홀딩/추가 매수 (MA50-MA200 +{gc_pct:.2f}%)")
            score += 35
            # 최근 30일 이내 골든크로스 발생
            for i in range(1, min(31, len(ma50))):
                if float(ma50.iloc[-i]) > float(ma200.iloc[-i]) and float(ma50.iloc[-i - 1]) <= float(ma200.iloc[-i - 1]):
                    reasons.append(f"최근 골든크로스 발생 ({i}일 전) → 강세 초입")
                    score += 10
                    break
        else:
            dc_pct = (float(ma200.iloc[-1]) - float(ma50.iloc[-1])) / float(ma200.iloc[-1]) * 100
            reasons.append(f"골든크로스 미확인 (MA50 < MA200, -{dc_pct:.2f}%) → 하락 대비 필요")
            # 골든크로스 없어도 RSI 조건 충족 시 MEDIUM 신호 유지 (기존 전략과의 핵심 차이)
            score += 5

        # ── 3. 거래량 확인 ──────────────────────────────────────
        vol_ma20 = float(volumes.tail(20).mean())
        vol_ratio = float(volumes.iloc[-1]) / vol_ma20 if vol_ma20 > 0 else 0
        if vol_ratio >= 1.5:
            reasons.append(f"거래량 증가 ({vol_ratio:.1f}배)")
            score += 15
        elif vol_ratio >= 1.0:
            reasons.append(f"거래량 보통 ({vol_ratio:.1f}배)")
            score += 5

        # ── 신호 결정 ───────────────────────────────────────────
        if score >= 70:
            strength, signal = SignalStrength.HIGH, SignalType.BUY
        elif score >= 45:
            strength, signal = SignalStrength.MEDIUM, SignalType.BUY
        else:
            strength, signal = SignalStrength.LOW, SignalType.HOLD

        return {
            "signal": signal,
            "strength": strength,
            "score": score,
            "reasons": reasons,
            "weekly_rsi": curr_w_rsi,
            "golden_cross": has_golden_cross,
            "ma50": float(ma50.iloc[-1]),
            "ma200": float(ma200.iloc[-1]),
        }


# ═══════════════════════════════════════════════════════════════
# M+ 전략: 다중 타임프레임 모멘텀 (일봉 근사)
# ═══════════════════════════════════════════════════════════════

class MultiTFMomentumPlusSignal:
    """
    M+ 전략: 일봉 RSI 30 돌파 + MA20/60 골든크로스 + MACD 오실레이터 양전

    다중 타임프레임 전략의 일봉 데이터 근사 구현:
      1단계 (관심): 일봉 RSI 14가 30을 상향 돌파 → 과매도 탈출
      2단계 (진입): MA20 > MA60 골든크로스 + MACD histogram > 0 → 상승 강도 확인
      3단계 (추가): 전일 고가 갱신 → 15분봉 전고점 돌파 근사

    M (rsi_golden_cross) 대비 핵심 차이:
      - MA 기준: MA50/200 → MA20/60 (더 빠른 단기 신호)
      - 필수 조건 추가: MACD histogram > 0 (상승 강도 필터)
      - MACD histogram <= 0이면 무조건 HOLD

    점수 구조:
      MACD 양전 전환: +35 / 유지: +20  (필수, 없으면 HOLD)
      MA20/60 GC 발생 (20일 이내): +30 / 유지: +20  (필수, 없으면 HOLD)
      RSI 30 돌파 (5일 이내): +30 / 탈출 구간: +15 / 정상: +5  (30 이하면 HOLD)
      거래량 급증(2배 이상): +15 / 증가(1.2배): +8
      전일 고가 갱신: +10
      BUY 기준: 70점 이상
    """

    MIN_BARS = 120  # MA60 + RSI 14 + MACD(26+9) + 여유

    def check_signal(self, ohlcv_data: pd.DataFrame) -> Dict:
        if len(ohlcv_data) < self.MIN_BARS:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": 0,
                "reasons": [f"데이터 부족 (최소 {self.MIN_BARS}일, 현재 {len(ohlcv_data)}일)"],
            }

        closes = ohlcv_data["Close"]
        highs = ohlcv_data["High"]
        volumes = ohlcv_data["Volume"]
        score = 0
        reasons = []

        # ── 1. MACD 오실레이터 > 0 (M+ 핵심 필수 조건) ──────────────
        macd_data = IndicatorEngine.calculate_macd(closes)
        histogram = macd_data.get("histogram", pd.Series(dtype=float))

        if len(histogram) < 2:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": 0,
                "reasons": ["MACD 계산 실패"],
            }

        curr_hist = float(histogram.iloc[-1])
        prev_hist = float(histogram.iloc[-2])

        if curr_hist <= 0:
            # MACD 오실레이터 음수 → M+ 핵심 조건 미충족
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": 0,
                "reasons": [f"MACD 오실레이터 음수 ({curr_hist:.4f}) — M+ 조건 미충족"],
                "macd_histogram": curr_hist,
            }

        if prev_hist <= 0 < curr_hist:
            reasons.append(f"MACD 오실레이터 양전 전환 ({curr_hist:.4f})")
            score += 35
        else:
            reasons.append(f"MACD 오실레이터 양수 유지 ({curr_hist:.4f})")
            score += 20

        # ── 2. MA20 > MA60 골든크로스 (필수 조건) ───────────────────
        ma20 = IndicatorEngine.calculate_ma(closes, 20)
        ma60 = IndicatorEngine.calculate_ma(closes, 60)

        if len(ma20) == 0 or len(ma60) == 0:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": score,
                "reasons": reasons + ["MA 계산 실패"],
                "macd_histogram": curr_hist,
            }

        curr_ma20 = float(ma20.iloc[-1])
        curr_ma60 = float(ma60.iloc[-1])

        if curr_ma20 <= curr_ma60:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": score,
                "reasons": reasons + [f"MA20 < MA60 — 골든크로스 미형성"],
                "macd_histogram": curr_hist,
                "ma20": curr_ma20,
                "ma60": curr_ma60,
            }

        gc_pct = (curr_ma20 - curr_ma60) / curr_ma60 * 100 if curr_ma60 > 0 else 0.0
        recent_gc = False
        for i in range(1, min(21, len(ma20))):
            if float(ma20.iloc[-i]) > float(ma60.iloc[-i]) and float(ma20.iloc[-i - 1]) <= float(ma60.iloc[-i - 1]):
                reasons.append(f"MA20/60 골든크로스 ({i}일 전, 격차 +{gc_pct:.2f}%)")
                score += 30
                recent_gc = True
                break
        if not recent_gc:
            reasons.append(f"MA20 > MA60 유지 (+{gc_pct:.2f}%)")
            score += 20

        # ── 3. RSI 30 상향 돌파 확인 ─────────────────────────────────
        rsi = IndicatorEngine.calculate_rsi(closes, 14)

        if len(rsi) < 6:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": score,
                "reasons": reasons + ["RSI 데이터 부족"],
                "macd_histogram": curr_hist,
            }

        curr_rsi = float(rsi.iloc[-1])

        # RSI 30 이하 → 아직 과매도, HOLD
        if curr_rsi <= 30:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": score,
                "reasons": reasons + [f"RSI 과매도 미탈출 ({curr_rsi:.1f})"],
                "macd_histogram": curr_hist,
                "rsi": curr_rsi,
            }

        # 최근 5일 이내 RSI 30 상향 돌파
        rsi_crossed = False
        for i in range(1, min(6, len(rsi))):
            if len(rsi) > i + 1 and float(rsi.iloc[-i - 1]) <= 30 < float(rsi.iloc[-i]):
                reasons.append(f"RSI 30 상향 돌파 ({i}일 전, 현재 {curr_rsi:.1f})")
                score += 30
                rsi_crossed = True
                break

        if not rsi_crossed:
            if 30 < curr_rsi < 50:
                reasons.append(f"RSI 과매도 탈출 구간 ({curr_rsi:.1f})")
                score += 15
            else:
                reasons.append(f"RSI 정상 범위 ({curr_rsi:.1f})")
                score += 5

        # ── 4. 거래량 확인 (보조) ────────────────────────────────────
        vol_ma20 = float(volumes.tail(20).mean())
        vol_ratio = float(volumes.iloc[-1]) / vol_ma20 if vol_ma20 > 0 else 0

        if vol_ratio >= 2.0:
            reasons.append(f"거래량 급증 ({vol_ratio:.1f}배)")
            score += 15
        elif vol_ratio >= 1.2:
            reasons.append(f"거래량 증가 ({vol_ratio:.1f}배)")
            score += 8
        else:
            reasons.append(f"거래량 보통 ({vol_ratio:.1f}배)")

        # ── 5. 전일 고가 갱신 (15분봉 전고점 돌파 근사) ──────────────
        curr_high = float(highs.iloc[-1])
        prev_high = float(highs.iloc[-2])
        if curr_high > prev_high:
            reasons.append(f"전일 고가 갱신 ({curr_high:,.0f} > {prev_high:,.0f})")
            score += 10

        # ── 신호 결정 ────────────────────────────────────────────────
        # M+ 전략: 고확신 신호(75점+)만 BUY → 과다 진입 방지
        if score >= 75:
            strength, signal_type = SignalStrength.HIGH, SignalType.BUY
        elif score >= 55:
            strength, signal_type = SignalStrength.MEDIUM, SignalType.HOLD  # 참고용만, 진입 안 함
        else:
            strength, signal_type = SignalStrength.LOW, SignalType.HOLD

        return {
            "signal": signal_type,
            "strength": strength,
            "score": score,
            "reasons": reasons,
            "macd_histogram": curr_hist,
            "rsi": curr_rsi,
            "ma20": curr_ma20,
            "ma60": curr_ma60,
            "volume_ratio": vol_ratio,
        }


# ═══════════════════════════════════════════════════════════════
# 분봉 진입 타이밍 신호 (단타 진입 + 스윙 홀딩 조합)
# ═══════════════════════════════════════════════════════════════

class MinuteBreakoutSignal:
    """분봉 진입 타이밍 신호 — 단타 진입 + 스윙 홀딩 조합용

    일봉 기반 종목 스크리닝 이후, 실제 진입 타이밍을 분봉으로 확인.
    "눌림목 반등" 또는 "분봉 고점 돌파" 시점을 포착한다.

    점수 구조:
        분봉 10봉 고점 돌파:      +25  (단기 모멘텀 확인)
        거래량 급증 (2배 이상):   +25 / 증가 (1.5배): +15
        단기 상승 추세:           +20  (최근 5봉 양봉 60% 이상)
        VWAP 상단:               +15  (장중 평균 단가 위)
        눌림목 반등 보너스:        +15  (장중 고점 대비 -2~-7% 구간)

    과열 차단: 장 시작 첫봉 시가 대비 +8% 이상 → 즉시 HOLD
    BUY 기준: 40점 이상
    """

    MIN_CANDLES = 10

    def check_signal(self, candles: list) -> Dict:
        """
        Args:
            candles: KIS 분봉 리스트 [{time, open, high, low, close, volume}, ...]
                     시간 오름차순 (get_minute_chart 반환값)

        Returns:
            {"signal": "BUY"|"HOLD", "strength": ..., "score": int, "reasons": [...], ...}
        """
        if len(candles) < self.MIN_CANDLES:
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": 0,
                "reasons": [f"분봉 데이터 부족 (최소 {self.MIN_CANDLES}봉, 현재 {len(candles)}봉)"],
            }

        latest = candles[-1]
        current_price = latest["close"]
        current_volume = latest["volume"]

        # 최근 10봉 (현재봉 제외)
        lookback = candles[-self.MIN_CANDLES - 1:-1]

        score = 0
        reasons = []

        # ── 과열 차단: 장 시작 첫봉 시가 대비 +8% 이상 ────────────────
        first_open = candles[0]["open"] if candles[0]["open"] > 0 else current_price
        intraday_change = (current_price - first_open) / first_open * 100 if first_open > 0 else 0
        if intraday_change >= 8.0:
            reasons.append(f"[과열차단] 장중 +{intraday_change:.1f}% (≥8% 진입 위험)")
            return {
                "signal": SignalType.HOLD,
                "strength": SignalStrength.LOW,
                "score": 0,
                "reasons": reasons,
                "intraday_change": round(intraday_change, 2),
            }

        # ── 1. 분봉 10봉 고점 돌파 ─────────────────────────────────────
        recent_high = max(c["high"] for c in lookback)
        if current_price > recent_high:
            reasons.append(f"분봉 10봉 고점 돌파 ({recent_high:,} → {current_price:,})")
            score += 25

        # ── 2. 거래량 급증 ──────────────────────────────────────────────
        avg_vol = sum(c["volume"] for c in lookback) / len(lookback) if lookback else 0
        vol_ratio = current_volume / avg_vol if avg_vol > 0 else 0
        if vol_ratio >= 2.0:
            reasons.append(f"분봉 거래량 급증 ({vol_ratio:.1f}배)")
            score += 25
        elif vol_ratio >= 1.5:
            reasons.append(f"분봉 거래량 증가 ({vol_ratio:.1f}배)")
            score += 15

        # ── 3. 단기 상승 추세: 최근 5봉 양봉 비율 ─────────────────────
        last5 = candles[-6:-1] if len(candles) >= 6 else candles[:-1]
        bullish_count = sum(1 for c in last5 if c["close"] >= c["open"])
        if last5 and bullish_count / len(last5) >= 0.6:
            reasons.append(f"단기 상승 추세 (최근 5봉 양봉 {bullish_count}/{len(last5)})")
            score += 20

        # ── 4. VWAP 상단 ────────────────────────────────────────────────
        total_value = sum(c["close"] * c["volume"] for c in candles if c["volume"] > 0)
        total_vol = sum(c["volume"] for c in candles)
        vwap = total_value / total_vol if total_vol > 0 else 0
        if vwap > 0 and current_price > vwap:
            reasons.append(f"VWAP 상단 ({vwap:,.0f})")
            score += 15

        # ── 5. 눌림목 반등 보너스 ───────────────────────────────────────
        intraday_high = max(c["high"] for c in candles)
        from_high_pct = (current_price - intraday_high) / intraday_high * 100 if intraday_high > 0 else 0
        if -7.0 <= from_high_pct <= -2.0 and bullish_count >= 2:
            reasons.append(f"눌림목 반등 구간 (고점 대비 {from_high_pct:.1f}%)")
            score += 15

        # ── 6. 분봉 캔들 해부 + 저항 거래량 분석 ────────────────────────
        candle_vol_result = self._analyze_candle_volume(candles, lookback_n=10)
        if candle_vol_result["fake_breakout_risk"]:
            reasons.extend(candle_vol_result["reasons"])
            score = max(0, score - 20)
        elif candle_vol_result["entry_signal"]:
            reasons.extend(["🕯️ 분봉 버팀 진입"] + candle_vol_result["reasons"])
            score += candle_vol_result["score"]
        elif candle_vol_result["reasons"]:
            reasons.extend(candle_vol_result["reasons"])

        signal = SignalType.BUY if score >= 40 else SignalType.HOLD
        if score >= 65:
            strength = SignalStrength.HIGH
        elif score >= 40:
            strength = SignalStrength.MEDIUM
        else:
            strength = SignalStrength.LOW

        return {
            "signal": signal,
            "strength": strength,
            "score": score,
            "reasons": reasons,
            "vol_ratio": round(vol_ratio, 2),
            "intraday_change": round(intraday_change, 2),
            "vwap": round(vwap, 0) if vwap > 0 else None,
            "candle_volume": candle_vol_result,
        }

    def _analyze_candle_volume(self, candles: list, lookback_n: int = 10) -> Dict:
        """분봉 리스트 기반 캔들 해부 + 저항 거래량 분석

        candles: [{open, high, low, close, volume}, ...] 형식
        """
        result = {
            "resistance_candles": [],
            "max_resistance_volume": 0.0,
            "resistance_price": 0.0,
            "entry_signal": False,
            "entry_strength": "none",
            "fake_breakout_risk": False,
            "score": 0,
            "reasons": [],
        }

        if len(candles) < lookback_n + 2:
            return result

        cur = candles[-1]
        cur_o = float(cur["open"])
        cur_h = float(cur["high"])
        cur_l = float(cur["low"])
        cur_c = float(cur["close"])
        cur_v = float(cur["volume"])

        cur_range = cur_h - cur_l
        if cur_range <= 0:
            return result

        cur_body_r  = abs(cur_c - cur_o) / cur_range
        cur_lower_r = (min(cur_o, cur_c) - cur_l) / cur_range
        cur_is_bull = cur_c > cur_o

        window = candles[-(lookback_n + 1):-1]
        vol_avg = sum(c["volume"] for c in window) / len(window) if window else 1.0

        # 저항 캔들 탐색
        resistance_candles = []
        for c in window:
            o, h, l, cl, v = float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]), float(c["volume"])
            rng = h - l
            if rng <= 0 or v <= 0:
                continue
            upper_r = (h - max(o, cl)) / rng
            if upper_r >= 0.40 and v >= vol_avg * 0.8:
                resistance_candles.append({"price": h, "volume": v, "upper_shadow_ratio": upper_r})

        if not resistance_candles:
            if cur_is_bull and cur_lower_r >= 0.25 and cur_body_r >= 0.35:
                result["entry_signal"] = True
                result["entry_strength"] = "normal"
                result["reasons"].append(f"분봉 버팀 양봉 (몸통 {cur_body_r:.0%}, 밑꼬리 {cur_lower_r:.0%})")
                result["score"] = 15
            return result

        max_res_vol   = max(rc["volume"] for rc in resistance_candles)
        res_price_ref = max(rc["price"]  for rc in resistance_candles)
        result["max_resistance_volume"] = max_res_vol
        result["resistance_price"] = res_price_ref

        near_resistance = abs(cur_c - res_price_ref) / res_price_ref < 0.02
        vol_below = cur_v < max_res_vol * 0.8

        if near_resistance and vol_below:
            result["fake_breakout_risk"] = True
            result["reasons"].append(
                f"[분봉 가짜돌파] 저항가 {res_price_ref:,} 근처 + 거래량 미달 ({cur_v/max_res_vol:.1%})"
            )
            return result

        if cur_is_bull and cur_lower_r >= 0.25 and cur_body_r >= 0.35:
            vol_vs_res = cur_v / max_res_vol if max_res_vol > 0 else 0
            if vol_vs_res >= 1.0:
                result["entry_signal"] = True
                result["entry_strength"] = "strong" if vol_vs_res >= 1.3 else "normal"
                result["reasons"].append(
                    f"분봉 버팀 양봉 + 저항 거래량 돌파 ({vol_vs_res:.1%})"
                )
                result["score"] = 25 if result["entry_strength"] == "strong" else 15

        return result


# ═══════════════════════════════════════════════════════════════
# 수급 분석 신호 (현업 트레이더 방식 추가)
# ═══════════════════════════════════════════════════════════════

class InstitutionalSupplySignal:
    """기관/외국인 순매수 수급 분석 — Track A combined 보너스 채점

    pykrx get_market_trading_volume_by_date 결과를 받아
    기관·외국인 연속 순매수 여부를 채점한다.

    채점 기준:
        기관 4일 이상 연속 순매수:   +10
        기관 2~3일 순매수:          +5
        외국인 4일 이상 연속 순매수: +10
        외국인 2~3일 순매수:        +5
        최대 보너스:                +15 (캡)

    현업과의 차이:
        현업 — 체결강도, 프로그램 매매, 공매도 잔고까지 통합
        현재 — 순매수 방향성만 확인 (일봉 배치 한계)
    """

    def check_signal(self, investor_data: Optional[pd.DataFrame]) -> Dict:
        """
        Args:
            investor_data: pykrx get_market_trading_volume_by_date 결과
                           MultiIndex 컬럼 (거래유형, 투자자유형) 또는 None

        Returns:
            {
                "score": 0~15 (보너스 점수),
                "reasons": [...],
                "available": bool,
                "institutional_net": float,  # 5일 합계
                "foreign_net": float,
            }
        """
        if investor_data is None or investor_data.empty:
            return {"score": 0, "reasons": [], "available": False,
                    "institutional_net": 0, "foreign_net": 0}

        score = 0
        reasons = []
        inst_net_total = 0.0
        foreign_net_total = 0.0

        try:
            # MultiIndex: (거래유형, 투자자유형) → 순매수 슬라이스
            if isinstance(investor_data.columns, pd.MultiIndex):
                try:
                    net_df = investor_data.xs("순매수", axis=1, level=0)
                except KeyError:
                    # level 순서가 반대인 경우
                    net_df = investor_data.xs("순매수", axis=1, level=1)
            else:
                net_df = investor_data  # 이미 순매수 컬럼만 있는 경우 fallback

            inst_col = next((c for c in net_df.columns if "기관" in str(c)), None)
            foreign_col = next((c for c in net_df.columns if "외국인" in str(c)), None)

            if inst_col is not None and len(net_df) >= 1:
                recent_inst = net_df[inst_col].tail(5)
                inst_net_total = float(recent_inst.sum())
                inst_pos = int((recent_inst > 0).sum())  # 5일 중 순매수 일수 (연속이 아닌 일수 합계)
                if inst_pos >= 4:
                    reasons.append(f"기관 순매수 우세 (5일 중 {inst_pos}일)")
                    score += 10
                elif inst_pos >= 2:
                    reasons.append(f"기관 순매수 (5일 중 {inst_pos}일)")
                    score += 5
                elif inst_pos == 0:
                    # 5일 전체 순매도 → 강한 매도 압력 패널티
                    reasons.append("기관 5일 전체 순매도 — 매도 압력")
                    score -= 7
                elif inst_pos == 1:
                    reasons.append(f"기관 순매도 우세 (5일 중 {5 - inst_pos}일 순매도)")
                    score -= 3

            if foreign_col is not None and len(net_df) >= 1:
                recent_foreign = net_df[foreign_col].tail(5)
                foreign_net_total = float(recent_foreign.sum())
                foreign_pos = int((recent_foreign > 0).sum())
                if foreign_pos >= 4:
                    reasons.append(f"외국인 순매수 우세 (5일 중 {foreign_pos}일)")
                    score += 10
                elif foreign_pos >= 2:
                    reasons.append(f"외국인 순매수 (5일 중 {foreign_pos}일)")
                    score += 5
                elif foreign_pos == 0:
                    reasons.append("외국인 5일 전체 순매도 — 이탈 압력")
                    score -= 7
                elif foreign_pos == 1:
                    reasons.append(f"외국인 순매도 우세 (5일 중 {5 - foreign_pos}일 순매도)")
                    score -= 3

        except Exception as e:
            logger.debug(f"InstitutionalSupplySignal 계산 실패: {e}")
            return {"score": 0, "reasons": [], "available": False,
                    "institutional_net": 0, "foreign_net": 0}

        return {
            "score": max(-14, min(score, 15)),  # 패널티 포함: -14 ~ +15
            "reasons": reasons,
            "available": True,
            "institutional_net": inst_net_total,
            "foreign_net": foreign_net_total,
        }


class SectorMomentumSignal:
    """KRX 섹터 지수 모멘텀 분석 — Track A combined 보너스 채점

    종목이 속한 업종 지수의 5일 수익률을 KOSPI와 비교하여
    섹터 강세 여부를 보너스 점수로 반영한다.

    채점 기준 (시장 대비 상대 수익률):
        섹터 +3% 이상 아웃퍼폼:  +10
        섹터 +1~3% 아웃퍼폼:    +5
        섹터 -2% 이상 언더퍼폼:  -5 (패널티)
        섹터 데이터 없음:         0 (보너스 없음, 패널티도 없음)

    현업과의 차이:
        현업 — 섹터 로테이션 실시간 모니터링, 자금 유입/유출 포착
        현재 — 5일 상대 수익률만 비교 (일봉 배치 한계)
    """

    def check_signal(self, sector_ohlcv: Optional[pd.DataFrame],
                     market_ohlcv: Optional[pd.DataFrame]) -> Dict:
        """
        Args:
            sector_ohlcv:  업종 지수 OHLCV (pykrx get_index_ohlcv_by_date 결과, 컬럼 영문)
                           None이면 보너스 0점
            market_ohlcv:  KOSPI 지수 OHLCV (비교 기준)
                           None이면 절대 수익률만 사용

        Returns:
            {
                "score": -5 ~ +10 (패널티 포함 보너스),
                "reasons": [...],
                "available": bool,
                "sector_5d_pct": float,
                "relative_vs_market": float | None,
            }
        """
        if sector_ohlcv is None or sector_ohlcv.empty or len(sector_ohlcv) < 5:
            return {"score": 0, "reasons": [], "available": False,
                    "sector_5d_pct": 0.0, "relative_vs_market": None}

        score = 0
        reasons = []

        try:
            close_col = "Close" if "Close" in sector_ohlcv.columns else sector_ohlcv.columns[3]
            s_close = sector_ohlcv[close_col]
            _s_base = float(s_close.iloc[-5])
            if _s_base == 0:
                return {"signal": SignalType.HOLD, "strength": SignalStrength.LOW, "score": 0, "reasons": []}
            sector_5d = (float(s_close.iloc[-1]) - _s_base) / _s_base * 100

            relative = None
            if market_ohlcv is not None and not market_ohlcv.empty and len(market_ohlcv) >= 5:
                m_close_col = "Close" if "Close" in market_ohlcv.columns else market_ohlcv.columns[3]
                m_close = market_ohlcv[m_close_col]
                _m_base = float(m_close.iloc[-5])
                market_5d = (float(m_close.iloc[-1]) - _m_base) / _m_base * 100 if _m_base != 0 else 0.0
                relative = sector_5d - market_5d

                if relative >= 3.0:
                    reasons.append(f"섹터 강세 (KOSPI 대비 +{relative:.1f}%, 5일)")
                    score += 10
                elif relative >= 1.0:
                    reasons.append(f"섹터 소폭 강세 (KOSPI 대비 +{relative:.1f}%, 5일)")
                    score += 5
                elif relative <= -2.0:
                    reasons.append(f"섹터 약세 (KOSPI 대비 {relative:.1f}%, 5일) — 진입 주의")
                    score -= 5
            else:
                # 시장 데이터 없으면 절대 수익률 기준
                if sector_5d >= 3.0:
                    reasons.append(f"섹터 상승세 (+{sector_5d:.1f}%, 5일)")
                    score += 10
                elif sector_5d >= 1.0:
                    reasons.append(f"섹터 소폭 상승 (+{sector_5d:.1f}%, 5일)")
                    score += 5

        except Exception as e:
            logger.debug(f"SectorMomentumSignal 계산 실패: {e}")
            return {"score": 0, "reasons": [], "available": False,
                    "sector_5d_pct": 0.0, "relative_vs_market": None}

        return {
            "score": score,
            "reasons": reasons,
            "available": True,
            "sector_5d_pct": round(sector_5d, 2),
            "relative_vs_market": round(relative, 2) if relative is not None else None,
        }


# ═══════════════════════════════════════════════════════════════
# 통합 신호 매니저
# ═══════════════════════════════════════════════════════════════

class SignalManager:
    """진입/청산 신호 통합 관리"""

    def __init__(self):
        self.volume_signal = VolumeBreakoutSignal()
        self.technical_signal = TechnicalBreakoutSignal()
        self.pattern_signal = PricePatternSignal()
        self.rsi_golden_cross_signal = RSIGoldenCrossSignal()
        self.weekly_rsi_swing_signal = WeeklyRSISwingSignal()
        self.multi_tf_momentum_plus_signal = MultiTFMomentumPlusSignal()
        self.institutional_supply_signal = InstitutionalSupplySignal()
        self.sector_momentum_signal = SectorMomentumSignal()

    def generate_entry_signal(self, ohlcv_data: pd.DataFrame, strategy: str = "combined",
                              investor_data: Optional[pd.DataFrame] = None,
                              sector_data: Optional[Dict] = None,
                              minute_data: list = None) -> Dict:
        """
        진입 신호 생성

        Args:
            ohlcv_data:    OHLCV 데이터
            strategy:      "volume" | "technical" | "pattern" | "rsi_golden_cross" |
                           "weekly_rsi_swing" | "multi_tf_momentum_plus" | "combined"
            investor_data: pykrx 투자자별 거래량 DataFrame (combined + KR만 사용)
                           None이면 수급 보너스 생략
            sector_data:   {"sector_ohlcv": DataFrame|None, "market_ohlcv": DataFrame|None}
                           None이면 섹터 보너스 생략

        Returns:
            종합 신호 정보
        """
        if strategy == "volume":
            return self.volume_signal.check_signal(ohlcv_data)
        elif strategy == "technical":
            return self.technical_signal.check_signal(ohlcv_data)
        elif strategy == "pattern":
            return self.pattern_signal.check_signal(ohlcv_data)
        elif strategy == "rsi_golden_cross":
            return self.rsi_golden_cross_signal.check_signal(ohlcv_data)
        elif strategy == "weekly_rsi_swing":
            return self.weekly_rsi_swing_signal.check_signal(ohlcv_data)
        elif strategy == "multi_tf_momentum_plus":
            return self.multi_tf_momentum_plus_signal.check_signal(ohlcv_data)
        else:  # combined
            # ── Step 1: 추격차단 게이트 (SignalManager 최상단) ──────────────
            # VolumeBreakoutSignal 내부 chase_blocked 보다 먼저 실행
            # → 모든 하위 클래스 호출 전에 차단하여 불필요한 계산 방지
            chase_blocked = False
            chase_reason = ""
            if len(ohlcv_data) >= 2:
                curr_p = float(ohlcv_data["Close"].iloc[-1])
                prev_p = float(ohlcv_data["Close"].iloc[-2])
                if prev_p > 0:
                    pct = (curr_p - prev_p) / prev_p * 100
                    if pct >= 5.0:
                        chase_blocked = True
                        chase_reason = f"[추격차단] 당일 +{pct:.1f}% 급등 (≥5%, 고점 진입 위험)"

            if chase_blocked:
                # 추격 차단이어도 컵앤핸들 형성 여부는 정보 제공 (진입 금지 ≠ 패턴 없음)
                ch_result = None
                if len(ohlcv_data) >= 60:
                    ch_result = self.pattern_signal.detect_cup_and_handle(ohlcv_data)
                return {
                    "signal": SignalType.HOLD,
                    "strength": SignalStrength.LOW,
                    "score": 0,
                    "reasons": [chase_reason],
                    "chase_blocked": True,
                    "cup_handle": ch_result,
                    "breakdown": {},
                }

            # ── Step 2: 하위 신호 클래스 실행 ───────────────────────────────
            volume_result = self.volume_signal.check_signal(ohlcv_data)
            technical_result = self.technical_signal.check_signal(ohlcv_data)
            pattern_result = self.pattern_signal.check_signal(ohlcv_data)
            mtf_result = self.multi_tf_momentum_plus_signal.check_signal(ohlcv_data)

            # ── Step 3: 각 클래스 점수 100점 캡 적용 ────────────────────────
            # 이론적 최대값이 100을 초과하는 클래스(PricePattern 등) 정규화
            v_score = min(volume_result["score"], 100)
            t_score = min(technical_result["score"], 100)
            p_score = min(pattern_result["score"], 100)
            m_score = min(mtf_result["score"], 100)

            # ── Step 4: 가중 합산 (4클래스, 합계 1.0) ───────────────────────
            # Volume 35% / Technical 30% / Pattern 20% / MultiTFMomentum 15%
            total_score = (
                v_score * 0.35 +
                t_score * 0.30 +
                p_score * 0.20 +
                m_score * 0.15
            )

            all_reasons = (
                volume_result["reasons"] +
                technical_result["reasons"] +
                pattern_result["reasons"] +
                mtf_result["reasons"]
            )

            # ── Step 5: 수급·섹터 보너스 (기관/외국인 + 업종 모멘텀) ──────────
            # 항상 계산 (breakdown 포함을 위해) — 단, 기술적 base가 부족하면 적용 차단
            supply_result = self.institutional_supply_signal.check_signal(investor_data)
            sector_ohlcv = sector_data.get("sector_ohlcv") if sector_data else None
            market_ohlcv = sector_data.get("market_ohlcv") if sector_data else None
            sector_result = self.sector_momentum_signal.check_signal(sector_ohlcv, market_ohlcv)

            base_score = total_score  # 보너스 적용 전 순수 기술적 점수 기록

            # ── Fix 5 게이트: base score < 40이면 보너스 적용 차단 ────────────
            # 기술적 구조가 미달인 종목은 수급·섹터가 좋아도 진입 금지
            # (수급+섹터 최대 +25점으로 HOLD→BUY HIGH 단독 역전 방지)
            if base_score >= 40:
                if supply_result["available"]:
                    total_score = max(0.0, min(100.0, total_score + supply_result["score"]))
                    all_reasons = all_reasons + supply_result["reasons"]
                if sector_result["available"]:
                    total_score = max(0.0, min(100.0, total_score + sector_result["score"]))
                    all_reasons = all_reasons + sector_result["reasons"]
            else:
                # base 미달: breakdown에는 포함하되 점수에는 반영하지 않음
                if supply_result["reasons"] or sector_result["reasons"]:
                    all_reasons = all_reasons + [
                        "[기술적 구조 미달] 수급·섹터 보너스 비적용 (base < 40)"
                    ]

            # ── VWAP 보너스 (분봉 데이터 있을 때만, base_score ≥ 40 게이트) ──
            minute_vwap_result = {"available": False, "score": 0, "vwap": None, "reasons": []}
            if minute_data and len(minute_data) >= 10 and base_score >= 40:
                total_vol = sum(c["volume"] for c in minute_data if c["volume"] > 0)
                if total_vol > 0:
                    vwap = sum(c["close"] * c["volume"] for c in minute_data if c["volume"] > 0) / total_vol
                    curr = float(ohlcv_data["Close"].iloc[-1])
                    if curr > vwap:
                        vwap_score = +8
                        vwap_reason = f"VWAP 상단 확인 ({vwap:,.0f}) — 매수세 우위"
                    else:
                        vwap_score = -5
                        vwap_reason = f"VWAP 하단 ({vwap:,.0f}) — 매도세 우위"
                    total_score = max(0.0, min(100.0, total_score + vwap_score))
                    minute_vwap_result = {
                        "available": True,
                        "score": vwap_score,
                        "vwap": round(vwap, 0),
                        "reasons": [vwap_reason],
                    }
                    all_reasons.append(vwap_reason)

            # 신호 강도 — base score가 낮으면 수급 보너스와 무관하게 HOLD 유지
            if base_score < 40:
                # 기술적 구조 미달: 항상 HOLD
                strength = SignalStrength.LOW
                signal = SignalType.HOLD
            elif total_score >= 65:
                strength = SignalStrength.HIGH
                signal = SignalType.BUY
            elif total_score >= 45:
                strength = SignalStrength.MEDIUM
                signal = SignalType.BUY
            else:
                strength = SignalStrength.LOW
                signal = SignalType.HOLD

            return {
                "signal": signal,
                "strength": strength,
                "score": round(total_score, 1),
                "base_score": round(base_score, 1),  # 수급·섹터 보너스 전 순수 기술 점수
                "reasons": all_reasons,
                # cup_handle / candle_volume을 top-level에 버블업 (signal_service 접근 편의)
                "cup_handle": pattern_result.get("cup_handle"),
                "candle_volume": pattern_result.get("candle_volume"),
                "breakdown": {
                    "volume": volume_result,
                    "technical": technical_result,
                    "pattern": pattern_result,
                    "momentum": mtf_result,
                    "supply": supply_result,
                    "sector": sector_result,
                    "minute_vwap": minute_vwap_result,
                }
            }

    def generate_exit_signal(self, entry_price: float, entry_time: datetime,
                           current_price: float, current_time: datetime,
                           position_size: float = 1.0,
                           atr: Optional[float] = None) -> Dict:
        """
        청산 신호 생성

        Returns:
            {
                "should_exit": True/False,
                "exit_type": "take_profit" | "stop_loss" | "time_based",
                "volume_pct": 매도 비율 (0.0~1.0),
                "reason": 청산 사유,
                "details": {...}
            }
        """
        # 익절 체크
        tp_strategy = TakeProfitStrategy(entry_price)
        tp_should_exit, tp_info = tp_strategy.check_exit(current_price, position_size)

        if tp_should_exit:
            return {
                "should_exit": True,
                "exit_type": "take_profit",
                "volume_pct": tp_info["volume_pct"],
                "reason": tp_info["reason"],
                "details": tp_info
            }

        # 손절 체크 (ATR 제공 시 동적 손절, 없으면 고정 -2%)
        sl_strategy = StopLossStrategy(entry_price, atr=atr)
        sl_should_exit, sl_info = sl_strategy.check_exit(current_price)

        if sl_should_exit:
            return {
                "should_exit": True,
                "exit_type": "stop_loss",
                "volume_pct": 1.0,  # 전량 청산
                "reason": sl_info["reason"],
                "details": sl_info
            }

        # 시간 기반 청산 체크
        time_strategy = TimeBasedExit(entry_time, holding_limit_minutes=30)
        time_should_exit, time_info = time_strategy.check_exit(current_time)

        if time_should_exit:
            return {
                "should_exit": True,
                "exit_type": "time_based",
                "volume_pct": 1.0,  # 전량 청산
                "reason": time_info["reason"],
                "details": time_info
            }

        return {
            "should_exit": False,
            "exit_type": None,
            "volume_pct": 0.0,
            "reason": "holding",
            "details": {}
        }
