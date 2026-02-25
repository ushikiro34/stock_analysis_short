# 🚀 빠른 시작 가이드

## ⚡ 5분 안에 시작하기

### 1️⃣ 서버 실행
```bash
# 프로젝트 루트에서
uvicorn backend.api.main:app --reload --port 8000
```

**실행 결과:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### 2️⃣ API 문서 확인
브라우저에서 접속:
```
http://localhost:8000/docs
```

**Swagger UI**에서 모든 API를 테스트할 수 있습니다!

---

## 📊 주요 기능 테스트

### 1. 급등주 조회
```bash
# 한국 시장
curl "http://localhost:8000/stocks/surge?market=KR"

# 미국 시장
curl "http://localhost:8000/stocks/surge?market=US"
```

### 2. 페니스탁 필터링
```bash
curl "http://localhost:8000/stocks/penny-stocks"
```

**조건:**
- 주가 < $1
- 당일 거래량 급증 (2배 이상)
- D-1, D-2 거래량 < D-3 거래량

### 3. 매매 신호 스캔
```bash
curl "http://localhost:8000/signals/scan?market=US&strategy=combined&min_score=70"
```

**파라미터:**
- `market`: KR | US
- `strategy`: volume | technical | pattern | combined
- `min_score`: 최소 점수 (0-100)

### 4. 빠른 최적화 (⭐ 추천)
```bash
curl -X POST "http://localhost:8000/optimize/quick" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "TSLA", "NVDA"],
    "market": "US",
    "days": 60,
    "optimization_metric": "sharpe_ratio"
  }'
```

**실행 시간:** 약 1-3분

**결과 예시:**
```json
{
  "status": "success",
  "execution_time_seconds": 125.3,
  "total_combinations_tested": 24,
  "best_params": {
    "stop_loss_ratio": -0.02,
    "take_profit_ratio": 0.04,
    "max_holding_days": 5,
    "min_entry_score": 60,
    "position_size_pct": 0.3
  },
  "best_performance": {
    "roi": 15.7,
    "sharpe_ratio": 1.82,
    "win_rate": 62.5,
    "total_trades": 48
  }
}
```

---

## 🧪 테스트 스크립트 실행

### 1. 최적화 테스트
```bash
python test_optimizer.py
```

### 2. 백테스팅 테스트
```bash
python test_backtest.py
```

### 3. 매매 신호 테스트
```bash
python test_trading_signals.py
```

### 4. 페니스탁 테스트
```bash
python test_penny_stocks.py
```

---

## 📈 실전 워크플로우

### Step 1: 급등주 발굴
```bash
# 미국 시장 급등주 조회
curl "http://localhost:8000/stocks/surge?market=US"
```

### Step 2: 매매 신호 확인
```bash
# 급등주에서 진입 신호 스캔 (점수 70점 이상)
curl "http://localhost:8000/signals/scan?market=US&min_score=70"
```

**응답 예시:**
```json
[
  {
    "code": "AAPL",
    "signal": "BUY",
    "strength": "high",
    "score": 82.5,
    "reasons": [
      "거래량 급증 (전일 대비 2.3배)",
      "RSI 상승 전환 (45.2 → 58.7)",
      "MACD 골든크로스"
    ],
    "current_price": 178.45
  }
]
```

### Step 3: 백테스팅으로 검증
```bash
curl -X POST "http://localhost:8000/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL"],
    "market": "US",
    "days": 90,
    "initial_capital": 10000,
    "entry_strategy": "combined",
    "min_entry_score": 70,
    "stop_loss_ratio": -0.02,
    "max_holding_days": 5
  }'
```

### Step 4: 파라미터 최적화
```bash
curl -X POST "http://localhost:8000/optimize/quick" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL"],
    "market": "US",
    "days": 60,
    "optimization_metric": "sharpe_ratio"
  }'
```

### Step 5: 최적 파라미터로 재검증
```bash
# Step 4에서 얻은 best_params 사용
curl -X POST "http://localhost:8000/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL"],
    "market": "US",
    "days": 90,
    "stop_loss_ratio": -0.02,
    "take_profit_ratio": 0.04,
    "max_holding_days": 5,
    "min_entry_score": 60
  }'
```

---

## 🎯 최적화 지표 선택 가이드

### 공격적 전략
```json
{
  "optimization_metric": "roi"
}
```
→ **총 수익률** 극대화

### 균형잡힌 전략 (⭐ 추천)
```json
{
  "optimization_metric": "sharpe_ratio"
}
```
→ **위험 대비 수익률** 최적화

### 방어적 전략
```json
{
  "optimization_metric": "sortino_ratio"
}
```
→ **하방 위험** 최소화

### 낙폭 최소화
```json
{
  "optimization_metric": "calmar_ratio"
}
```
→ **MDD 대비 수익률** 최적화

### 안정적 수익
```json
{
  "optimization_metric": "win_rate"
}
```
→ **승률** 극대화

### 수익 극대화
```json
{
  "optimization_metric": "profit_factor"
}
```
→ **손익비** 최적화

---

## 📊 사용 가능한 지표 조회

### 최적화 지표 목록
```bash
curl "http://localhost:8000/optimize/metrics"
```

### 기본 파라미터 범위
```bash
curl "http://localhost:8000/optimize/param-ranges"
```

**응답:**
```json
{
  "stop_loss_ratios": [-0.01, -0.015, -0.02, -0.025, -0.03],
  "take_profit_ratios": [0.03, 0.04, 0.05],
  "max_holding_days_options": [3, 5, 7],
  "min_entry_scores": [55, 60, 65],
  "position_size_pcts": [0.2, 0.3, 0.4],
  "total_combinations": 405
}
```

---

## 🔧 커스텀 최적화

### 전체 Grid Search (고급)
```bash
curl -X POST "http://localhost:8000/optimize/grid-search" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "TSLA"],
    "market": "US",
    "days": 60,
    "optimization_metric": "sharpe_ratio",
    "stop_loss_ratios": [-0.01, -0.02, -0.03],
    "take_profit_ratios": [0.03, 0.05, 0.07],
    "max_holding_days_options": [3, 5],
    "min_entry_scores": [60, 70],
    "position_size_pcts": [0.25, 0.5]
  }'
```

**조합 수:** 3 × 3 × 2 × 2 × 2 = **72개**
**예상 시간:** 약 5-10분

---

## 💡 팁과 요령

### ✅ 빠른 시작
1. `/optimize/quick`로 먼저 테스트 (1-3분)
2. 결과가 좋으면 `/backtest/run`으로 검증
3. 실전 투자 전 충분한 기간 백테스팅 필요

### ✅ 파라미터 조정
- **stop_loss_ratio**: -0.02 (2% 손절) 권장
- **take_profit_ratio**: 0.03~0.05 (3-5% 익절)
- **max_holding_days**: 3-5일 (단타)
- **min_entry_score**: 60-70점

### ✅ 성과 평가
- **Sharpe Ratio > 1.0**: 양호
- **Sharpe Ratio > 2.0**: 우수
- **Win Rate > 50%**: 양호
- **MDD < 15%**: 양호

### ⚠️ 주의사항
- 백테스팅 결과 ≠ 실전 수익률
- 과거 데이터는 미래를 보장하지 않음
- 충분한 거래 횟수 필요 (최소 30회 이상)
- 다양한 시장 상황에서 테스트 권장

---

## 🆘 문제 해결

### 서버가 시작되지 않음
```bash
# 포트가 이미 사용 중인 경우
uvicorn backend.api.main:app --reload --port 8001
```

### 한글 깨짐 (Windows)
```python
# 테스트 스크립트 상단에 추가
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```

### 데이터 수집 오류
```bash
# yfinance 업데이트
pip install --upgrade yfinance

# pykrx 업데이트
pip install --upgrade pykrx
```

---

## 📚 더 알아보기

- **API 레퍼런스**: [API_REFERENCE.md](API_REFERENCE.md)
- **구조 다이어그램**: [API_STRUCTURE.md](API_STRUCTURE.md)
- **구현 요약**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **최종 요약**: [FINAL_SUMMARY.md](FINAL_SUMMARY.md)

---

## 🎉 시작 준비 완료!

```bash
# 서버 시작
uvicorn backend.api.main:app --reload --port 8000

# 브라우저 열기
# → http://localhost:8000/docs
```

Happy Trading! 📈🚀
