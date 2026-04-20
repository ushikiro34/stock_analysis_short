"""
캔들 해부 + 거래량 조합 신호 테스트
Priority 1/2 구현 검증
"""
import pandas as pd
from datetime import datetime, timezone

from ..core.signals import PricePatternSignal, MinuteBreakoutSignal
from ..core.paper_engine import PaperPosition


# ─────────────────────────────────────────────────────────────
# 헬퍼: 테스트용 OHLCV DataFrame 생성
# ─────────────────────────────────────────────────────────────

def make_ohlcv(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["Open", "High", "Low", "Close", "Volume"])
    return df


def base_candle(o=100, h=110, l=90, c=105, v=1000):
    return dict(Open=o, High=h, Low=l, Close=c, Volume=v)


def resistance_candle(price=110, vol=3000):
    """윗꼬리 큰 캔들: high=price, close≈low (upper_shadow_ratio ≈ 0.70)"""
    # range = 10, upper = 7 → upper_r ≈ 0.70
    return dict(Open=price - 9, High=price, Low=price - 10, Close=price - 7, Volume=vol)


def bullish_persistence(low=90, high=112, vol=4000):
    """버팀 양봉: 밑꼬리 크고 몸통 두꺼운 양봉
    range=22, open=96, close=108
    body=12 (54.5% ≥ 35%), lower=6 (27.3% ≥ 25%), is_bull=True
    """
    return dict(Open=96, High=high, Low=low, Close=108, Volume=vol)


# ─────────────────────────────────────────────────────────────
# 1. detect_candle_volume_resistance
# ─────────────────────────────────────────────────────────────

class TestDetectCandleVolumeResistance:
    def setup_method(self):
        self.signal = PricePatternSignal()

    def _make_data_with_resistance(self, cur_vol=5000, cur_close=108):
        rows = []
        # 15개 일반 캔들 (평균 거래량 ~1000)
        for _ in range(13):
            rows.append(base_candle(v=1000))
        # 저항 캔들 (거래량 3000, 윗꼬리 비율 높음)
        rows.append(resistance_candle(price=110, vol=3000))
        # 현재 캔들: 버팀 양봉 (open=96, low=90 → lower_r=27%, body_r=55%)
        rows.append(dict(Open=96, High=112, Low=90, Close=cur_close, Volume=cur_vol))
        return make_ohlcv(rows)

    def test_resistance_candle_detected(self):
        df = self._make_data_with_resistance()
        result = self.signal.detect_candle_volume_resistance(df, lookback=10)
        assert len(result["resistance_candles"]) >= 1
        assert result["max_resistance_volume"] >= 3000
        assert result["resistance_price"] == 110.0

    def test_entry_signal_strong_breakout(self):
        """저항 거래량(3000)의 130% 이상(3900+) → strong entry"""
        df = self._make_data_with_resistance(cur_vol=4000, cur_close=108)
        result = self.signal.detect_candle_volume_resistance(df, lookback=10)
        assert result["entry_signal"] is True
        assert result["entry_strength"] == "strong"
        assert result["score"] >= 40

    def test_entry_signal_normal_breakout(self):
        """저항 거래량(3000)의 100~129% → normal entry"""
        df = self._make_data_with_resistance(cur_vol=3100, cur_close=108)
        result = self.signal.detect_candle_volume_resistance(df, lookback=10)
        assert result["entry_signal"] is True
        assert result["entry_strength"] == "normal"

    def test_fake_breakout_risk(self):
        """저항가 ±3% 이내 + 거래량 80% 미만 → fake_breakout_risk"""
        # 저항가 = 110, 현재가 = 108.35 (1.5% below) → near_resistance = True
        # 현재 거래량 = 1500 < 3000 * 0.8 = 2400 → vol_below = True
        df = self._make_data_with_resistance(cur_vol=1500, cur_close=109)
        result = self.signal.detect_candle_volume_resistance(df, lookback=10)
        assert result["fake_breakout_risk"] is True
        assert result["score"] < 0


# ─────────────────────────────────────────────────────────────
# 2. PaperPosition._check_exit 저항 거래량 미달 익절
# ─────────────────────────────────────────────────────────────

def make_position(resistance_price=0.0, resistance_volume=0.0,
                  entry_price=1000.0, qty=10):
    return PaperPosition(
        db_id=1,
        code="TEST",
        name="테스트",
        market="KR",
        entry_time=datetime.now(timezone.utc),
        entry_price=entry_price,
        quantity=qty,
        highest_price=entry_price,
        resistance_price=resistance_price,
        resistance_volume=resistance_volume,
    )


def make_engine():
    from ..core.paper_engine import PaperEngine
    return PaperEngine()


class TestResistanceVolumeExit:
    def setup_method(self):
        self.engine = make_engine()

    def test_no_resistance_data_no_trigger(self):
        """저항 데이터 없으면 발동 안 함"""
        pos = make_position(resistance_price=0.0, resistance_volume=0.0)
        current_price = 1015.0  # +1.5%
        exit_, reason, vol_pct = self.engine._check_exit(pos, current_price, current_volume=100)
        assert reason != "저항거래량미달_익절"

    def test_no_current_volume_no_trigger(self):
        """current_volume=0 이면 발동 안 함"""
        pos = make_position(resistance_price=1015.0, resistance_volume=5000.0)
        exit_, reason, vol_pct = self.engine._check_exit(pos, 1015.0, current_volume=0)
        assert reason != "저항거래량미달_익절"

    def test_below_one_pct_pnl_no_trigger(self):
        """수익 +1% 미만이면 발동 안 함"""
        pos = make_position(resistance_price=1005.0, resistance_volume=5000.0)
        exit_, reason, vol_pct = self.engine._check_exit(pos, 1005.0, current_volume=1000)
        # +0.5% → should not trigger
        assert reason != "저항거래량미달_익절"

    def test_trigger_near_resistance_low_volume(self):
        """조건 충족 → 저항거래량미달_익절, 50% 청산"""
        pos = make_position(resistance_price=1020.0, resistance_volume=5000.0,
                            entry_price=1000.0)
        # current_price: 1.5% below resistance (1020 * 0.985 ≈ 1004.7... wait)
        # We need pnl >= 1% AND near resistance AND low volume
        # entry=1000, resistance=1020
        # current_price = 1015 → pnl=+1.5%, distance from 1020 = 0.49% → near
        # volume = 3000 < 5000 * 0.70 = 3500 → weak
        current_price = 1015.0
        exit_, reason, vol_pct = self.engine._check_exit(
            pos, current_price, current_volume=3000
        )
        assert exit_ is True
        assert reason == "저항거래량미달_익절"
        assert vol_pct == 0.5

    def test_strong_volume_no_trigger(self):
        """거래량이 충분하면 발동 안 함"""
        pos = make_position(resistance_price=1020.0, resistance_volume=5000.0,
                            entry_price=1000.0)
        current_price = 1015.0  # +1.5%, near resistance
        # volume >= 70% of 5000 → 3500+
        exit_, reason, vol_pct = self.engine._check_exit(
            pos, current_price, current_volume=4000
        )
        assert reason != "저항거래량미달_익절"


# ─────────────────────────────────────────────────────────────
# 3. 컵앤핸들 소멸(failed) 감지
# ─────────────────────────────────────────────────────────────

class TestCupHandleFailed:
    def setup_method(self):
        self.signal = PricePatternSignal()

    def _make_cup_handle_data(self, cur_price_ratio=0.80):
        """
        컵 구조: 80일 데이터
          - 좌측 림: 100 (초반 20일)
          - 바닥: 65 (중간 30일, 깊이 35%)
          - 우측 림: 100 (후반 20일)
          - 핸들: 5일, 현재가 = right_rim * cur_price_ratio
        """
        import numpy as np
        rows = []
        # 좌측 림 구간 (고점 100)
        for i in range(20):
            rows.append(dict(Open=98, High=100, Low=95, Close=100 - i * 0.1, Volume=2000))
        # 하락 구간 (100 → 65)
        for i in range(15):
            p = 100 - (i + 1) * (35 / 15)
            rows.append(dict(Open=p+1, High=p+2, Low=p-1, Close=p, Volume=1500))
        # 바닥 구간 (65 근방)
        for i in range(10):
            rows.append(dict(Open=65, High=67, Low=63, Close=65, Volume=1000))
        # 상승 구간 (65 → 100)
        for i in range(15):
            p = 65 + (i + 1) * (35 / 15)
            rows.append(dict(Open=p-1, High=p+1, Low=p-2, Close=p, Volume=1800))
        # 우측 림 구간 (100 근방)
        for i in range(15):
            rows.append(dict(Open=99, High=101, Low=97, Close=100, Volume=1500))
        # 핸들 + 현재가 (last candle = cur_price_ratio * right_rim)
        cur = round(100 * cur_price_ratio, 1)
        for i in range(4):
            rows.append(dict(Open=99, High=100, Low=96, Close=98, Volume=800))
        rows.append(dict(Open=cur-1, High=cur+1, Low=cur-2, Close=cur, Volume=900))
        return make_ohlcv(rows)

    def test_failed_status_detected(self):
        """현재가 우측 림 대비 -14% → breakout_status = 'failed'"""
        df = self._make_cup_handle_data(cur_price_ratio=0.86)
        result = self.signal.detect_cup_and_handle(df)
        # 패턴 자체는 감지되어야 함 (score >= 40)
        assert result.get("score", 0) >= 40
        assert result.get("breakout_status") == "failed"
        assert result.get("is_cup_handle") is False  # 소멸 = 진입 신호 아님

    def test_forming_status_not_failed(self):
        """현재가 우측 림 대비 -8% → 'forming' (아직 소멸 아님)"""
        df = self._make_cup_handle_data(cur_price_ratio=0.92)
        result = self.signal.detect_cup_and_handle(df)
        if result.get("score", 0) >= 40:
            assert result.get("breakout_status") in ("forming", "pre", "fresh")


# ─────────────────────────────────────────────────────────────
# 4. MinuteBreakoutSignal candle_volume 필드
# ─────────────────────────────────────────────────────────────

class TestMinuteBreakoutCandleVolume:
    def setup_method(self):
        self.signal = MinuteBreakoutSignal()

    def _make_minute_candles(self):
        candles = []
        for i in range(20):
            candles.append({
                "open": 100, "high": 110, "low": 90, "close": 105,
                "volume": 1000, "time": f"09:{30+i:02d}:00"
            })
        return candles

    def test_candle_volume_in_result(self):
        candles = self._make_minute_candles()
        result = self.signal.check_signal(candles)
        assert "candle_volume" in result
        assert isinstance(result["candle_volume"], dict)
