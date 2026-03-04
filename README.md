# 📊 Stock Analysis System - 단타매매 전문 시스템

A professional-grade stock analysis system for **day trading**, with automated signal generation, backtesting, and parameter optimization.

> **최신 업데이트 (2026-03-04)**: KIS REST API로 KR 급등주 연동 교체, UI 개선 (매매신호 종목명/주가 표시, 가격 조건 통화 분리) ✨

---

## 🎯 핵심 기능

### 1. 📊 주식 데이터 수집 및 분석
- **급등주 발굴**: 실시간 거래량 급증 종목 탐지
- **페니스탁 필터**: 1달러 미만 고위험/고수익 종목 선별
- **차트 데이터**: 분봉/일봉/주봉 OHLCV 데이터 제공
- **점수 시스템**: 가치/추세/안정성 종합 평가

### 2. 🚦 자동 매매 신호 생성
- **진입 신호**: 거래량/기술적지표/패턴 분석
- **청산 신호**: 분할 익절 + 손절 + 시간 기반 청산
- **신호 스캔**: 급등주에서 자동으로 진입 기회 탐색
- **신호 점수**: 0-100점 신뢰도 점수 제공

### 3. 📈 백테스팅 시스템
- **전략 검증**: 과거 데이터로 전략 성과 시뮬레이션
- **상세 분석**: Sharpe/Sortino/Calmar Ratio, MDD 계산
- **거래 내역**: 모든 진입/청산 거래 추적 및 분석
- **전략 비교**: 여러 전략을 동시에 비교 평가

### 4. 🔧 파라미터 최적화
- **Grid Search**: 최적의 매매 파라미터 자동 탐색
- **빠른 최적화**: 1-3분 내 결과 제공
- **6가지 지표**: ROI, Sharpe, Sortino, Calmar, Win Rate, Profit Factor
- **커스텀 범위**: 손절/익절/보유기간/진입점수/포지션 크기 조정 가능

### 5. 📊 섹터 모니터링 (⭐ NEW)
- **섹터 분석**: 10개 주요 섹터 실시간 강도 평가
- **섹터 비교**: 전체 섹터 성과 비교 및 순위
- **로테이션 감지**: 자금 유입/유출 섹터 자동 감지
- **섹터 신호**: 섹터 내 매매 기회 자동 스캔

---

## 🚀 빠른 시작

### 1️⃣ 서버 실행
```bash
uvicorn backend.api.main:app --reload --port 8000
```

### 2️⃣ API 문서 확인
```
http://localhost:8000/docs
```

### 3️⃣ 빠른 최적화 테스트
```bash
curl -X POST "http://localhost:8000/optimize/quick" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "TSLA"],
    "market": "US",
    "days": 60,
    "optimization_metric": "sharpe_ratio"
  }'
```

📚 **더 자세한 가이드**: [QUICK_START.md](QUICK_START.md)

---

## 📁 프로젝트 구조

```
stock-analysis-system/
│
├── backend/
│   ├── api/
│   │   ├── main.py              # 🏠 메인 FastAPI 앱
│   │   ├── routers/             # 📦 카테고리별 API 라우터
│   │   │   ├── stocks.py        # 📊 주식 데이터
│   │   │   ├── signals.py       # 🚦 매매 신호
│   │   │   ├── backtest.py      # 📈 백테스팅
│   │   │   ├── optimize.py      # 🔧 최적화
│   │   │   └── sectors.py       # 📊 섹터 분석 (NEW)
│   │   └── schemas/             # 📄 Pydantic 스키마
│   │
│   ├── backtest/
│   │   ├── engine.py            # 백테스팅 엔진
│   │   ├── analytics.py         # 성과 분석
│   │   └── optimizer.py         # Grid Search (NEW)
│   │
│   ├── core/
│   │   ├── indicators.py        # 기술적 지표
│   │   ├── signals.py           # 신호 로직
│   │   ├── signal_service.py    # 신호 서비스
│   │   └── score_service.py     # 점수 서비스
│   │
│   ├── sectors/
│   │   ├── sector_config.py     # 섹터 정의 및 종목 매핑
│   │   └── sector_analyzer.py   # 섹터 분석 엔진
│   │
│   ├── kis/                     # 한국투자증권 API
│   ├── us/                      # 미국 주식 (yfinance)
│   └── collector/               # 실시간 데이터 수집
│
├── test_*.py                    # 테스트 스크립트
│
└── 📚 문서/
    ├── QUICK_START.md           # 빠른 시작 가이드
    ├── API_REFERENCE.md         # API 레퍼런스
    ├── API_STRUCTURE.md         # 구조 다이어그램
    ├── FINAL_SUMMARY.md         # 최종 요약
    └── *.md                     # 기타 가이드 문서
```

---

## 🎯 API 엔드포인트

### 📊 Stocks (주식 데이터)
```
GET  /stocks/surge              - 급등주 목록
GET  /stocks/penny-stocks       - 페니스탁 필터
GET  /stocks/{code}/score       - 종목 점수
GET  /stocks/{code}/daily       - 일봉 차트
GET  /stocks/{code}/weekly      - 주봉 차트
GET  /stocks/{code}/minute      - 분봉 차트
```

### 🚦 Signals (매매 신호)
```
GET  /signals/entry/{code}      - 진입 신호
GET  /signals/scan              - 신호 스캔
POST /signals/exit              - 청산 신호
```

### 📈 Backtest (백테스팅)
```
POST /backtest/run              - 백테스팅 실행
POST /backtest/compare          - 전략 비교
```

### 🔧 Optimize (최적화)
```
POST /optimize/grid-search      - 전체 Grid Search
POST /optimize/quick            - 빠른 최적화
GET  /optimize/metrics          - 지표 목록
GET  /optimize/param-ranges     - 파라미터 범위
```

### 📊 Sectors (섹터 분석) ⭐ NEW
```
GET  /sectors/list              - 섹터 목록
GET  /sectors/{sector}/analyze  - 섹터 분석
GET  /sectors/compare           - 섹터 비교
GET  /sectors/{sector}/signals  - 섹터 신호
```

📚 **전체 API 문서**: [API_REFERENCE.md](API_REFERENCE.md)

---

## 🧪 테스트 스크립트

### 최적화 테스트
```bash
python test_optimizer.py
```

### 백테스팅 테스트
```bash
python test_backtest.py
```

### 매매 신호 테스트
```bash
python test_trading_signals.py
```

### 페니스탁 테스트
```bash
python test_penny_stocks.py
```

---

## 💡 실전 활용 예시

### Step 1: 급등주 발굴
```bash
curl "http://localhost:8000/stocks/surge?market=US"
```

### Step 2: 매매 신호 확인
```bash
curl "http://localhost:8000/signals/scan?market=US&min_score=70"
```

### Step 3: 파라미터 최적화
```bash
curl -X POST "http://localhost:8000/optimize/quick" \
  -d '{"symbols": ["AAPL"], "market": "US", "days": 60}'
```

### Step 4: 최적 파라미터로 백테스팅
```bash
curl -X POST "http://localhost:8000/backtest/run" \
  -d '{"symbols": ["AAPL"], "stop_loss_ratio": -0.02, ...}'
```

---

## 🎓 기술 스택

### Backend
- **FastAPI** - 고성능 웹 프레임워크
- **Pydantic** - 데이터 검증 및 스키마
- **pandas** - 데이터 분석
- **yfinance** - 미국 주식 데이터
- **KIS REST API** - 한국투자증권 Open API (KR 급등주 거래량 순위)
- **pykrx** - 한국 주식 보조 데이터

### Analysis
- **Technical Indicators**: RSI, MACD, Bollinger Bands, Stochastic
- **Performance Metrics**: Sharpe, Sortino, Calmar Ratio, MDD
- **Optimization**: Grid Search with multiple objectives

### Frontend (기존)
- **React** + **Vite** + **TailwindCSS**
- **Lightweight-Charts** - 실시간 차트

---

## ⚙️ 설치 및 설정

### 1. 백엔드 설정
```bash
cd backend
pip install -r requirements.txt
```

### 2. 환경 변수 설정
```bash
# .env 파일 생성
cp .env.example .env

# KIS API 키 입력
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
```

### 3. 서버 실행
```bash
uvicorn backend.api.main:app --reload --port 8000
```

### 4. 프론트엔드 설정 (선택)
```bash
cd frontend
npm install
npm run dev
```

---

## 📈 성과 지표

### 백테스팅 제공 지표
- **ROI**: 총 수익률
- **Sharpe Ratio**: 위험 대비 수익률
- **Sortino Ratio**: 하방 위험 대비 수익률
- **Calmar Ratio**: MDD 대비 수익률
- **Win Rate**: 승률
- **Profit Factor**: 손익비
- **MDD**: 최대 낙폭
- **Total Trades**: 총 거래 횟수

### 최적화 가능 파라미터
- **Stop Loss**: -1% ~ -3% (손절 비율)
- **Take Profit**: +3% ~ +5% (익절 비율)
- **Max Holding Days**: 3-7일 (최대 보유 기간)
- **Min Entry Score**: 55-65점 (최소 진입 점수)
- **Position Size**: 20-40% (포지션 크기)

---

## 📚 문서

- 📖 [빠른 시작 가이드](QUICK_START.md)
- 📖 [API 레퍼런스](API_REFERENCE.md)
- 📖 [API 구조 다이어그램](API_STRUCTURE.md)
- 📖 [구현 요약](IMPLEMENTATION_SUMMARY.md)
- 📖 [최종 요약](FINAL_SUMMARY.md)
- 📖 [단타매매 전략 가이드](DAY_TRADING_STRATEGY.md)
- 📖 [매매 신호 가이드](TRADING_SIGNALS_GUIDE.md)
- 📖 [백테스팅 가이드](BACKTESTING_GUIDE.md)
- 📖 [페니스탁 API 가이드](PENNY_STOCKS_API.md)

---

## 🎯 로드맵

### ✅ 완료된 기능
- [x] 급등주 발굴 시스템
- [x] 페니스탁 필터링
- [x] 자동 매매 신호 생성
- [x] 백테스팅 엔진
- [x] Grid Search 최적화
- [x] API 재구조화
- [x] 섹터 모니터링 시스템 (2026-03-02)
- [x] KIS REST API KR 급등주 연동 (2026-03-04)
- [x] 프론트엔드 UI 개선 (2026-03-04)

### 🔍 조사 완료 (2026-03-02)
- [x] **QNCX 누락 원인 분석**: Yahoo Finance 스크리너 API 한계
  - QNCX: 당일 -0.09% 하락으로 급등주 목록 제외
  - BNAI, BATL: 급등했으나 API 제한으로 누락
  - **Yahoo Finance API 한계**: day_gainers (25개) + most_actives (25개) = 최대 ~47개
  - **해결**: 두 스크리너 합쳐서 최대한 확보 (20개 → 47개)

### 🚧 향후 계획
- [ ] 추가 데이터 소스 검토 (Alpha Vantage, Polygon.io 등)
- [ ] 실시간 알림 (Telegram Bot)
- [ ] 관심 종목 관리 API
- [ ] 포트폴리오 추적
- [ ] 자동 주문 실행 (브로커 API 연동)
- [ ] ML 기반 신호 개선
- [ ] 프론트엔드 대시보드 업데이트

---

## ⚠️ 주의사항

1. **투자 리스크**: 이 시스템은 교육 목적이며, 실제 투자는 본인 책임입니다.
2. **백테스팅 한계**: 과거 성과가 미래를 보장하지 않습니다.
3. **실전 적용**: 충분한 테스트 후 소액으로 시작하세요.
4. **시장 변동성**: 급변하는 시장 상황에 유의하세요.

---

## 📞 지원 및 기여

- **Issues**: GitHub Issues에 버그 리포트 및 기능 제안
- **Documentation**: 문서 개선 기여 환영
- **Code**: Pull Request 환영

---

## 📄 라이센스

MIT License

---

## 🎉 시작하기

```bash
# 서버 실행
uvicorn backend.api.main:app --reload --port 8000

# 브라우저에서 API 문서 확인
# → http://localhost:8000/docs

# 테스트 실행
python test_optimizer.py
```

**Happy Trading! 📈🚀**

---

**버전**: 2.2.0
**최종 업데이트**: 2026-03-04
**개발자**: Personal Stock Analysis System Team

---

## 📝 변경 이력

### v2.2.0 (2026-03-04)
- 🔄 **KIS REST API KR 급등주 연동 교체**
  - pykrx/KRX 스크래핑 → KIS REST API (`FHPST01720000`) 교체
  - KOSPI(`J`) + KOSDAQ(`Q`) 거래량 상위 종목 조회
  - `change_rate` 기준 내림차순 정렬, 상승 종목만 반환
  - `max_price` 필터 지원 (기본 20,000원 이하)
  - KIS 토큰 23시간 캐싱으로 Rate Limit 방지
- 🐛 **StocksDashboard 런타임 오류 수정**
  - `Cannot read properties of undefined (reading 'toFixed')` 오류 해결
  - 펀더멘털/기술적 지표 필드 전체 null 체크 추가
    - 펀더멘털: `per`, `pbr`, `roe`, `eps`, `bps`
    - 기술적: `rsi`, `volatility`, `return_60d`
- ✨ **매매신호 탭 UI 개선**
  - 신호 카드 헤더: `종목명(종목코드)` 형식으로 표시
  - 주가 표시: `[주가 : ###원]` 형식, 볼드(bold) + 폰트 크기 2xl
  - `EntrySignal` 인터페이스에 `stock_info` 필드 추가
- ✨ **가격 조건 통화 분리 (UI)**
  - 한국장: `1,000원 미만` 표시, 입력란에 `원` 단위 표시
  - 미국장: `$1 미만` 표시, 입력란에 `$` 단위 표시
  - 시장 전환 시 가격 필터 자동 초기화 (원/달러 혼용 방지)

### v2.1.0 (2026-03-02)
- ✨ **섹터 모니터링 시스템 추가**
  - 10개 주요 섹터 실시간 분석 (기술, 에너지, 헬스케어, 금융 등)
  - 섹터 강도 평가 (strong/moderate/weak)
  - 섹터 로테이션 자동 감지 (rotating_in/rotating_out)
  - 섹터별 매매 신호 생성
  - 병렬 데이터 수집 및 5분 캐싱
- 🔍 **QNCX, BNAI, BATL 분석 완료**
  - 현재 시스템의 예측 능력 검증
  - 급등주 스크리너 한계 파악
- ⚡ **급등주 스크리너 개선**
  - US surge stocks: day_gainers + most_actives 통합 (20개 → 47개)
  - limit 파라미터 추가 (10~200, 기본값 100)
  - Yahoo Finance API 한계 분석: 각 스크리너당 최대 25개
- 🐛 **버그 수정**
  - VSCode Diagnostics 경고 해결
  - main.py 미사용 변수/파라미터 정리

### v2.0.0 (2026-02-25)
- Grid Search 파라미터 최적화
- API 재구조화
