# 단타매매 신호 시스템 가이드

## 개요

이 시스템은 주식 단타매매를 위한 진입/청산 신호를 자동으로 생성합니다.

## 구현된 기능

### ✅ 기술적 지표 (indicators.py)
- **이동평균 (MA)**: 20, 60, 120일
- **지수이동평균 (EMA)**: 빠른 추세 반영
- **RSI**: 과매수/과매도 판단
- **MACD**: 추세 전환 포착
- **볼린저 밴드**: 변동성 기반 진입점
- **스토캐스틱**: 모멘텀 분석
- **거래량 이동평균**: 거래량 급증 감지

### ✅ 진입 신호 (signals.py)

#### 1. 거래량 돌파 신호 (VolumeBreakoutSignal)
```python
조건:
- 거래량 전일 대비 2배 이상
- 가격 2% 이상 상승
- 거래량 MA5 대비 3배 이상
- 거래대금 2배 이상 증가

점수 배점:
- 거래량 급증: 30점
- 가격 상승: 25점
- 거래량 MA5 돌파: 25점
- 거래대금 증가: 20점
```

#### 2. 기술적 돌파 신호 (TechnicalBreakoutSignal)
```python
조건:
- MA20 상향 돌파
- MA20 > MA60 정배열
- RSI 30~70 적정 범위
- MACD 골든크로스
- 볼린저밴드 하단 반등

점수 배점:
- MA20 돌파: 25점
- MA 정배열: 15점
- RSI 적정: 15점
- RSI 상승: 10점
- MACD 골든크로스: 30점
- 볼린저밴드 반등: 20점
```

#### 3. 가격 패턴 신호 (PricePatternSignal)
```python
패턴:
- 저점 높이기 (Higher Lows)
- 횡보 후 돌파 (Consolidation Breakout)
- 상승 추세 (20일 수익률 > 0)

점수 배점:
- 저점 높이기: 30점
- 횡보 후 돌파: 40점
- 상승 추세: 15점
```

#### 4. 통합 신호 (Combined Strategy)
```python
종합 점수 = 거래량 신호 × 0.4 + 기술적 신호 × 0.4 + 패턴 신호 × 0.2

신호 강도:
- 70점 이상: HIGH (강력 매수)
- 50~69점: MEDIUM (매수 고려)
- 50점 미만: LOW (관망)
```

### ✅ 청산 신호 (signals.py)

#### 1. 익절 전략 (TakeProfitStrategy)
```python
분할 익절:
- +3% 도달: 50% 매도
- +5% 도달: 30% 매도 (누적 80%)
- +10% 도달: 20% 매도 (전량 청산)
```

#### 2. 손절 전략 (StopLossStrategy)
```python
고정 손절:
- 진입가 대비 -2% 도달 시 전량 청산

트레일링 스톱:
- 최고가 대비 -3% 하락 시 전량 청산
- 수익이 발생한 후 적용됨
```

#### 3. 시간 기반 청산 (TimeBasedExit)
```python
시간 제한:
- 30분 이상 보유 시 자동 청산
- 장 마감 10분 전 무조건 청산
```

---

## API 엔드포인트

### 1. 진입 신호 조회

#### GET `/signals/entry/{code}`

단일 종목의 진입 신호를 조회합니다.

**파라미터:**
- `code` (path): 종목 코드
- `market` (query): "KR" | "US" (기본값: "KR")
- `strategy` (query): "volume" | "technical" | "pattern" | "combined" (기본값: "combined")

**예시:**
```bash
# 미국 애플 주식 진입 신호
curl "http://localhost:8000/signals/entry/AAPL?market=US&strategy=combined"

# 한국 삼성전자 진입 신호
curl "http://localhost:8000/signals/entry/005930?market=KR&strategy=combined"
```

**응답:**
```json
{
  "code": "AAPL",
  "market": "US",
  "signal": "BUY",
  "strength": "high",
  "score": 77.0,
  "reasons": [
    "거래량 급증 (2.62배)",
    "가격 상승 (+14.89%)",
    "MACD 골든크로스"
  ],
  "current_price": 272.14,
  "timestamp": "2026-02-25T17:30:06",
  "breakdown": {
    "volume": {"score": 80, "signal": "BUY"},
    "technical": {"score": 70, "signal": "BUY"},
    "pattern": {"score": 45, "signal": "HOLD"}
  }
}
```

---

### 2. 급등주 진입 신호 스캔

#### GET `/signals/scan`

급등주 목록에서 진입 신호를 스캔합니다.

**파라미터:**
- `market` (query): "KR" | "US" (기본값: "KR")
- `strategy` (query): 신호 전략 (기본값: "combined")
- `min_score` (query): 최소 점수 (기본값: 60)

**예시:**
```bash
# 미국 급등주 중 점수 60점 이상
curl "http://localhost:8000/signals/scan?market=US&min_score=60"

# 한국 급등주 중 점수 70점 이상 (강력 매수 신호만)
curl "http://localhost:8000/signals/scan?market=KR&min_score=70"
```

**응답:**
```json
[
  {
    "code": "DRS",
    "market": "US",
    "signal": "BUY",
    "strength": "high",
    "score": 77.0,
    "reasons": [
      "거래량 급증 (2.62배)",
      "가격 상승 (+14.89%)",
      "거래대금 2배 이상 증가"
    ],
    "current_price": 43.82,
    "timestamp": "2026-02-25T17:30:06",
    "stock_info": {
      "code": "DRS",
      "name": "Leonardo DRS, Inc.",
      "price": 43.82,
      "change_rate": 14.89,
      "volume": 1500000
    }
  },
  ...
]
```

---

### 3. 청산 신호 조회

#### POST `/signals/exit`

보유 중인 포지션의 청산 신호를 조회합니다.

**파라미터 (JSON Body):**
- `code` (string): 종목 코드
- `entry_price` (number): 진입 가격
- `entry_time` (string): 진입 시각 (ISO 8601 형식)
- `market` (string): "KR" | "US" (기본값: "KR")

**예시:**
```bash
curl -X POST "http://localhost:8000/signals/exit" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "AAPL",
    "entry_price": 250.0,
    "entry_time": "2026-02-25T09:30:00",
    "market": "US"
  }'
```

**응답 (익절):**
```json
{
  "code": "AAPL",
  "market": "US",
  "should_exit": true,
  "exit_type": "take_profit",
  "volume_pct": 0.5,
  "reason": "1차 익절 +3%",
  "current_price": 257.5,
  "entry_price": 250.0,
  "profit_loss": 7.5,
  "profit_loss_pct": 3.0,
  "holding_time": 15.5,
  "timestamp": "2026-02-25T09:45:30",
  "details": {
    "profit_ratio": 0.03,
    "target_ratio": 0.03
  }
}
```

**응답 (손절):**
```json
{
  "code": "AAPL",
  "should_exit": true,
  "exit_type": "stop_loss",
  "volume_pct": 1.0,
  "reason": "fixed_stop_loss",
  "current_price": 245.0,
  "profit_loss": -5.0,
  "profit_loss_pct": -2.0,
  "details": {
    "reason": "fixed_stop_loss",
    "loss_ratio": -0.02,
    "stop_price": 245.0
  }
}
```

**응답 (보유):**
```json
{
  "code": "AAPL",
  "should_exit": false,
  "exit_type": null,
  "volume_pct": 0.0,
  "reason": "holding",
  "current_price": 252.0,
  "profit_loss": 2.0,
  "profit_loss_pct": 0.8,
  "holding_time": 10.2
}
```

---

## 사용 예시

### Python 클라이언트

```python
import asyncio
from backend.core.signal_service import (
    generate_entry_signal,
    generate_exit_signal,
    scan_signals_from_surge_stocks
)
from datetime import datetime

async def trading_bot():
    # 1. 급등주 스캔
    signals = await scan_signals_from_surge_stocks(
        market="US",
        strategy="combined",
        min_score=70  # 강력 매수 신호만
    )

    for signal in signals:
        if signal['signal'] == 'BUY' and signal['strength'] == 'high':
            print(f"매수 신호: {signal['code']} - {signal['score']}점")

            # 매수 주문 (실제 브로커 API 연동 필요)
            # order = place_buy_order(signal['code'], ...)

            # 포지션 추적
            entry_price = signal['current_price']
            entry_time = datetime.now()

            # 2. 청산 신호 모니터링
            while True:
                await asyncio.sleep(60)  # 1분마다 체크

                exit_signal = await generate_exit_signal(
                    code=signal['code'],
                    entry_price=entry_price,
                    entry_time=entry_time,
                    market="US"
                )

                if exit_signal['should_exit']:
                    print(f"청산 신호: {exit_signal['reason']}")
                    print(f"손익률: {exit_signal['profit_loss_pct']:.2f}%")

                    # 매도 주문
                    # place_sell_order(...)
                    break

asyncio.run(trading_bot())
```

### JavaScript/TypeScript 클라이언트

```typescript
// 진입 신호 조회
async function getEntrySignal(code: string, market: string = 'US') {
  const response = await fetch(
    `http://localhost:8000/signals/entry/${code}?market=${market}`
  );
  return await response.json();
}

// 급등주 스캔
async function scanSignals(market: string = 'US', minScore: number = 60) {
  const response = await fetch(
    `http://localhost:8000/signals/scan?market=${market}&min_score=${minScore}`
  );
  return await response.json();
}

// 청산 신호 조회
async function getExitSignal(
  code: string,
  entryPrice: number,
  entryTime: string,
  market: string = 'US'
) {
  const response = await fetch('http://localhost:8000/signals/exit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, entry_price: entryPrice, entry_time: entryTime, market })
  });
  return await response.json();
}

// 사용 예시
const signals = await scanSignals('US', 70);
console.log(`발견된 신호: ${signals.length}개`);

for (const signal of signals) {
  if (signal.signal === 'BUY' && signal.strength === 'high') {
    console.log(`${signal.code}: ${signal.score}점 - ${signal.reasons.join(', ')}`);
  }
}
```

---

## 테스트

### 테스트 실행
```bash
python test_trading_signals.py
```

### 테스트 결과 예시
```
🚀 단타매매 신호 로직 테스트

📊 진입 신호 테스트
종목: Apple Inc. (AAPL) - US
신호: BUY
강도: medium
점수: 62.0/100
현재가: $272.14

발생 이유:
  1. 가격 상승 (+2.24%)
  2. RSI 적정 범위 (52.5)
  3. MACD 골든크로스

🔍 급등주 진입 신호 스캔 테스트
✅ 8개 신호 발견

1. DRS - Leonardo DRS, Inc.
   신호: BUY (high)
   점수: 77.0/100
   현재가: $43.82
```

---

## 전략 커스터마이징

### 손절/익절 비율 변경

```python
# signals.py에서 수정

# 익절 목표 변경
targets = [
    {"ratio": 0.02, "volume_pct": 0.3, "name": "1차 익절 +2%"},  # 더 빠른 익절
    {"ratio": 0.04, "volume_pct": 0.4, "name": "2차 익절 +4%"},
    {"ratio": 0.08, "volume_pct": 0.3, "name": "3차 익절 +8%"},
]

# 손절 비율 변경
stop_loss_ratio = -0.015  # -1.5% 손절 (더 빡빡하게)
trailing_ratio = -0.02    # 최고가 대비 -2% 트레일링
```

### 시간 제한 변경

```python
# 최대 보유 시간 변경
holding_limit_minutes = 60  # 1시간으로 연장

# 장 마감 시각 설정
market_close_time = "15:20"  # 한국: 15:20, 미국: 16:00 (ET)
```

### 신호 점수 가중치 조정

```python
# signal_service.py - generate_entry_signal()

# 거래량 중시 전략
total_score = (
    volume_result["score"] * 0.6 +    # 거래량 60%
    technical_result["score"] * 0.3 +  # 기술적 30%
    pattern_result["score"] * 0.1      # 패턴 10%
)

# 기술적 지표 중시 전략
total_score = (
    volume_result["score"] * 0.2 +
    technical_result["score"] * 0.6 +
    pattern_result["score"] * 0.2
)
```

---

## 다음 단계

1. **실시간 알림** - Telegram Bot 연동
2. **백테스팅** - 과거 데이터로 전략 검증
3. **자동 매매** - 브로커 API 연동
4. **포트폴리오 관리** - 여러 종목 동시 관리
5. **리스크 관리** - 일일 최대 손실 제한

자세한 내용은 [DAY_TRADING_STRATEGY.md](DAY_TRADING_STRATEGY.md)를 참고하세요.
