# API Reference - 주식 단타매매 시스템

## 📑 목차
- [개요](#개요)
- [📊 Stocks API](#-stocks-api-주식-데이터)
- [🚦 Signals API](#-signals-api-매매-신호)
- [📈 Backtest API](#-backtest-api-백테스팅)
- [🔧 Optimize API](#-optimize-api-파라미터-최적화)
- [에러 코드](#에러-코드)

---

## 개요

**Base URL**: `http://localhost:8000`

**인증**: 현재 인증 없음 (개인용)

**응답 형식**: JSON

---

## 📊 Stocks API (주식 데이터)

### GET `/stocks/surge`
급등주 목록 조회

**Query Parameters:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| market | string | "KR" | "KR" 또는 "US" |

**Response:**
```json
[
  {
    "code": "DRS",
    "name": "Leonardo DRS, Inc.",
    "price": 43.82,
    "change_rate": 14.89,
    "volume": 1500000,
    "change_price": 6.45
  }
]
```

---

### GET `/stocks/penny-stocks`
1달러 미만 주식 조회 (미국 시장)

**Response:**
```json
[
  {
    "code": "ABCD",
    "name": "Example Corp",
    "price": 0.85,
    "change_rate": 15.5,
    "volume": 5000000,
    "change_price": 0.11,
    "volume_pattern": {
      "d0": 5000000,
      "d1": 2000000,
      "d2": 1500000,
      "d3": 1800000,
      "surge_ratio": 2.5
    }
  }
]
```

---

### GET `/stocks/{code}/score`
종목 점수 조회

**Path Parameters:**
- `code`: 종목 코드

**Query Parameters:**
- `market`: "KR" | "US" (기본값: "KR")

**Response:**
```json
{
  "code": "AAPL",
  "calculated_at": "2026-02-25T18:00:00",
  "value_score": 35.0,
  "trend_score": 25.0,
  "stability_score": 18.0,
  "risk_penalty": 0.0,
  "total_score": 78.0,
  "fundamental": {...},
  "technical": {...}
}
```

---

### GET `/stocks/{code}/daily`
일봉 데이터 조회

**Path Parameters:**
- `code`: 종목 코드

**Query Parameters:**
- `market`: "KR" | "US"

**Response:**
```json
[
  {
    "time": "2026-02-25",
    "open": 150.0,
    "high": 152.5,
    "low": 149.0,
    "close": 151.0,
    "volume": 1000000
  }
]
```

---

## 🚦 Signals API (매매 신호)

### GET `/signals/entry/{code}`
진입 신호 조회

**Path Parameters:**
- `code`: 종목 코드

**Query Parameters:**
- `market`: "KR" | "US" (기본값: "KR")
- `strategy`: "volume" | "technical" | "pattern" | "combined" (기본값: "combined")

**Response:**
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
  "timestamp": "2026-02-25T18:00:00",
  "current_price": 151.0,
  "breakdown": {...}
}
```

---

### GET `/signals/scan`
급등주 진입 신호 스캔

**Query Parameters:**
- `market`: "KR" | "US" (기본값: "KR")
- `strategy`: 전략 (기본값: "combined")
- `min_score`: 최소 점수 (기본값: 60)

**Response:**
```json
[
  {
    "code": "DRS",
    "market": "US",
    "signal": "BUY",
    "strength": "high",
    "score": 77.0,
    "reasons": [...],
    "current_price": 43.82,
    "stock_info": {...}
  }
]
```

---

### POST `/signals/exit`
청산 신호 조회

**Request Body:**
```json
{
  "code": "AAPL",
  "entry_price": 150.0,
  "entry_time": "2026-02-25T09:30:00",
  "market": "US"
}
```

**Response:**
```json
{
  "code": "AAPL",
  "should_exit": true,
  "exit_type": "take_profit",
  "volume_pct": 0.5,
  "reason": "1차 익절 +3%",
  "current_price": 154.5,
  "profit_loss": 4.5,
  "profit_loss_pct": 3.0,
  "holding_time": 15.5
}
```

---

## 📈 Backtest API (백테스팅)

### POST `/backtest/run`
백테스팅 실행

**Request Body:**
```json
{
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "market": "US",
  "days": 90,
  "initial_capital": 10000.0,
  "entry_strategy": "combined",
  "min_entry_score": 60.0,
  "stop_loss_ratio": -0.02,
  "max_holding_days": 5
}
```

**Response:**
```json
{
  "summary": {
    "initial_capital": 10000.0,
    "final_capital": 12500.0,
    "net_profit": 2500.0,
    "roi": 25.0,
    "total_trades": 45,
    "winning_trades": 30,
    "losing_trades": 15,
    "win_rate": 66.67,
    "profit_factor": 2.5,
    "max_drawdown": 8.5
  },
  "advanced_metrics": {
    "sharpe_ratio": 1.85,
    "sortino_ratio": 2.3,
    "calmar_ratio": 2.94,
    "expectancy": 55.56
  },
  "trades": [...],
  "monthly_returns": [...]
}
```

---

### POST `/backtest/compare`
전략 비교

**Request Body:**
```json
{
  "symbols": ["AAPL", "MSFT"],
  "market": "US",
  "days": 90,
  "strategies": ["volume", "technical", "combined"]
}
```

**Response:**
```json
{
  "comparison": {
    "strategies": [
      {
        "strategy": "volume",
        "roi": 15.2,
        "sharpe_ratio": 1.45,
        "win_rate": 62.5,
        "max_drawdown": 10.2
      },
      {
        "strategy": "combined",
        "roi": 25.0,
        "sharpe_ratio": 1.85,
        "win_rate": 66.7,
        "max_drawdown": 8.5
      }
    ],
    "best_roi": "combined",
    "best_sharpe": "combined"
  }
}
```

---

## 🔧 Optimize API (파라미터 최적화)

### POST `/optimize/grid-search`
Grid Search 파라미터 최적화

**Request Body:**
```json
{
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "market": "US",
  "days": 60,
  "optimization_metric": "sharpe_ratio",
  "stop_loss_ratios": [-0.01, -0.02, -0.03],
  "take_profit_ratios": [0.03, 0.04, 0.05],
  "max_holding_days_options": [3, 5, 7],
  "min_entry_scores": [55, 60, 65],
  "position_size_pcts": [0.2, 0.3, 0.4]
}
```

**Response:**
```json
{
  "status": "completed",
  "optimization_id": "opt_20260225_180000",
  "optimization_metric": "sharpe_ratio",
  "execution_time_seconds": 245.5,
  "total_combinations_tested": 135,
  "best_params": {
    "stop_loss_ratio": -0.02,
    "take_profit_targets": [...],
    "max_holding_days": 5,
    "min_entry_score": 65,
    "position_size_pct": 0.3
  },
  "best_performance": {
    "sharpe_ratio": 2.1,
    "roi": 32.5,
    "win_rate": 68.5,
    "max_drawdown": 7.2
  },
  "top_5_results": [...],
  "parameter_analysis": {...}
}
```

---

### POST `/optimize/quick`
빠른 최적화 (제한된 범위)

**Request Body:**
```json
{
  "symbols": ["AAPL", "MSFT"],
  "market": "US",
  "days": 60,
  "optimization_metric": "sharpe_ratio"
}
```

**Response:** (grid-search와 동일 형식)

---

### GET `/optimize/metrics`
사용 가능한 최적화 지표 목록

**Response:**
```json
{
  "metrics": [
    {
      "name": "roi",
      "display_name": "수익률 (ROI)",
      "description": "총 수익률을 최대화",
      "unit": "%",
      "recommended_for": "공격적 전략"
    },
    {
      "name": "sharpe_ratio",
      "display_name": "샤프 비율",
      "description": "위험 대비 수익률 최적화",
      "unit": "ratio",
      "recommended_for": "균형잡힌 전략"
    }
  ]
}
```

---

### GET `/optimize/param-ranges`
기본 파라미터 범위

**Response:**
```json
{
  "stop_loss_ratios": [-0.01, -0.015, -0.02, -0.025, -0.03],
  "take_profit_ratios": [0.03, 0.04, 0.05],
  "max_holding_days_options": [3, 5, 7],
  "min_entry_scores": [55, 60, 65],
  "position_size_pcts": [0.2, 0.3, 0.4],
  "total_combinations": 375
}
```

---

## 에러 코드

| 코드 | 설명 |
|------|------|
| 200 | 성공 |
| 400 | 잘못된 요청 (파라미터 오류) |
| 404 | 리소스를 찾을 수 없음 |
| 500 | 서버 내부 오류 |

---

## 사용 시나리오

### 시나리오 1: 급등주 찾고 신호 확인
```bash
# 1. 급등주 조회
curl "http://localhost:8000/stocks/surge?market=US"

# 2. 특정 종목 진입 신호 확인
curl "http://localhost:8000/signals/entry/AAPL?market=US"

# 3. 급등주 전체 스캔
curl "http://localhost:8000/signals/scan?market=US&min_score=70"
```

### 시나리오 2: 전략 백테스팅 및 최적화
```bash
# 1. 기본 백테스팅
curl -X POST "http://localhost:8000/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["AAPL","MSFT"],"market":"US","days":90}'

# 2. 전략 비교
curl -X POST "http://localhost:8000/backtest/compare" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["AAPL","MSFT"],"strategies":["volume","combined"]}'

# 3. 파라미터 최적화
curl -X POST "http://localhost:8000/optimize/quick" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["AAPL","MSFT"],"optimization_metric":"sharpe_ratio"}'
```

### 시나리오 3: 실시간 포지션 모니터링
```bash
# 1. 청산 신호 확인
curl -X POST "http://localhost:8000/signals/exit" \
  -H "Content-Type: application/json" \
  -d '{
    "code":"AAPL",
    "entry_price":150.0,
    "entry_time":"2026-02-25T09:30:00",
    "market":"US"
  }'
```

---

## 카테고리 요약

### 📊 Stocks (주식 데이터)
- 급등주, 페니스탁, 종목 점수, OHLCV 차트

### 🚦 Signals (매매 신호)
- 진입 신호, 청산 신호, 신호 스캔

### 📈 Backtest (백테스팅)
- 백테스팅 실행, 전략 비교, 성과 분석

### 🔧 Optimize (최적화) ⭐ NEW
- Grid Search, 빠른 최적화, 지표 정보

---

**마지막 업데이트**: 2026-02-25
