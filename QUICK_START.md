# 빠른 시작 가이드

> 설치 및 환경 세팅은 [SETUP_GUIDE.md](SETUP_GUIDE.md) 참조

---

## 서버 실행

```bash
# 백엔드 (프로젝트 루트에서)
uvicorn backend.api.main:app --reload --port 8000

# 프론트엔드 (별도 터미널)
cd frontend && npm run dev
```

- 백엔드: http://localhost:8000
- 프론트엔드: http://localhost:5173
- API 문서(Swagger): http://localhost:8000/docs

---

## 기본 워크플로우

### Step 1: 급등주 발굴

```bash
# 한국 시장 (KIS API, 2만원 이하 거래량 급증)
curl "http://localhost:8000/stocks/surge?market=KR"

# 미국 시장 (Yahoo Finance, day_gainers + most_actives ~47개)
curl "http://localhost:8000/stocks/surge?market=US"

# 미국 시장 (Finviz, 전략 선택, 최대 500개)
curl "http://localhost:8000/stocks/surge/finviz?strategy=gainers&limit=100"
```

Finviz 전략: `gainers` | `breakout` | `volume` | `momentum` | `penny`

### Step 2: 매매 신호 스캔

```bash
# 급등주 전체 스캔 (점수 60점 이상)
curl "http://localhost:8000/signals/scan?market=KR&min_score=60"

# 단일 종목 신호 조회
curl "http://localhost:8000/signals/entry/005930?market=KR&strategy=combined"
```

전략: `combined`(기본) | `volume` | `technical` | `pattern` | `rsi_golden_cross`

### Step 3: 종목 점수 조회

```bash
curl "http://localhost:8000/stocks/005930/score?market=KR"
```

응답: `value_score`, `trend_score`, `stability_score`, `risk_penalty`, `total_score`

### Step 4: 백테스팅

```bash
curl -X POST "http://localhost:8000/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "AAPL",
    "market": "US",
    "strategy": "combined",
    "period_days": 90
  }'
```

### Step 5: 파라미터 최적화

```bash
# 빠른 최적화
curl -X POST "http://localhost:8000/optimize/quick" \
  -H "Content-Type: application/json" \
  -d '{"code": "AAPL", "market": "US", "metric": "sharpe_ratio"}'
```

최적화 지표: `sharpe_ratio`(추천) | `total_return` | `win_rate` | `profit_factor` | `max_drawdown`

### Step 6: 모의투자 시뮬레이션

```bash
# 시작 (KR, combined 전략, 점수 65점 이상, 최대 3종목)
curl -X POST "http://localhost:8000/paper/start" \
  -H "Content-Type: application/json" \
  -d '{
    "initial_capital": 10000000,
    "market": "KR",
    "strategy": "combined",
    "min_score": 65,
    "max_positions": 3,
    "position_size_pct": 0.3
  }'

# 상태 조회
curl "http://localhost:8000/paper/status"

# 중지 / 초기화
curl -X POST "http://localhost:8000/paper/stop"
curl -X POST "http://localhost:8000/paper/reset"
```

모의투자는 **5분 주기** 자동 루프 (장 시간 09:00~15:20 KST에만 실행).

---

## 탭 구성 (프론트엔드)

| 탭 | 기능 |
|----|------|
| Stocks | 급등주 리스트, 차트(분봉/일봉/주봉), 종목 점수 |
| Signals | 진입/청산 신호 대시보드, 알림 |
| Backtest | 백테스팅 실행 및 성과 분석 |
| Optimize | 파라미터 Grid Search 최적화 |
| 모의투자 | 자동매매 시뮬레이션, 포지션/거래 내역, 포트폴리오 차트 |

---

## 주의사항

- KIS API 토큰은 **1일 1회** 발급 가능. 서버를 하루에 여러 번 재시작하면 KR 신호 스캔이 403 오류 발생
- `pykrx`는 KR OHLCV(기술적 지표) 전용, KRX 서버 점검 시간(오전 6~8시)에 일시 실패 가능
- Finviz는 분당 10회 Rate Limit 적용
