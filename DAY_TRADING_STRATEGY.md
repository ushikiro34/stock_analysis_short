# 주식 단타매매 시스템 로직 설계

## 현재 시스템 분석

### 기존 구현 기능
- ✅ 급등주 필터링 (KR, US)
- ✅ 1달러 미만 주식 + 거래량 패턴 필터링
- ✅ 펀더멘털 분석 (PER, PBR, ROE, EPS)
- ✅ 기술적 지표 (MA20/60/120, RSI, 변동성)
- ✅ 분봉/일봉/주봉 데이터 수집
- ✅ WebSocket 실시간 체결 (KR)

### 부족한 부분
- ❌ 진입/청산 신호 로직
- ❌ 리스크 관리 (손절/익절)
- ❌ 백테스팅 시스템
- ❌ 실시간 알림
- ❌ 포지션 관리

---

## 단타매매 핵심 로직 설계

### 1. 진입 신호 (Entry Signals)

#### A. 거래량 기반 진입
```python
class VolumeBreakoutSignal:
    """거래량 돌파 진입 신호"""

    def check_signal(self, stock_data):
        # 조건 1: 거래량 급증 (전일 대비 2배 이상)
        volume_surge = current_volume >= prev_volume * 2

        # 조건 2: 가격 상승 (+ 거래대금 증가)
        price_increase = current_price > prev_close * 1.02

        # 조건 3: 거래량 5일 평균 대비 3배 이상
        volume_ma5_breakout = current_volume >= volume_ma5 * 3

        return volume_surge and price_increase and volume_ma5_breakout
```

#### B. 기술적 지표 기반 진입
```python
class TechnicalBreakoutSignal:
    """기술적 돌파 진입 신호"""

    def check_signal(self, technical_data):
        # 조건 1: 가격이 MA20 돌파
        price_above_ma20 = current_price > ma20 > ma60

        # 조건 2: RSI 과매도 탈출 (30~50 구간)
        rsi_bullish = 30 < rsi < 50

        # 조건 3: MACD 골든크로스
        macd_golden_cross = macd > signal

        # 조건 4: 볼린저밴드 하단 터치 후 반등
        bb_bounce = price > bb_lower and price < bb_middle

        return price_above_ma20 and rsi_bullish and macd_golden_cross
```

#### C. 가격 패턴 기반 진입
```python
class PricePatternSignal:
    """가격 패턴 진입 신호"""

    def check_signal(self, candles):
        # 패턴 1: 상승 돌파형 (컵앤핸들)
        cup_and_handle = self.detect_cup_and_handle(candles)

        # 패턴 2: 저점 높이기 (Higher Lows)
        higher_lows = self.detect_higher_lows(candles)

        # 패턴 3: 횡보 후 돌파 (Consolidation Breakout)
        consolidation_breakout = self.detect_consolidation_breakout(candles)

        return cup_and_handle or consolidation_breakout
```

---

### 2. 청산 신호 (Exit Signals)

#### A. 익절 (Take Profit)
```python
class TakeProfitStrategy:
    """익절 전략"""

    def __init__(self, entry_price):
        self.entry_price = entry_price
        self.targets = [
            {"ratio": 0.03, "volume": 0.5},  # +3% 도달 시 50% 청산
            {"ratio": 0.05, "volume": 0.3},  # +5% 도달 시 30% 청산
            {"ratio": 0.10, "volume": 0.2},  # +10% 도달 시 나머지 청산
        ]

    def check_exit(self, current_price, position_size):
        profit_ratio = (current_price - self.entry_price) / self.entry_price

        for target in self.targets:
            if profit_ratio >= target["ratio"]:
                sell_volume = position_size * target["volume"]
                return sell_volume

        return 0
```

#### B. 손절 (Stop Loss)
```python
class StopLossStrategy:
    """손절 전략"""

    def __init__(self, entry_price):
        self.entry_price = entry_price
        self.stop_loss_ratio = -0.02  # -2% 손절
        self.trailing_stop = True
        self.highest_price = entry_price

    def check_exit(self, current_price):
        # 고정 손절
        if current_price <= self.entry_price * (1 + self.stop_loss_ratio):
            return True, "fixed_stop_loss"

        # 트레일링 스톱 (최고가 대비 -3%)
        if self.trailing_stop:
            self.highest_price = max(self.highest_price, current_price)
            if current_price <= self.highest_price * 0.97:
                return True, "trailing_stop"

        return False, None
```

#### C. 시간 기반 청산
```python
class TimeBasedExit:
    """시간 기반 청산 (단타 특화)"""

    def check_exit(self, entry_time, current_time):
        holding_minutes = (current_time - entry_time).total_seconds() / 60

        # 30분 이내 미익절 시 강제 청산
        if holding_minutes >= 30:
            return True, "time_limit_30min"

        # 장 마감 10분 전 무조건 청산
        if self.is_near_market_close(current_time, minutes=10):
            return True, "market_close"

        return False, None
```

---

### 3. 리스크 관리 (Risk Management)

#### A. 포지션 사이징
```python
class PositionSizer:
    """포지션 크기 계산"""

    def __init__(self, total_capital, max_risk_per_trade=0.02):
        self.total_capital = total_capital
        self.max_risk_per_trade = max_risk_per_trade  # 거래당 최대 2% 리스크

    def calculate_position_size(self, entry_price, stop_loss_price):
        # 1회 거래 최대 손실 금액
        max_loss_amount = self.total_capital * self.max_risk_per_trade

        # 주당 손실 금액
        loss_per_share = abs(entry_price - stop_loss_price)

        # 매수 가능 주식 수
        position_size = max_loss_amount / loss_per_share

        # 자본금 대비 최대 30% 이내
        max_position_value = self.total_capital * 0.3
        max_shares_by_capital = max_position_value / entry_price

        return min(position_size, max_shares_by_capital)
```

#### B. 동시 포지션 제한
```python
class PortfolioManager:
    """포트폴리오 관리"""

    def __init__(self, max_positions=3):
        self.max_positions = max_positions  # 최대 3종목 동시 보유
        self.current_positions = []

    def can_open_position(self):
        return len(self.current_positions) < self.max_positions

    def add_position(self, position):
        if self.can_open_position():
            self.current_positions.append(position)
            return True
        return False
```

---

### 4. 실시간 모니터링 & 알림

#### A. 실시간 신호 감지
```python
class RealTimeScanner:
    """실시간 신호 스캐너"""

    async def scan_stocks(self, watchlist):
        signals = []

        for stock in watchlist:
            # 실시간 체결 데이터 수집
            realtime_data = await self.get_realtime_data(stock)

            # 진입 신호 체크
            entry_signal = self.check_entry_signals(realtime_data)
            if entry_signal:
                signals.append({
                    "code": stock,
                    "signal": "BUY",
                    "price": realtime_data["price"],
                    "strength": entry_signal["strength"],
                    "timestamp": datetime.now()
                })

            # 보유 중인 종목 청산 신호 체크
            if stock in self.positions:
                exit_signal = self.check_exit_signals(realtime_data)
                if exit_signal:
                    signals.append({
                        "code": stock,
                        "signal": "SELL",
                        "reason": exit_signal["reason"],
                        "timestamp": datetime.now()
                    })

        return signals
```

#### B. 알림 시스템
```python
class AlertSystem:
    """알림 시스템 (Telegram, Email, WebSocket)"""

    async def send_alert(self, signal):
        message = f"""
        🚨 거래 신호 발생

        종목: {signal['code']} {signal['name']}
        신호: {signal['signal']}
        가격: ${signal['price']}
        시간: {signal['timestamp']}
        사유: {signal.get('reason', 'N/A')}
        """

        # Telegram 알림
        await self.send_telegram(message)

        # WebSocket 브로드캐스트 (프론트엔드)
        await self.websocket_broadcast(signal)

        # 이메일 (중요 신호만)
        if signal.get('strength') == 'high':
            await self.send_email(message)
```

---

### 5. 백테스팅 시스템

```python
class Backtester:
    """전략 백테스팅"""

    def __init__(self, strategy, initial_capital=10000):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = []
        self.trades = []

    async def run_backtest(self, symbols, start_date, end_date):
        for symbol in symbols:
            # 과거 데이터 로드
            historical_data = await self.load_historical_data(
                symbol, start_date, end_date
            )

            for i, candle in enumerate(historical_data):
                # 진입 신호 체크
                if self.strategy.check_entry(historical_data[:i+1]):
                    position = self.open_position(candle)
                    self.positions.append(position)

                # 청산 신호 체크
                for position in self.positions:
                    if self.strategy.check_exit(position, candle):
                        trade = self.close_position(position, candle)
                        self.trades.append(trade)

        return self.generate_report()

    def generate_report(self):
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['profit'] > 0]
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0

        total_profit = sum(t['profit'] for t in self.trades)
        roi = (self.capital - self.initial_capital) / self.initial_capital * 100

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_profit": total_profit,
            "roi": roi,
            "final_capital": self.capital,
            "trades": self.trades
        }
```

---

## 단타매매 시스템 구현 우선순위

### Phase 1: 신호 생성 (1-2주)
1. ✅ **거래량 돌파 신호** - VolumeBreakoutSignal
2. ✅ **기술적 지표 추가** - MACD, Bollinger Bands, Stochastic
3. ✅ **신호 강도 점수화** - 여러 지표 종합 점수

### Phase 2: 리스크 관리 (1주)
4. ✅ **손절/익절 로직** - StopLossStrategy, TakeProfitStrategy
5. ✅ **포지션 사이징** - PositionSizer
6. ✅ **포트폴리오 관리** - PortfolioManager

### Phase 3: 실시간 시스템 (1-2주)
7. ✅ **실시간 스캐너** - RealTimeScanner
8. ✅ **알림 시스템** - Telegram/Email/WebSocket
9. ✅ **워치리스트 자동 생성** - 조건 부합 종목 자동 추가

### Phase 4: 백테스팅 & 최적화 (2-3주)
10. ✅ **백테스팅 엔진** - Backtester
11. ✅ **파라미터 최적화** - 최적 손절/익절 비율 찾기
12. ✅ **성과 분석 대시보드** - 승률, 손익비, MDD 등

### Phase 5: 자동 매매 (선택 사항)
13. ⚠️ **API 연동** - KIS API, Interactive Brokers 등
14. ⚠️ **자동 주문 실행** - 신호 발생 시 자동 매수/매도
15. ⚠️ **안전장치** - 일일 최대 손실 제한, 긴급 중단

---

## 단타매매 추천 전략 조합

### 전략 A: 거래량 급증 + 단기 MA 돌파
```
진입 조건:
- 거래량 전일 대비 2배 이상
- 가격이 MA20 상향 돌파
- RSI 30~70 (과매도/과매수 제외)

청산 조건:
- +3% 익절 또는 -2% 손절
- 30분 이내 청산
```

### 전략 B: 1달러 미만 페니스탁 (고위험/고수익)
```
진입 조건:
- 가격 < $1
- 거래량 패턴: D-3 > D-2, D-1 그리고 D-0 급증
- 당일 상승률 > +5%

청산 조건:
- +10% 익절 (50% 청산) → +20% 나머지 청산
- -5% 손절 (전량 청산)
- 1시간 이내 청산
```

### 전략 C: 한국 급등주 (2만원 이하)
```
진입 조건:
- 가격 < 20,000원
- 거래량 순위 Top 20
- 종합 스코어 > 60점

청산 조건:
- +5% 익절 또는 -2% 손절
- 장 마감 10분 전 무조건 청산
```

---

## 데이터베이스 스키마 (필요 시)

```sql
-- 거래 기록
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20),
    name VARCHAR(100),
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    entry_price DECIMAL(10, 2),
    exit_price DECIMAL(10, 2),
    quantity INTEGER,
    profit DECIMAL(10, 2),
    profit_ratio DECIMAL(5, 2),
    strategy VARCHAR(50),
    exit_reason VARCHAR(50)
);

-- 신호 로그
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20),
    signal_type VARCHAR(10),  -- BUY, SELL
    signal_strength VARCHAR(10),  -- high, medium, low
    price DECIMAL(10, 2),
    timestamp TIMESTAMP,
    indicators JSONB,
    executed BOOLEAN DEFAULT FALSE
);

-- 워치리스트
CREATE TABLE watchlist (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE,
    name VARCHAR(100),
    market VARCHAR(10),
    added_at TIMESTAMP,
    strategy VARCHAR(50),
    notes TEXT
);
```

---

## 참고 자료

### 추천 라이브러리
- `ta-lib` - 기술적 지표 계산
- `backtrader` - 백테스팅 프레임워크
- `python-telegram-bot` - 텔레그램 알림
- `schedule` - 정기 스캐닝

### 다음 단계
1. 어떤 Phase부터 시작할까요?
2. 특정 전략에 집중하시겠습니까?
3. 백테스팅부터 하시겠습니까?
