# 🏗️ API 구조 다이어그램

## 📁 파일 구조

```
stock-analysis-system/
│
├── backend/
│   ├── api/
│   │   ├── main.py                    # 🏠 메인 앱 (라우터 등록)
│   │   ├── routers/                   # 📦 카테고리별 라우터
│   │   │   ├── __init__.py
│   │   │   ├── stocks.py              # 📊 주식 데이터
│   │   │   ├── signals.py             # 🚦 매매 신호
│   │   │   ├── backtest.py            # 📈 백테스팅
│   │   │   └── optimize.py            # 🔧 최적화
│   │   └── schemas/                   # 📄 Pydantic 스키마
│   │       ├── __init__.py
│   │       ├── stock.py
│   │       ├── signal.py
│   │       ├── backtest.py
│   │       └── optimize.py
│   │
│   ├── backtest/
│   │   ├── engine.py                  # 백테스팅 엔진
│   │   ├── analytics.py               # 성과 분석
│   │   └── optimizer.py               # 🔧 Grid Search 엔진
│   │
│   ├── core/
│   │   ├── indicators.py              # 기술적 지표
│   │   ├── scorer.py                  # 점수 계산
│   │   ├── score_service.py           # 점수 서비스
│   │   ├── signals.py                 # 신호 로직
│   │   └── signal_service.py          # 신호 서비스
│   │
│   ├── kis/                           # 한국투자증권 API
│   ├── us/                            # 미국 주식 API
│   └── collector/                     # 데이터 수집
│
├── test_optimizer.py                  # 최적화 테스트
├── test_trading_signals.py            # 신호 테스트
├── test_backtest.py                   # 백테스팅 테스트
├── test_penny_stocks.py               # 페니스탁 테스트
│
└── 📚 문서/
    ├── API_REFERENCE.md               # API 레퍼런스
    ├── IMPLEMENTATION_SUMMARY.md      # 구현 요약
    ├── FINAL_SUMMARY.md               # 최종 요약
    ├── API_STRUCTURE.md               # 이 문서
    ├── README_NEW.md                  # 업데이트된 README
    ├── DAY_TRADING_STRATEGY.md        # 전략 가이드
    ├── TRADING_SIGNALS_GUIDE.md       # 신호 가이드
    ├── BACKTESTING_GUIDE.md           # 백테스팅 가이드
    └── PENNY_STOCKS_API.md            # 페니스탁 가이드
```

---

## 🔄 요청 흐름

### 예시: 최적화 요청 흐름

```
Client
  │
  │ POST /optimize/quick
  │ {
  │   "symbols": ["AAPL"],
  │   "market": "US",
  │   "days": 60,
  │   "optimization_metric": "sharpe_ratio"
  │ }
  ▼
main.py
  │
  │ app.include_router(optimize_router)
  ▼
routers/optimize.py
  │
  │ @router.post("/quick")
  │ async def run_quick_optimization(request: QuickOptimizeRequest)
  ▼
backend/backtest/optimizer.py
  │
  │ async def quick_optimize(...)
  │   ├─ GridSearchOptimizer 생성
  │   ├─ 제한된 파라미터 범위 설정
  │   └─ 최적화 실행
  ▼
backend/backtest/engine.py
  │
  │ async def run_simple_backtest(...)
  │   ├─ 종목 데이터 수집
  │   ├─ 진입/청산 신호 생성
  │   └─ 시뮬레이션 실행
  ▼
backend/backtest/analytics.py
  │
  │ PerformanceAnalytics.generate_enhanced_report(...)
  │   ├─ Sharpe Ratio 계산
  │   ├─ Sortino Ratio 계산
  │   ├─ Calmar Ratio 계산
  │   └─ 상세 리포트 생성
  ▼
Client
  │
  │ {
  │   "status": "success",
  │   "best_params": {...},
  │   "best_performance": {...},
  │   "execution_time_seconds": 125.3
  │ }
```

---

## 🎯 API 엔드포인트 맵

```
http://localhost:8000/
│
├── 📊 /stocks/
│   ├── GET  /surge                    # 급등주 목록
│   ├── GET  /penny-stocks             # 페니스탁 필터
│   ├── GET  /{code}/score             # 종목 점수
│   ├── GET  /{code}/daily             # 일봉 차트
│   ├── GET  /{code}/weekly            # 주봉 차트
│   └── GET  /{code}/minute            # 분봉 차트
│
├── 🚦 /signals/
│   ├── GET  /entry/{code}             # 진입 신호
│   ├── GET  /scan                     # 신호 스캔
│   └── POST /exit                     # 청산 신호
│
├── 📈 /backtest/
│   ├── POST /run                      # 백테스팅 실행
│   └── POST /compare                  # 전략 비교
│
├── 🔧 /optimize/
│   ├── POST /grid-search              # 전체 Grid Search
│   ├── POST /quick                    # 빠른 최적화
│   ├── GET  /metrics                  # 지표 목록
│   └── GET  /param-ranges             # 파라미터 범위
│
├── GET  /                             # API 정보
├── GET  /docs                         # Swagger UI
└── WS   /ws/{code}                    # 실시간 WebSocket
```

---

## 🔗 데이터 흐름

### 1. 주식 데이터 수집
```
yfinance / pykrx
        ↓
  데이터 수집
        ↓
  캐싱 (5분)
        ↓
   API 응답
```

### 2. 매매 신호 생성
```
주식 데이터
        ↓
기술적 지표 계산
 (RSI, MACD, 등)
        ↓
   신호 점수 계산
 (거래량 + 기술 + 패턴)
        ↓
  BUY / HOLD 신호
```

### 3. 백테스팅
```
    종목 리스트
        ↓
  과거 데이터 수집
        ↓
날짜별 시뮬레이션
 (진입/청산 신호)
        ↓
   성과 분석
 (ROI, Sharpe, MDD)
```

### 4. 최적화
```
  파라미터 범위
        ↓
모든 조합 생성
 (Grid Search)
        ↓
각 조합 백테스팅
        ↓
 최적 파라미터 선정
 (지표 기준 정렬)
```

---

## 📦 컴포넌트 의존성

```
main.py
  │
  ├─→ routers/stocks.py
  │     └─→ core/score_service.py
  │           └─→ core/scorer.py
  │                 └─→ core/indicators.py
  │
  ├─→ routers/signals.py
  │     └─→ core/signal_service.py
  │           └─→ core/signals.py
  │                 └─→ core/indicators.py
  │
  ├─→ routers/backtest.py
  │     └─→ backtest/engine.py
  │           ├─→ core/signal_service.py
  │           └─→ backtest/analytics.py
  │
  └─→ routers/optimize.py
        └─→ backtest/optimizer.py
              └─→ backtest/engine.py
```

---

## 🎨 카테고리별 색상 코드

API 문서와 로그에서 일관된 색상 사용:

- 📊 **Stocks** (주식 데이터) - 파란색
- 🚦 **Signals** (매매 신호) - 노란색/빨간색
- 📈 **Backtest** (백테스팅) - 녹색
- 🔧 **Optimize** (최적화) - 주황색

---

## 🚀 확장 가능성

### 추가 가능한 카테고리

```
backend/api/routers/
├── stocks.py       # ✅ 구현됨
├── signals.py      # ✅ 구현됨
├── backtest.py     # ✅ 구현됨
├── optimize.py     # ✅ 구현됨
├── watchlist.py    # 💡 추가 가능: 관심 종목 관리
├── alerts.py       # 💡 추가 가능: 알림 설정
├── portfolio.py    # 💡 추가 가능: 포트폴리오 관리
└── orders.py       # 💡 추가 가능: 자동 주문 실행
```

각 새로운 카테고리는 독립적인 라우터 파일로 추가 가능!

---

## 📝 네이밍 컨벤션

### Router 파일
- 파일명: `{category}.py` (복수형)
- 예: `stocks.py`, `signals.py`

### Prefix
- URL prefix: `/{category}`
- 예: `/stocks`, `/signals`

### Tags
- OpenAPI tag: `{icon} {Category}`
- 예: `📊 Stocks`, `🚦 Signals`

### 함수명
- 동사 + 명사 + 카테고리
- 예: `get_stock_score()`, `run_backtest()`

---

## 🔧 설정 및 관리

### 환경 변수
```bash
# .env
KIS_APP_KEY=your_key
KIS_APP_SECRET=your_secret
```

### 로깅
```python
import logging
logger = logging.getLogger(__name__)
logger.info(f"Optimizer: Running Grid Search...")
```

### 캐싱
```python
# 각 라우터에서 독립적으로 관리
_surge_cache: dict = {"data": [], "ts": 0}
```

---

이 구조는 **확장 가능하고**, **유지보수가 쉬우며**, **직관적**입니다! 🎉
