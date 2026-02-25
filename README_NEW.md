# 🎯 주식 단타매매 시스템

AI 기반 진입/청산 신호, 백테스팅, 파라미터 최적화를 제공하는 종합 단타매매 시스템

---

## ✨ 주요 기능

### 📊 주식 데이터 분석
- **급등주 실시간 조회** (한국/미국)
- **페니스탁 필터링** (1달러 미만)
- **종목 점수 시스템** (펀더멘털 + 기술적 분석)
- **차트 데이터** (분봉/일봉/주봉)

### 🚦 매매 신호 시스템
- **진입 신호**: 거래량, 기술적 지표, 가격 패턴 분석
- **청산 신호**: 익절/손절/시간 기반 자동 청산
- **신호 스캔**: 급등주 전체 스캔 및 점수화
- **실시간 모니터링**: 보유 포지션 실시간 추적

### 📈 백테스팅 & 성과 분석
- **과거 데이터 검증**: 전략의 실전 수익성 확인
- **전략 비교**: 여러 전략 동시 백테스팅
- **고급 지표**: 샤프 비율, 소르티노, 칼마, MDD
- **상세 리포트**: 거래 내역, 월별 수익률, 청산 분석

### 🔧 파라미터 최적화 ⭐ NEW
- **Grid Search**: 최적의 손절/익절 비율 자동 탐색
- **빠른 최적화**: 제한된 범위에서 신속한 최적화
- **지표 기반**: ROI, 샤프 비율, 승률 등 다양한 기준
- **파라미터 분석**: 상위 결과의 파라미터 분포 분석

---

## 🏗️ 시스템 구조

```
📁 stock-analysis-system/
├── 📁 backend/
│   ├── 📁 api/                    # FastAPI 엔드포인트
│   │   ├── main.py                # 메인 앱
│   │   ├── 📁 routers/            # 카테고리별 라우터
│   │   │   ├── stocks.py          # 📊 주식 데이터
│   │   │   ├── signals.py         # 🚦 매매 신호
│   │   │   ├── backtest.py        # 📈 백테스팅
│   │   │   └── optimize.py        # 🔧 최적화
│   │   └── 📁 schemas/            # Pydantic 스키마
│   ├── 📁 core/                   # 핵심 로직
│   │   ├── indicators.py          # 기술적 지표 (MACD, BB, RSI 등)
│   │   ├── signals.py             # 진입/청산 신호 로직
│   │   └── signal_service.py      # 신호 생성 서비스
│   ├── 📁 backtest/               # 백테스팅
│   │   ├── engine.py              # 백테스팅 엔진
│   │   ├── analytics.py           # 성과 분석
│   │   └── optimizer.py           # 파라미터 최적화 ⭐
│   ├── 📁 collector/              # 데이터 수집
│   ├── 📁 kis/                    # 한국투자증권 API
│   └── 📁 us/                     # 미국 주식 (yfinance)
├── 📁 frontend/                   # React + Vite + TailwindCSS
├── 📁 docs/
│   ├── API_REFERENCE.md           # API 레퍼런스 ⭐ NEW
│   ├── TRADING_SIGNALS_GUIDE.md   # 신호 가이드
│   ├── BACKTESTING_GUIDE.md       # 백테스팅 가이드
│   └── DAY_TRADING_STRATEGY.md    # 단타 전략 가이드
└── 📁 tests/
    ├── test_trading_signals.py
    ├── test_backtest.py
    └── test_optimizer.py          # 최적화 테스트 ⭐
```

---

## 📑 API 카테고리 (한눈에 보기)

### 📊 Stocks API
**주식 데이터 및 분석**
- `GET /stocks/surge` - 급등주 조회
- `GET /stocks/penny-stocks` - 페니스탁 필터링
- `GET /stocks/{code}/score` - 종목 점수
- `GET /stocks/{code}/daily` - 일봉 데이터
- `GET /stocks/{code}/weekly` - 주봉 데이터
- `GET /stocks/{code}/minute` - 분봉 데이터

### 🚦 Signals API
**매매 신호 생성**
- `GET /signals/entry/{code}` - 진입 신호 조회
- `GET /signals/scan` - 급등주 신호 스캔
- `POST /signals/exit` - 청산 신호 조회

### 📈 Backtest API
**백테스팅 및 전략 검증**
- `POST /backtest/run` - 백테스팅 실행
- `POST /backtest/compare` - 전략 비교

### 🔧 Optimize API ⭐ NEW
**파라미터 최적화**
- `POST /optimize/grid-search` - Grid Search 실행
- `POST /optimize/quick` - 빠른 최적화
- `GET /optimize/metrics` - 사용 가능한 지표
- `GET /optimize/param-ranges` - 기본 파라미터 범위

---

## 🚀 빠른 시작

### 1. 설치

```bash
# 백엔드 설치
cd backend
pip install -r requirements.txt

# 프론트엔드 설치 (선택)
cd frontend
npm install
```

### 2. 환경 변수 설정

`.env` 파일 생성:
```env
# 한국투자증권 API (한국 주식용)
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_ACCOUNT_NO=your_account

# 데이터베이스 (선택)
DATABASE_URL=postgresql://user:pass@localhost/stock_db
```

### 3. 서버 실행

```bash
# 백엔드
python -m backend.api.main
# 또는
uvicorn backend.api.main:app --reload

# 서버 주소: http://localhost:8000
# API 문서: http://localhost:8000/docs
```

---

## 💡 사용 예시

### 예시 1: 급등주 찾고 진입 신호 확인

```bash
# 1. 미국 급등주 조회
curl "http://localhost:8000/stocks/surge?market=US"

# 2. 특정 종목 진입 신호
curl "http://localhost:8000/signals/entry/AAPL?market=US&strategy=combined"

# 3. 급등주 전체 스캔 (점수 70점 이상)
curl "http://localhost:8000/signals/scan?market=US&min_score=70"
```

### 예시 2: 백테스팅 및 파라미터 최적화

```bash
# 1. 백테스팅 실행
curl -X POST "http://localhost:8000/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "MSFT", "GOOGL"],
    "market": "US",
    "days": 90
  }'

# 2. 파라미터 최적화 (빠른 모드)
curl -X POST "http://localhost:8000/optimize/quick" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "MSFT"],
    "market": "US",
    "optimization_metric": "sharpe_ratio"
  }'
```

### 예시 3: Python으로 사용

```python
import asyncio
from backend.backtest.optimizer import quick_optimize

async def main():
    # 빠른 최적화 실행
    result = await quick_optimize(
        symbols=["AAPL", "MSFT"],
        market="US",
        days=60,
        metric="sharpe_ratio"
    )

    print(f"최적 손절 비율: {result['best_params']['stop_loss_ratio']}")
    print(f"ROI: {result['best_performance']['roi']:.2f}%")
    print(f"샤프 비율: {result['best_performance']['sharpe_ratio']:.2f}")

asyncio.run(main())
```

---

## 📊 성과 지표 해석

| 지표 | 좋은 값 | 의미 |
|------|---------|------|
| ROI | > 20% | 투자 대비 수익률 |
| 승률 | > 60% | 성공적인 거래 비율 |
| 샤프 비율 | > 1.5 | 위험 대비 수익률 |
| 소르티노 비율 | > 2.0 | 하방 위험 대비 수익률 |
| 손익비 | > 2.0 | 수익/손실 비율 |
| MDD | < 15% | 최대 낙폭 |

---

## 📚 문서

| 문서 | 설명 |
|------|------|
| [API_REFERENCE.md](API_REFERENCE.md) | 전체 API 레퍼런스 (카테고리별 정리) |
| [TRADING_SIGNALS_GUIDE.md](TRADING_SIGNALS_GUIDE.md) | 진입/청산 신호 가이드 |
| [BACKTESTING_GUIDE.md](BACKTESTING_GUIDE.md) | 백테스팅 사용법 |
| [DAY_TRADING_STRATEGY.md](DAY_TRADING_STRATEGY.md) | 단타 전략 설명 |

---

## 🧪 테스트

```bash
# 신호 시스템 테스트
python test_trading_signals.py

# 백테스팅 테스트
python test_backtest.py

# 파라미터 최적화 테스트
python test_optimizer.py
```

---

## 🎯 핵심 전략

### 거래량 돌파 전략
- 거래량 전일 대비 2배 이상 급증
- 가격 2% 이상 상승
- 거래량 MA5 대비 3배 이상

### 기술적 돌파 전략
- MA20 상향 돌파
- RSI 30~70 적정 범위
- MACD 골든크로스
- 볼린저밴드 하단 반등

### 청산 전략
- **익절**: +3% (50%), +5% (30%), +10% (20%)
- **손절**: -2% 고정 손절
- **트레일링**: 최고가 대비 -3%
- **시간**: 30분 초과 또는 장 마감 10분 전

---

## ⚙️ 주요 설정

### 백테스팅 설정
```python
BacktestConfig(
    initial_capital=10000,      # 초기 자본
    position_size_pct=0.3,      # 종목당 30%
    max_positions=3,            # 최대 3종목
    stop_loss_ratio=-0.02,      # -2% 손절
    max_holding_days=5          # 최대 5일
)
```

### 최적화 파라미터 범위
```python
OptimizationParams(
    stop_loss_ratios=[-0.01, -0.015, -0.02, -0.025, -0.03],
    take_profit_ratios=[0.03, 0.04, 0.05],
    max_holding_days_options=[3, 5, 7],
    min_entry_scores=[55, 60, 65],
    position_size_pcts=[0.2, 0.3, 0.4]
)
```

---

## 🔮 향후 계획

- [ ] **실시간 알림**: Telegram Bot 연동
- [ ] **자동 매매**: 브로커 API 연동
- [ ] **관심 종목 관리**: 워치리스트 기능
- [ ] **포트폴리오 대시보드**: 시각화 강화
- [ ] **머신러닝**: AI 기반 신호 개선

---

## ⚠️ 주의사항

1. **과거 성과 ≠ 미래 수익**: 백테스팅 결과가 미래를 보장하지 않습니다.
2. **리스크 관리 필수**: 적절한 손절과 포지션 사이징을 준수하세요.
3. **충분한 검증**: 실전 투자 전 충분한 백테스팅과 페이퍼 트레이딩을 권장합니다.
4. **개인 투자 책임**: 모든 투자 결정은 본인의 판단과 책임입니다.

---

## 📜 라이선스

개인 사용 목적 프로젝트

---

## 🙏 기여

개선 사항이나 버그 발견 시 Issue 또는 PR 환영합니다!

---

**마지막 업데이트**: 2026-02-25
