class IndicatorEngine:
    @staticmethod
    def calculate_ma(prices, period: int):
        import pandas as pd
        s = pd.Series(prices) if not isinstance(prices, pd.Series) else prices
        return s.rolling(window=period).mean()

    @staticmethod
    def calculate_rsi(prices, period: int = 14):
        import pandas as pd
        s = pd.Series(prices) if not isinstance(prices, pd.Series) else prices
        delta = s.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def calculate_volatility(returns, period: int = 20):
        import pandas as pd
        s = pd.Series(returns) if not isinstance(returns, pd.Series) else returns
        return s.rolling(window=period).std()

    @staticmethod
    def calculate_mdd(prices):
        import pandas as pd
        s = pd.Series(prices) if not isinstance(prices, pd.Series) else prices
        peak = s.cummax()
        drawdown = (s - peak) / peak
        return drawdown.min()

    @staticmethod
    def calculate_ema(prices, period: int):
        """지수 이동평균 (Exponential Moving Average)"""
        import pandas as pd
        s = pd.Series(prices) if not isinstance(prices, pd.Series) else prices
        return s.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_macd(prices, fast=12, slow=26, signal=9):
        """MACD (Moving Average Convergence Divergence)"""
        import pandas as pd
        s = pd.Series(prices) if not isinstance(prices, pd.Series) else prices

        ema_fast = s.ewm(span=fast, adjust=False).mean()
        ema_slow = s.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }

    @staticmethod
    def calculate_bollinger_bands(prices, period: int = 20, std_dev: float = 2.0):
        """볼린저 밴드 (Bollinger Bands)"""
        import pandas as pd
        s = pd.Series(prices) if not isinstance(prices, pd.Series) else prices

        ma = s.rolling(window=period).mean()
        std = s.rolling(window=period).std()

        upper_band = ma + (std * std_dev)
        lower_band = ma - (std * std_dev)

        return {
            "upper": upper_band,
            "middle": ma,
            "lower": lower_band
        }

    @staticmethod
    def calculate_stochastic(high, low, close, k_period: int = 14, d_period: int = 3):
        """스토캐스틱 (Stochastic Oscillator)"""
        import pandas as pd

        high_s = pd.Series(high) if not isinstance(high, pd.Series) else high
        low_s = pd.Series(low) if not isinstance(low, pd.Series) else low
        close_s = pd.Series(close) if not isinstance(close, pd.Series) else close

        lowest_low = low_s.rolling(window=k_period).min()
        highest_high = high_s.rolling(window=k_period).max()

        k_line = 100 * ((close_s - lowest_low) / (highest_high - lowest_low))
        d_line = k_line.rolling(window=d_period).mean()

        return {
            "k": k_line,
            "d": d_line
        }

    @staticmethod
    def calculate_volume_ma(volumes, period: int = 5):
        """거래량 이동평균"""
        import pandas as pd
        s = pd.Series(volumes) if not isinstance(volumes, pd.Series) else volumes
        return s.rolling(window=period).mean()

    @staticmethod
    def calculate_atr(high, low, close, period: int = 14):
        """ATR (Average True Range) — 변동성 기반 동적 손절 계산용

        True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
        ATR = TR의 period일 단순이동평균

        현업 트레이더 활용 예:
            손절가 = 진입가 - ATR × 1.5  (변동성이 클수록 여유 손절)
            목표가 = 진입가 + ATR × 3.0  (리스크:리워드 = 1:2)

        Args:
            high:   고가 시리즈
            low:    저가 시리즈
            close:  종가 시리즈
            period: ATR 기간 (기본 14)

        Returns:
            pd.Series — ATR 값 (초기 period-1봉은 NaN)
        """
        import pandas as pd
        high_s = pd.Series(high) if not isinstance(high, pd.Series) else high
        low_s = pd.Series(low) if not isinstance(low, pd.Series) else low
        close_s = pd.Series(close) if not isinstance(close, pd.Series) else close

        prev_close = close_s.shift(1)
        true_range = pd.concat([
            high_s - low_s,
            (high_s - prev_close).abs(),
            (low_s - prev_close).abs(),
        ], axis=1).max(axis=1)

        return true_range.rolling(window=period).mean()
