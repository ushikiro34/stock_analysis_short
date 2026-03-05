# API Reference

**Base URL**: `http://localhost:8000`
**인증**: 없음 (개인용)
**응답 형식**: JSON
**상세 문서**: http://localhost:8000/docs (Swagger UI)

---

## Stocks API — `/stocks`

| Method | 경로 | 설명 | 캐시 |
|--------|------|------|------|
| GET | `/stocks/surge` | 급등주 목록 (`market=KR\|US`, `limit=100`) | 30초 |
| GET | `/stocks/surge/finviz` | Finviz 스크리너 (`strategy`, `limit`) | 5분 |
| GET | `/stocks/surge/combined` | Finviz 조합 전략 | 5분 |
| GET | `/stocks/screener/strategies` | 사용 가능한 Finviz 전략 목록 | - |
| GET | `/stocks/penny-stocks` | 미국 1달러 미만 거래량 급증 종목 | 5분 |
| GET | `/stocks/{code}/score` | 종목 점수 (`market=KR\|US`) | 10분 |
| GET | `/stocks/{code}/daily` | 일봉 OHLCV (90일) | 5분 |
| GET | `/stocks/{code}/weekly` | 주봉 OHLCV (1년) | 10분 |
| GET | `/stocks/{code}/minute` | 분봉 OHLCV (최근 30개) | 1분 |

### surge 응답 예시
```json
[
  {
    "code": "005930",
    "name": "삼성전자",
    "price": 73400,
    "change_rate": 3.52,
    "volume": 15234000,
    "change_price": 2500
  }
]
```

### score 응답 예시
```json
{
  "code": "005930",
  "value_score": 72,
  "trend_score": 65,
  "stability_score": 80,
  "risk_penalty": 5,
  "total_score": 74,
  "fundamental": { "per": 14.2, "pbr": 1.1, "roe": 12.3 },
  "technical": { "ma20": 72100, "rsi": 54.3, "volatility": 0.018 }
}
```

---

## Signals API — `/signals`

| Method | 경로 | 설명 | 캐시 |
|--------|------|------|------|
| GET | `/signals/entry/{code}` | 단일 종목 진입 신호 (`market`, `strategy`) | - |
| GET | `/signals/scan` | 급등주 신호 스캔 (`market`, `strategy`, `min_score=60`) | 3분 |
| POST | `/signals/exit` | 청산 신호 (`code`, `entry_price`, `entry_time`, `market`) | - |

**strategy 값**: `combined`(기본) | `volume` | `technical` | `pattern` | `rsi_golden_cross`

### entry 응답 예시
```json
{
  "code": "005930",
  "signal": "BUY",
  "strength": "high",
  "score": 78,
  "reasons": ["거래량 MA5 대비 3.2배", "RSI 상승 추세"],
  "current_price": 73400
}
```

---

## Backtest API — `/backtest`

| Method | 경로 | 설명 |
|--------|------|------|
| POST | `/backtest/run` | 백테스팅 실행 |
| POST | `/backtest/compare` | 두 전략 비교 |

### run 요청 body
```json
{
  "code": "AAPL",
  "market": "US",
  "strategy": "combined",
  "period_days": 90
}
```

---

## Optimize API — `/optimize`

| Method | 경로 | 설명 |
|--------|------|------|
| POST | `/optimize/quick` | 빠른 최적화 (제한된 파라미터 범위) |
| POST | `/optimize/grid-search` | 전체 Grid Search |
| GET | `/optimize/metrics` | 사용 가능한 최적화 지표 목록 |
| GET | `/optimize/param-ranges` | 파라미터 범위 조회 |

**metric 값**: `sharpe_ratio`(추천) | `total_return` | `win_rate` | `profit_factor` | `max_drawdown`

---

## Paper Trading API — `/paper`

| Method | 경로 | 설명 |
|--------|------|------|
| POST | `/paper/start` | 시뮬레이션 시작 (StartConfig body) |
| POST | `/paper/stop` | 시뮬레이션 중지 |
| POST | `/paper/reset` | 전체 초기화 |
| GET | `/paper/status` | 계좌 현황 |
| GET | `/paper/positions` | 현재 오픈 포지션 |
| GET | `/paper/trades` | 체결 거래 내역 (`limit=30`) |
| GET | `/paper/history` | 포트폴리오 가치 이력 (`limit=200`) |

### start 요청 body
```json
{
  "initial_capital": 10000000,
  "market": "KR",
  "strategy": "combined",
  "min_score": 65,
  "max_positions": 3,
  "position_size_pct": 0.3
}
```

---

## Sectors API — `/sectors`

| Method | 경로 | 설명 |
|--------|------|------|
| GET | `/sectors/list` | 섹터 목록 (10개 섹터, 74개 종목) |
| GET | `/sectors/{sector}/analyze` | 섹터 분석 |
| GET | `/sectors/{sector}/signals` | 섹터 내 신호 스캔 |
| GET | `/sectors/compare` | 섹터 간 비교 |
