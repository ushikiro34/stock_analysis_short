# 📊 Stock Analysis System - 단타매매 전문 시스템

A professional-grade stock analysis system for **day trading**, with automated signal generation, backtesting, parameter optimization, and paper trading simulation.

> **최신 업데이트 (2026-03-12)**: 투자일지 AI 분석 모달 추가 (Groq · Llama-3.3-70b), 뉴스 크롤링 연동, 다국어 혼용 필터 ✨

---

## 🎯 핵심 기능

### 1. 📊 주식 데이터 수집 및 분석
- **급등주 발굴**: KIS REST API 기반 실시간 거래량 급증 종목 탐지 (KR)
- **종목 상세 분석**: MA5/20/60/120, 거래량비율, 52주/20일 신고가, 신호 점수
- **차트 데이터**: 분봉/일봉/주봉 OHLCV 데이터
- **점수 시스템**: 가치/추세/안정성 종합 평가

### 2. 🚦 자동 매매 신호 생성
- **진입 신호**: 거래량/기술적지표/패턴 분석 (combined / volume / technical 등)
- **신호 스캔**: 급등주에서 자동으로 진입 기회 탐색
- **신호 점수**: 0-100점 신뢰도 점수 + 추격 차단 필터

### 3. 📈 백테스팅 시스템
- **전략 검증**: 과거 데이터로 전략 성과 시뮬레이션
- **상세 분석**: Sharpe/Sortino/Calmar Ratio, MDD 계산
- **거래 내역**: 모든 진입/청산 거래 추적 및 분석

### 4. 🔧 파라미터 최적화
- **Grid Search**: 최적의 매매 파라미터 자동 탐색
- **6가지 지표**: ROI, Sharpe, Sortino, Calmar, Win Rate, Profit Factor
- **커스텀 범위**: 손절/익절/보유기간/진입점수/포지션 크기 조정

### 5. 📄 모의투자 시뮬레이션 ⭐ NEW
- **자동매매**: 5분 주기로 신호 스캔 → 자동 진입/청산
- **분할 익절/손절**: +2%/+5%/+10% 분할 익절, -1%/-2% 분할 손절, 트레일링 스톱
- **수동 포지션 추가**: 종목코드 입력 시 현재가 자동 조회 후 즉시 매수
- **DB 영속화**: SQLite/PostgreSQL 기반 상태·거래내역 저장 (서버 재시작 후 복원)
- **포트폴리오 차트**: 5분 단위 자산 가치 변화 추적

### 6. ⭐ 관심종목 탭 NEW
- **분석 그리드**: MA, 거래량비율, 52주 신고가, 신호, 점수 한 화면에 표시
- **즉시 매수**: 현재가로 바로 모의투자 포지션 추가
- **localStorage 저장**: 서버 재시작 후에도 목록 유지

### 7. 📓 투자일지 탭 NEW
- **체결 내역 조회**: 날짜/종목/수익여부 필터, 페이지네이션
- **수익 요약**: 총 손익, 승률, 익절/손절 금액 집계
- **컬럼 구분**: 종목별 상세 정보 그리드 표시
- **🤖 AI 분석 모달**: 종목명 클릭 → Groq AI 기반 7개 섹션 상세 분석 (SSE 스트리밍)
  - 종목·섹터 정보 / 관련 뉴스(Naver Finance 크롤링) / 차트패턴 / 종가 분석 / 종합 분석 / 익일 예상 / 거래 교훈

### 8. 📡 시스템 모니터링
- **실시간 로그**: 인메모리 로그 버퍼 (DEBUG/INFO/WARNING/ERROR 필터)
- **태스크 상태**: collector / scorer / paper_trading 백그라운드 태스크 상태 조회

---

## 🚀 빠른 시작

### 1️⃣ 백엔드 실행
```bash
pip install -r requirements.txt
uvicorn backend.api.main:app --reload --port 8000
```

### 2️⃣ 프론트엔드 실행
```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 3️⃣ API 문서 확인
```
http://localhost:8000/docs
```

---

## 📁 프로젝트 구조

```
stock_analysis_short/
│
├── backend/
│   ├── api/
│   │   ├── main.py              # 🏠 메인 FastAPI 앱 (startup, 백그라운드 태스크)
│   │   └── routers/
│   │       ├── stocks.py        # 📊 주식 데이터 + /analyze 엔드포인트
│   │       ├── signals.py       # 🚦 매매 신호 스캔
│   │       ├── backtest.py      # 📈 백테스팅
│   │       ├── optimize.py      # 🔧 파라미터 최적화
│   │       ├── sectors.py       # 📊 섹터 분석
│   │       ├── paper_trading.py # 📄 모의투자 API
│   │       └── monitor.py       # 📡 모니터링/로그
│   │
│   ├── core/
│   │   ├── paper_engine.py      # 📄 페이퍼 트레이딩 엔진 (싱글턴)
│   │   ├── indicators.py        # 기술적 지표
│   │   ├── signals.py           # 신호 로직 (VolumeBreakout, TechnicalBreakout 등)
│   │   ├── signal_service.py    # 신호 서비스
│   │   ├── score_service.py     # 점수 서비스
│   │   ├── scorer.py            # 가치/추세/안정성 스코어러
│   │   └── log_buffer.py        # 인메모리 로그 버퍼
│   │
│   ├── db/
│   │   ├── models.py            # 🗄️ SQLAlchemy ORM (PaperAccount, PaperTrade, PortfolioHistory)
│   │   └── session.py           # DB 세션 (async SQLAlchemy)
│   │
│   ├── backtest/
│   │   ├── engine.py            # 백테스팅 엔진
│   │   ├── analytics.py         # 성과 분석
│   │   └── optimizer.py         # Grid Search
│   │
│   ├── kis/
│   │   └── rest_client.py       # 한국투자증권 REST API (거래량순위, 분봉 등)
│   │
│   ├── sectors/
│   │   ├── sector_config.py     # 섹터 정의 및 종목 매핑
│   │   └── sector_analyzer.py   # 섹터 분석 엔진
│   │
│   └── collector/               # KIS WebSocket 실시간 수집
│
├── frontend/src/
│   ├── App.tsx                  # 탭 라우팅 (7개 탭)
│   ├── lib/api.ts               # API 클라이언트 (타입 + fetch 함수)
│   ├── pages/
│   │   ├── StocksDashboard.tsx        # 주식 분석
│   │   ├── SignalsDashboard.tsx       # 매매 신호
│   │   ├── WatchlistDashboard.tsx     # ⭐ 관심종목
│   │   ├── BacktestDashboard.tsx      # 백테스팅
│   │   ├── OptimizeDashboard.tsx      # 최적화
│   │   ├── PaperTradingDashboard.tsx  # ⭐ 모의투자
│   │   └── InvestmentJournalDashboard.tsx  # ⭐ 투자일지
│   └── components/
│       ├── CandleChart.tsx      # 캔들스틱 차트
│       ├── ScoreCard.tsx        # 점수 카드
│       ├── RiskCard.tsx         # 리스크 카드
│       └── SurgeList.tsx        # 급등주 목록
│
├── .env                         # KIS API 키, DATABASE_URL
└── requirements.txt
```

---

## 🎯 API 엔드포인트

### 📊 Stocks (주식 데이터)
```
GET  /stocks/surge              - 급등주 목록 (KIS REST API)
GET  /stocks/{code}/analyze     - 종목 상세 분석 (MA, 신고가, 신호, 5분 캐시)
GET  /stocks/{code}/score       - 종합 점수 (가치/추세/안정성)
GET  /stocks/{code}/daily       - 일봉 차트
GET  /stocks/{code}/weekly      - 주봉 차트
GET  /stocks/{code}/minute      - 분봉 차트
```

### 🚦 Signals (매매 신호)
```
GET  /signals/entry/{code}      - 단일 종목 진입 신호
GET  /signals/scan              - 급등주 전체 신호 스캔
POST /signals/exit              - 청산 신호
```

### 📈 Backtest (백테스팅)
```
POST /backtest/run              - 백테스팅 실행
POST /backtest/compare          - 전략 비교
```

### 🔧 Optimize (최적화)
```
POST /optimize/quick            - 빠른 최적화
POST /optimize/grid-search      - 전체 Grid Search
GET  /optimize/metrics          - 지표 목록
GET  /optimize/param-ranges     - 파라미터 범위
```

### 📄 Paper Trading (모의투자)
```
POST /paper/start               - 시뮬레이션 시작 (초기 자본, 전략 등 설정)
POST /paper/stop                - 시뮬레이션 중지
POST /paper/reset               - 전체 초기화 (거래내역·이력 삭제)
GET  /paper/status              - 계좌 현황 (총 자산, 현금, ROI 등)
GET  /paper/positions           - 보유 포지션 조회
POST /paper/positions           - 수동 포지션 추가
POST /paper/positions/{code}/close  - 특정 포지션 수동 청산
POST /paper/positions/close-all - 전체 일괄 청산
GET  /paper/trades              - 체결 거래 내역
GET  /paper/history             - 포트폴리오 가치 변화 이력
GET  /paper/journal             - 투자일지 (날짜/종목/수익 필터)
GET  /paper/journal/{id}/analyze - AI 거래 분석 (SSE 스트리밍, Groq Llama-3.3-70b)
```

### 📡 Monitor (모니터링)
```
GET    /monitor/status          - 서버 업타임, 태스크 상태
GET    /monitor/logs            - 실시간 로그 조회 (level, limit 파라미터)
DELETE /monitor/logs            - 로그 버퍼 초기화
```

---

## 🗄️ 데이터베이스

SQLAlchemy 비동기 (aiosqlite/asyncpg) 기반. 서버 시작 시 테이블 자동 생성.

| 테이블 | 설명 |
|--------|------|
| `paper_account` | 모의투자 계좌 상태 (자본, 현금, 설정값) |
| `paper_trades` | 진입/청산 거래 내역 (OPEN/CLOSED) |
| `paper_portfolio_history` | 5분 단위 포트폴리오 가치 이력 |

```bash
# .env에 DB URL 설정 (미설정 시 SQLite 기본 사용)
DATABASE_URL=sqlite+aiosqlite:///./paper_trading.db
# 또는 PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
```

---

## ⚙️ 설치 및 설정

### 1. 환경 변수 설정
```bash
# .env 파일 생성
cp .env.example .env

# 필수 항목 입력
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
DATABASE_URL=sqlite+aiosqlite:///./paper_trading.db  # 선택 (기본값)
```

### 2. 백엔드 설치 및 실행
```bash
pip install -r requirements.txt
uvicorn backend.api.main:app --reload --port 8000
```

### 3. 프론트엔드 설치 및 실행
```bash
cd frontend
npm install
npm run dev
```

---

## 🎓 기술 스택

### Backend
- **FastAPI** + **uvicorn** - 고성능 비동기 웹 프레임워크
- **SQLAlchemy (async)** + **aiosqlite** - 비동기 ORM
- **pydantic v2** - 데이터 검증
- **pandas** - 데이터 분석
- **KIS REST API** - 한국투자증권 Open API (거래량순위, 분봉)
- **pykrx** - 한국 주식 일봉/기본정보 보조 데이터
- **yfinance** - 미국 주식 데이터
- **Groq API** (llama-3.3-70b-versatile) - AI 거래 분석 (무료)
- **beautifulsoup4** - Naver Finance 뉴스 크롤링

### Frontend
- **React** + **Vite** + **TypeScript**
- **TailwindCSS** - 스타일링
- **Lightweight-Charts** - 포트폴리오/캔들 차트
- **lucide-react** - 아이콘

### Background Tasks (서버 시작 시 자동 실행)
| 태스크 | 주기 | 역할 |
|--------|------|------|
| `collector` | 상시 | KIS WebSocket 실시간 호가 수집 |
| `scorer` | 5분 | 급등주 점수 사전 계산 |
| `paper_trading` | 5분 | 신호 스캔 → 자동 진입/청산 |

---

## 📈 모의투자 전략 설명

### 진입 조건
- 거래량 급증 상위 종목 스캔
- 등락률 3~15% (과열/침체 제외)
- 최소 거래량 100,000주 이상
- 설정된 최소 점수 이상

### 청산 조건 (분할)
| 조건 | 비율 | 청산량 |
|------|------|--------|
| 1차 익절 | +2% | 잔여 1/3 |
| 2차 익절 | +5% | 잔여 1/2 |
| 3차 익절 | +10% | 전량 |
| 1차 손절 | -1% | 잔여 1/3 |
| 2차 손절 | -2% | 전량 |
| 트레일링 스톱 | 최고가 대비 -4% | 전량 |
| 최대 보유 | 5일 초과 | 전량 |

---

## ✅ 로드맵

### 완료된 기능
- [x] 급등주 발굴 시스템 (KIS REST API)
- [x] 자동 매매 신호 생성 (combined/volume/technical)
- [x] 백테스팅 엔진
- [x] Grid Search 최적화
- [x] 섹터 모니터링 시스템 (2026-03-02)
- [x] 프론트엔드 대시보드 (2026-03-04)
- [x] 모의투자 시뮬레이션 엔진 (2026-03-11)
- [x] DB 기반 상태 영속화 (2026-03-11)
- [x] 관심종목 탭 (2026-03-11)
- [x] 투자일지 탭 (2026-03-11)
- [x] 수동 포지션 추가 + 현재가 자동 조회 (2026-03-11)
- [x] 투자일지 AI 분석 모달 (2026-03-12)
- [x] Naver Finance 뉴스 크롤링 연동 (2026-03-12)
- [x] 다국어 혼용 필터 (한문·일본어·러시아어·베트남어 제거) (2026-03-12)

### 향후 계획
- [ ] 실시간 알림 (Telegram Bot)
- [ ] 자동 주문 실행 (KIS 실전계좌 연동)
- [ ] ML 기반 신호 개선
- [ ] 미국 주식 모의투자 지원

---

## ⚠️ 주의사항

1. **투자 리스크**: 이 시스템은 교육/연구 목적이며, 실제 투자는 본인 책임입니다.
2. **백테스팅 한계**: 과거 성과가 미래를 보장하지 않습니다.
3. **모의투자**: 실제 거래 없이 시뮬레이션만 수행합니다.
4. **API 한도**: KIS API 요청 한도 초과 시 일부 기능이 제한될 수 있습니다.

---

## 📝 변경 이력

### v3.1.0 (2026-03-12)
- ✨ **투자일지 AI 분석 모달 추가**
  - 종목명 클릭 → 92vw × 90vh 모달에서 Groq AI 7개 섹션 실시간 스트리밍 분석
  - 섹션: 종목·섹터 정보 / 관련 뉴스 / 차트 패턴 / 당일 종가 / 주가 종합 / 익일 예상 / 거래 교훈
  - SSE 스트리밍 (`GET /paper/journal/{id}/analyze`) → 프론트 `ReadableStream` 수신
- ✨ **Naver Finance 뉴스 크롤링 연동**
  - 매수일 기준 3일 전~당일 범위 뉴스 최대 3개 자동 크롤링
  - 실제 뉴스 제목 + 링크를 AI 프롬프트에 주입하여 할루시네이션 방지
- 🐛 **다국어 혼용 필터 (`_clean_foreign`)**
  - 스트리밍 줄 단위 버퍼링으로 OHLCV 등 약어 청크 분리 문제 해결
  - CJK 한자·일본어 / 키릴(러시아어) / 라틴 이형(베트남어) / 영문 소문자 단어 제거
  - 허용 약어 보호: OHLCV, ETF, PER, PBR, MACD, RSI 등 30여 개
- 🎨 **UI 개선**
  - 섹션 헤더 regex 수정 (첫 단어 잘림 버그 해결 `^\d+\.\s*`)
  - AI 모델: Groq Llama-3.3-70b-versatile (무료, 영문 system 지시)

### v3.0.0 (2026-03-11)
- ✨ **모의투자 시뮬레이션 시스템 추가**
  - `PaperEngine` 싱글턴 엔진: 5분 주기 자동 진입/청산
  - 분할 익절(+2%/+5%/+10%) + 분할 손절(-1%/-2%) + 트레일링 스톱
  - Break-even 전략: 1차 익절 후 손절가를 자동으로 진입가로 이동
  - 수동 포지션 추가 (종목코드 입력 → 현재가 자동 조회)
  - 포트폴리오 가치 차트 (lightweight-charts)
- ✨ **DB 레이어 추가** (`backend/db/`)
  - SQLAlchemy async ORM (aiosqlite/asyncpg)
  - 서버 시작 시 테이블 자동 생성 및 이전 상태 복원
  - `PaperAccount`, `PaperTrade`, `PaperPortfolioHistory` 모델
- ✨ **관심종목 탭 추가** (`WatchlistDashboard.tsx`)
  - localStorage 기반 종목 관리 (`watchlist_v1` 키)
  - MA/거래량/신호/점수 분석 그리드
  - 현재가로 즉시 모의투자 매수 버튼
- ✨ **투자일지 탭 추가** (`InvestmentJournalDashboard.tsx`)
  - 날짜/종목/수익여부 필터
  - 페이지네이션 (offset 기반)
  - 컬럼 구분선, 총 손익 요약
- ✨ **`/stocks/{code}/analyze` 엔드포인트 추가**
  - MA5/20/60/120, 거래량비율, 52주/20일 신고가, combined 신호
  - 5분 캐시 적용
- ✨ **모니터링 API 추가** (`/monitor/`)
  - 인메모리 로그 버퍼 (`log_buffer.py`)
  - 태스크 상태 조회 (collector/scorer/paper)
- 🐛 **모의투자 초기자본 설정 개선**
  - 서버 상태 `initial_capital`을 폼에 반영 (최초 1회)
  - 실행 중에도 설정 폼 표시 (disabled 처리)

### v2.2.0 (2026-03-04)
- 🔄 KIS REST API KR 급등주 연동 교체 (pykrx → KIS)
- ✨ 매매신호 UI 개선 (종목명/주가 표시)
- ✨ 가격 조건 통화 분리 (원/달러)

### v2.1.0 (2026-03-02)
- ✨ 섹터 모니터링 시스템 추가
- ⚡ 급등주 스크리너 개선 (day_gainers + most_actives 통합)

### v2.0.0 (2026-02-25)
- Grid Search 파라미터 최적화
- API 재구조화

---

**버전**: 3.1.0
**최종 업데이트**: 2026-03-12

**Happy Trading! 📈🚀**
