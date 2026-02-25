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
        volume_surge = current_volume >= prev_volume * self.volume_surge_ratio
        if volume_surge:
            reasons.append(f"거래량 급증 ({current_volume / prev_volume:.2f}배)")
            score += 30

        # 조건 2: 가격 상승
        price_increase = current_price > prev_close * (1 + self.price_increase_ratio)
        if price_increase:
            change_pct = (current_price - prev_close) / prev_close * 100
            reasons.append(f"가격 상승 (+{change_pct:.2f}%)")
            score += 25

        # 조건 3: 거래량 MA5 대비 급증
        volume_ma5_breakout = current_volume >= volume_ma5 * 3
        if volume_ma5_breakout:
            reasons.append(f"거래량 MA5 돌파 ({current_volume / volume_ma5:.2f}배)")
            score += 25

        # 조건 4: 전일 대비 거래대금 증가
        prev_amount = prev_volume * prev_close
        current_amount = current_volume * current_price
        if current_amount > prev_amount * 2:
            reasons.append("거래대금 2배 이상 증가")
            score += 20

        # 신호 강도 결정
        if score >= 70:
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
            "price_change": (current_price - prev_close) / prev_close if prev_close > 0 else 0
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
        consolidation_range = (consolidation_high - consolidation_low) / consolidation_low

        # 횡보 조건: 변동폭 5% 이내
        if consolidation_range > 0.05:
            return False

        # 돌파 조건: 당일 종가가 횡보 고가 돌파
        breakout = current["Close"] > consolidation_high * 1.02

        return breakout

    def check_signal(self, ohlcv_data: pd.DataFrame) -> Dict:
        """가격 패턴 신호 체크"""
        if len(ohlcv_data) < 15:
            return {"signal": SignalType.HOLD, "strength": SignalStrength.LOW, "score": 0, "reasons": []}

        closes = ohlcv_data["Close"]
        reasons = []
        score = 0

        # 패턴 1: 저점 높이기
        higher_lows = self.detect_higher_lows(closes, 5)
        if higher_lows:
            reasons.append("저점 높이기 패턴")
            score += 30

        # 패턴 2: 횡보 후 돌파
        consolidation_breakout = self.detect_consolidation_breakout(ohlcv_data, 5)
        if consolidation_breakout:
            reasons.append("횡보 후 돌파")
            score += 40

        # 패턴 3: 상승 추세 (20일 수익률 > 0)
        if len(closes) >= 20:
            returns_20d = (closes.iloc[-1] - closes.iloc[-20]) / closes.iloc[-20]
            if returns_20d > 0:
                reasons.append(f"20일 상승 추세 (+{returns_20d*100:.1f}%)")
                score += 15

        # 신호 강도 결정
        if score >= 60:
            strength = SignalStrength.HIGH
            signal_type = SignalType.BUY
        elif score >= 40:
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
            {"ratio": 0.03, "volume_pct": 0.5, "name": "1차 익절 +3%"},
            {"ratio": 0.05, "volume_pct": 0.3, "name": "2차 익절 +5%"},
            {"ratio": 0.10, "volume_pct": 0.2, "name": "3차 익절 +10%"},
        ]
        self.executed_targets = set()

    def check_exit(self, current_price: float, position_size: float) -> Tuple[bool, Optional[Dict]]:
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
    """손절 전략"""

    def __init__(self, entry_price: float, stop_loss_ratio: float = -0.02,
                 trailing_stop: bool = True, trailing_ratio: float = -0.03):
        """
        Args:
            entry_price: 진입 가격
            stop_loss_ratio: 고정 손절 비율 (예: -0.02 = -2%)
            trailing_stop: 트레일링 스톱 사용 여부
            trailing_ratio: 트레일링 스톱 비율 (최고가 대비)
        """
        self.entry_price = entry_price
        self.stop_loss_ratio = stop_loss_ratio
        self.trailing_stop = trailing_stop
        self.trailing_ratio = trailing_ratio
        self.highest_price = entry_price

    def update_highest_price(self, current_price: float):
        """최고가 업데이트"""
        if current_price > self.highest_price:
            self.highest_price = current_price

    def check_exit(self, current_price: float) -> Tuple[bool, Optional[Dict]]:
        """
        손절 조건 체크

        Returns:
            (should_exit, exit_info)
        """
        self.update_highest_price(current_price)

        # 1. 고정 손절
        loss_ratio = (current_price - self.entry_price) / self.entry_price
        if loss_ratio <= self.stop_loss_ratio:
            return True, {
                "reason": "fixed_stop_loss",
                "loss_ratio": loss_ratio,
                "stop_price": self.entry_price * (1 + self.stop_loss_ratio)
            }

        # 2. 트레일링 스톱
        if self.trailing_stop:
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
# 통합 신호 매니저
# ═══════════════════════════════════════════════════════════════

class SignalManager:
    """진입/청산 신호 통합 관리"""

    def __init__(self):
        self.volume_signal = VolumeBreakoutSignal()
        self.technical_signal = TechnicalBreakoutSignal()
        self.pattern_signal = PricePatternSignal()

    def generate_entry_signal(self, ohlcv_data: pd.DataFrame, strategy: str = "combined") -> Dict:
        """
        진입 신호 생성

        Args:
            ohlcv_data: OHLCV 데이터
            strategy: "volume" | "technical" | "pattern" | "combined"

        Returns:
            종합 신호 정보
        """
        if strategy == "volume":
            return self.volume_signal.check_signal(ohlcv_data)
        elif strategy == "technical":
            return self.technical_signal.check_signal(ohlcv_data)
        elif strategy == "pattern":
            return self.pattern_signal.check_signal(ohlcv_data)
        else:  # combined
            volume_result = self.volume_signal.check_signal(ohlcv_data)
            technical_result = self.technical_signal.check_signal(ohlcv_data)
            pattern_result = self.pattern_signal.check_signal(ohlcv_data)

            # 종합 점수 (가중 평균)
            total_score = (
                volume_result["score"] * 0.4 +
                technical_result["score"] * 0.4 +
                pattern_result["score"] * 0.2
            )

            all_reasons = (
                volume_result["reasons"] +
                technical_result["reasons"] +
                pattern_result["reasons"]
            )

            # 신호 강도
            if total_score >= 70:
                strength = SignalStrength.HIGH
                signal = SignalType.BUY
            elif total_score >= 50:
                strength = SignalStrength.MEDIUM
                signal = SignalType.BUY
            else:
                strength = SignalStrength.LOW
                signal = SignalType.HOLD

            return {
                "signal": signal,
                "strength": strength,
                "score": total_score,
                "reasons": all_reasons,
                "breakdown": {
                    "volume": volume_result,
                    "technical": technical_result,
                    "pattern": pattern_result
                }
            }

    def generate_exit_signal(self, entry_price: float, entry_time: datetime,
                           current_price: float, current_time: datetime,
                           position_size: float = 1.0) -> Dict:
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

        # 손절 체크
        sl_strategy = StopLossStrategy(entry_price)
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
