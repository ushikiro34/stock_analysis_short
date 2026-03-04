# Stock Analysis System - 시스템 전체 구조 및 필터/전략 정리

## 📋 목차
1. [프론트엔드 - 주식 리스트 기준](#프론트엔드---주식-리스트-기준)
2. [백엔드 - 급등주 필터링 로직](#백엔드---급등주-필터링-로직)
3. [매매 신호 전략](#매매-신호-전략)
4. [청산 전략](#청산-전략)
5. [스크리너 전략 (Finviz)](#스크리너-전략-finviz)
6. [API 엔드포인트 요약](#api-엔드포인트-요약)

---

## 프론트엔드 - 주식 리스트 기준

### 📊 주식 분석 탭 (Stocks Dashboard)

#### 데이터 소스
프론트엔드의 주식 리스트는 **백엔드의 급등주 API**를 호출하여 표시됩니다:

```typescript
// API 호출: /stocks/surge?market={KR|US}&limit=100
const data = await fetchSurgeStocks(market);
```

#### 표시 기준 (Market별)

**🇰🇷 한국 시장 (KR)**
- **API**: `GET /stocks/surge?market=KR`
- **데이터 소스**: KIS REST API
- **필터링**:
  - 가격: **2만원 이하**
  - 거래량: **급증 종목** (volume_rank)
  - 최대 종목 수: 100개 (기본값)
- **정렬**: 거래량 순위 (높은 순)
- **캐싱**: 30초

**🇺🇸 미국 시장 (US)**
- **API**: `GET /stocks/surge?market=US`
- **데이터 소스**: Yahoo Finance Screener
- **필터링**:
  - `day_gainers` (25개)
  - `most_actives` (25개)
  - 중복 제거 후 병합
  - 최대 종목 수: **약 47개** (Yahoo Finance 제한)
- **정렬**: 변동률 절대값 (높은 순)
- **캐싱**: 30초

#### 프론트엔드 필터 기능

사용자가 UI에서 추가로 필터링 가능:

1. **가격 필터** (Price Filter) - 시장별 통화 분리
   - **전체**: 모든 가격대
   - **저가주 필터**:
     - 🇰🇷 한국장: `1,000원 미만`
     - 🇺🇸 미국장: `$1 미만`
   - **가격 범위**: 사용자 지정 (From ~ To)
     - 🇰🇷 한국장: 원(₩) 단위 입력 (`최소(원)` ~ `최대(원)`)
     - 🇺🇸 미국장: 달러($) 단위 입력 (`From($)` ~ `To($)`)
   - **시장 전환 시**: 가격 필터 자동 초기화 (원/달러 혼용 방지)

2. **종목명 검색**
   - 종목 코드 검색 (예: AAPL, 005930)
   - 종목명 검색 (예: Apple, 삼성전자)
   - 대소문자 구분 없음

```typescript
// 필터 적용 로직 (frontend/src/pages/StocksDashboard.tsx)
const filteredStocks = useMemo(() => {
    let filtered = [...surgeStocks];

    // 가격 필터
    if (filter.priceFilter === 'penny') {
        filtered = filtered.filter(s => s.price < 1);
    } else if (filter.priceFilter === 'range') {
        if (filter.priceFrom !== undefined) {
            filtered = filtered.filter(s => s.price >= filter.priceFrom!);
        }
        if (filter.priceTo !== undefined) {
            filtered = filtered.filter(s => s.price <= filter.priceTo!);
        }
    }

    // 종목명 검색
    if (filter.stockName.trim()) {
        const searchTerm = filter.stockName.toLowerCase();
        filtered = filtered.filter(s =>
            s.code.toLowerCase().includes(searchTerm) ||
            s.name.toLowerCase().includes(searchTerm)
        );
    }

    return filtered;
}, [surgeStocks, filter]);
```

#### 자동 갱신
- **급등주 리스트**: 30초마다 자동 갱신
- **차트/점수 데이터**: 10초마다 자동 갱신 (선택된 종목)

---

## 백엔드 - 급등주 필터링 로직

### 📍 API 위치
**File**: `backend/api/routers/stocks.py`

### 1. 한국 시장 (KR) - KIS API

```python
@router.get("/surge")
async def get_surge_stocks(market: str = "KR", limit: int = 100):
    """
    급등주 목록
    - KR: 가격 2만원 이하 거래량 급증 종목
    """
    if market == "KR":
        results = await kis_client.get_volume_rank(max_price=20000, limit=limit)
        return results
```

**필터링 기준**:
- ✅ 가격 ≤ 20,000원
- ✅ 거래량 급증 (volume_rank API)
- ✅ 최대 100개 종목

### 2. 미국 시장 (US) - Yahoo Finance

```python
@router.get("/surge")
async def get_surge_stocks(market: str = "US", limit: int = 100):
    """
    급등주 목록
    - US: Top Gainers (day_gainers + most_actives)
    """
    if market == "US":
        from ...us.yfinance_client import get_us_surge_stocks
        results = await get_us_surge_stocks(limit=limit)
        return results
```

**File**: `backend/us/yfinance_client.py`

```python
async def get_us_surge_stocks(limit: int = 100) -> list[dict]:
    """
    Yahoo Finance 스크리너 조합
    - day_gainers: 25개
    - most_actives: 25개
    - 중복 제거 후 변동률 순 정렬
    """
    def _fetch():
        gainers = screen("day_gainers").get("quotes", [])
        actives = screen("most_actives").get("quotes", [])

        # 중복 제거
        all_quotes = {}
        for q in gainers + actives:
            symbol = q.get("symbol", "")
            if symbol and symbol not in all_quotes:
                all_quotes[symbol] = q

        # 변동률 절대값으로 정렬
        stocks = list(all_quotes.values())
        stocks.sort(key=lambda x: abs(x["change_rate"]), reverse=True)
        return stocks[:limit]

    return await _run_sync(_fetch)
```

**제한사항**:
- ⚠️ Yahoo Finance API 제한: 최대 약 47개 종목
  - day_gainers: 25개
  - most_actives: 25개
  - 중복 제거 후 실제 약 47개

### 3. Penny Stocks (US 특수 필터)

```python
@router.get("/penny-stocks")
async def get_penny_stocks():
    """
    미국 주식 중 조건 필터링:
    - 주가 1달러 미만
    - 당일 거래량 급증 (전일 대비 2배 이상)
    - 최근 2일(D-1, D-2) 거래량이 그 이전(D-3)보다 작음
    """
    from ...us.yfinance_client import get_penny_stocks_with_volume_pattern
    results = await get_penny_stocks_with_volume_pattern(limit=50)
    return results
```

**필터링 기준**:
- ✅ 가격 < $1
- ✅ 거래량 급증 (당일 / 전일 ≥ 2.0)
- ✅ 거래량 패턴: D-1, D-2 < D-3 (조용했다가 터지는 패턴)
- ✅ 최대 50개

---

## 매매 신호 전략

### 📍 전략 위치
**File**: `backend/core/signals.py`

### 전략 개요

| 전략 | 클래스 | 핵심 지표 | 점수 배분 | 최소 데이터 |
|------|--------|----------|----------|------------|
| **거래량 돌파** | `VolumeBreakoutSignal` | 거래량 급증 + 가격 상승 | 100점 | 6일 |
| **기술적 돌파** | `TechnicalBreakoutSignal` | MA, RSI, MACD, BB | 100점 | 30일 |
| **가격 패턴** | `PricePatternSignal` | 눌림목, 저점 높이기, 횡보 돌파 | 100점 | 15일 |
| **RSI 골든크로스** | `RSIGoldenCrossSignal` | RSI 30 돌파 + MA50/200 골든크로스 | 100점 | 200일 |
| **복합 전략** | `SignalManager` | 위 3개 전략 가중 평균 | 100점 | 120일 |

---

### 1️⃣ 거래량 돌파 전략 (Volume Breakout)

#### 조건
```python
class VolumeBreakoutSignal:
    # 조건 1: 거래량 급증 (전일 대비 2배) → +30점
    current_volume >= prev_volume * 2.0

    # 조건 2: 가격 상승 (전일 대비 2% 이상) → +25점
    current_price > prev_close * 1.02

    # 조건 3: 거래량 MA5 돌파 (3배 이상) → +25점
    current_volume >= volume_ma5 * 3

    # 조건 4: 거래대금 증가 (2배 이상) → +20점
    current_amount > prev_amount * 2
```

#### 신호 강도
- **70점 이상**: BUY (HIGH)
- **50~69점**: BUY (MEDIUM)
- **50점 미만**: HOLD (LOW)

---

### 2️⃣ 기술적 돌파 전략 (Technical Breakout)

#### 조건
```python
class TechnicalBreakoutSignal:
    # 조건 1: MA20 상향 돌파 → +25점
    current_price > ma20 and prev_price <= prev_ma20

    # 조건 1-1: MA 정배열 (MA20 > MA60) → +15점
    ma20 > ma60

    # 조건 2: RSI 적정 범위 (30~70) → +15점
    30 < rsi < 70

    # 조건 2-1: RSI 상승 추세 → +10점
    current_rsi > prev_rsi

    # 조건 3: MACD 골든크로스 → +30점
    macd > signal and prev_macd <= prev_signal

    # 조건 4: 볼린저밴드 하단 반등 → +20점
    prev_price <= bb_lower * 1.02 and current_price > bb_lower
```

---

### 3️⃣ 가격 패턴 전략 (Price Pattern)

#### 패턴 1: 눌림목 (Pullback) - 최우선 ⭐

```python
class PricePatternSignal:
    def detect_pullback(self, ohlcv_data):
        # 1. 상승 추세 확인 (MA20 > MA60) → +20점
        # 2. 조정 기간 감지 (2~10일, 60% 이상 하락일) → +15점
        # 3. 지지선 터치 (MA20 ±3% 이내) → +25점
        # 4. 조정 기간 거래량 감소 → +20점
        # 5. 반등 신호 (당일 양봉) → +10점
        # 6. 거래량 증가 → +15점

        # 추세전환 위험 체크:
        # - MA20 < MA60 → 즉시 HOLD
        # - MA20 5% 이상 이탈 → 즉시 HOLD
        # - 이전 저점 하회 → 위험 표시
        # - RSI < 30 → 위험 표시
```

#### 패턴 2: 저점 높이기 (Higher Lows) → +30점

```python
def detect_higher_lows(self, closes, window=5):
    # 최근 두 저점 비교
    first_half = recent_data.head(window)
    second_half = recent_data.tail(window)

    first_low = first_half.min()
    second_low = second_half.min()

    return second_low > first_low  # 저점이 점점 높아지면 True
```

#### 패턴 3: 횡보 후 돌파 (Consolidation Breakout) → +40점

```python
def detect_consolidation_breakout(self, ohlcv_data, consolidation_days=5):
    # 횡보 구간 (변동폭 5% 이내)
    consolidation_range = (high - low) / low

    if consolidation_range <= 0.05:  # 5% 이내 횡보
        # 당일 종가가 횡보 고가 2% 이상 돌파
        breakout = current_close > consolidation_high * 1.02
```

#### 패턴 4: 상승 추세 → +15점
- 20일 수익률 > 0%

---

### 4️⃣ RSI 골든크로스 전략 (RSI Golden Cross) 💎

**최근 추가된 강력한 트렌드 전환 전략**

#### 조건
```python
class RSIGoldenCrossSignal:
    # 조건 1: 골든크로스 유지 (MA50 > MA200) → +40점
    ma50 > ma200

    # 조건 1-1: 최근 골든크로스 발생 (20일 이내) → +10점 추가

    # 조건 2: RSI 30 상향 돌파 (최근 5일 이내) → +30점
    # - 전일 RSI ≤ 30
    # - 당일 RSI > 30
    # 대안: RSI 30~50 구간 → +15점
    # 대안: RSI ≥ 50 → +5점

    # 조건 3: 거래량 증가
    # - 거래량 ≥ MA20 * 2.0 → +20점
    # - 거래량 ≥ MA20 * 1.2 → +10점

    # 조건 4: MA50 상승 추세 (5일 기준) → +10점

    # 조건 5: 가격 > MA50 → +5점
```

#### 전략 특성
- ✅ **매우 선택적**: 신호 빈도 낮음 (보수적)
- ✅ **고신뢰도**: 복합 조건으로 false signal 최소화
- ✅ **트렌드 전환 포착**: 과매도 탈출 + 상승 추세 확인
- ⚠️ **데이터 요구**: 최소 200일 (MA200 계산)

**실전 테스트 결과** (2026-03-02):
- 13개 BUY 신호 발견
- Top 종목: LION (90점), AAOI (80점), SOFI (80점, RSI 30 돌파 4일 전 감지!)

**상세 문서**: [RSI_GOLDEN_CROSS_STRATEGY.md](RSI_GOLDEN_CROSS_STRATEGY.md)

---

### 5️⃣ 복합 전략 (Combined)

```python
class SignalManager:
    def generate_entry_signal(self, strategy="combined"):
        if strategy == "combined":
            volume_result = self.volume_signal.check_signal(ohlcv_data)
            technical_result = self.technical_signal.check_signal(ohlcv_data)
            pattern_result = self.pattern_signal.check_signal(ohlcv_data)

            # 가중 평균
            total_score = (
                volume_result["score"] * 0.4 +      # 40%
                technical_result["score"] * 0.4 +   # 40%
                pattern_result["score"] * 0.2       # 20%
            )
```

---

## 청산 전략

### 📍 위치
**File**: `backend/core/signals.py`

### 1️⃣ 익절 전략 (Take Profit)

```python
class TakeProfitStrategy:
    # 분할 익절
    targets = [
        {"ratio": 0.03, "volume_pct": 0.5, "name": "1차 익절 +3%"},  # 50% 매도
        {"ratio": 0.05, "volume_pct": 0.3, "name": "2차 익절 +5%"},  # 30% 매도
        {"ratio": 0.10, "volume_pct": 0.2, "name": "3차 익절 +10%"}, # 20% 매도
    ]
```

### 2️⃣ 손절 전략 (Stop Loss)

```python
class StopLossStrategy:
    # 1. 고정 손절
    stop_loss_ratio = -0.02  # -2%

    # 2. 트레일링 스톱
    trailing_ratio = -0.03  # 최고가 대비 -3%
```

### 3️⃣ 시간 기반 청산 (Time-Based Exit)

```python
class TimeBasedExit:
    holding_limit_minutes = 30  # 최대 보유 30분
    market_close_time = "15:20"  # 장 마감 10분 전
```

---

## 스크리너 전략 (Finviz)

### 📍 위치
**File**: `backend/us/finviz_screener.py`

### Finviz vs Yahoo Finance

| 항목 | Yahoo Finance | Finviz |
|------|--------------|--------|
| 최대 종목 수 | **47개** | **500개+** |
| 필터 옵션 | 2개 (day_gainers, most_actives) | **60+ 필터** |
| 전략 다양성 | 제한적 | 5개 전략 |
| 속도 | 빠름 (~1s) | 보통 (4.5s, 캐시: <0.1s) |
| 커스터마이징 | 불가 | 가능 |

### Finviz 5대 전략

#### 1️⃣ Gainers (가격 급등주)

```python
STRATEGIES = {
    "gainers": {
        "name": "Top Gainers",
        "filters": {
            "Change": "Up 5%",                    # 5% 이상 상승
            "Average Volume": "Over 1M",          # 거래량 100만 이상
            "Market Cap.": "+Small (over $300mln)" # 시가총액 3억 이상
        }
    }
}
```
**결과**: 약 63개 종목, 4.5초

#### 2️⃣ Breakout (신고가 돌파)

```python
"breakout": {
    "name": "Breakout Stocks",
    "filters": {
        "Change": "Up 3%",
        "Current Volume": "Over 1M",
        "20-Day High/Low": "New High"  # 20일 신고가
    }
}
```

#### 3️⃣ Volume (거래량 급증)

```python
"volume": {
    "name": "High Volume",
    "filters": {
        "Relative Volume": "Over 2",      # 평균 대비 2배 거래량
        "Current Volume": "Over 1M",
        "Average Volume": "Over 500K"
    }
}
```

#### 4️⃣ Momentum (모멘텀)

```python
"momentum": {
    "name": "Momentum Stocks",
    "filters": {
        "Performance (Week)": "Up",       # 주간 상승
        "Change": "Up",
        "Current Volume": "Over 500K",
        "RSI (14)": "Overbought (60)"     # RSI 60 이상
    }
}
```

#### 5️⃣ Penny (페니스탁)

```python
"penny": {
    "name": "Penny Stocks",
    "filters": {
        "Price": "Under $1",              # $1 미만
        "Current Volume": "Over 1M",
        "Change": "Up 5%"
    }
}
```

### 캐싱 시스템

```python
_finviz_cache = {
    "gainers": {"data": [], "ts": 0},
    "breakout": {"data": [], "ts": 0},
    "volume": {"data": [], "ts": 0},
    "momentum": {"data": [], "ts": 0},
    "penny": {"data": [], "ts": 0},
}

CACHE_TTL = 300  # 5분
```

### Rate Limiting

```python
_request_times = deque(maxlen=10)

def _check_rate_limit():
    # 최대 10 requests/minute
    if len(_request_times) >= 10:
        elapsed = time() - _request_times[0]
        if elapsed < 60:
            raise Exception("Rate limit exceeded")
```

### 조합 전략 (Combined)

```python
async def get_combined_surge_stocks(limit: int = 100):
    # Gainers: 50%
    gainers = await get_finviz_surge_stocks(limit=int(limit * 0.5), strategy="gainers")

    # Volume: 30%
    volume = await get_finviz_surge_stocks(limit=int(limit * 0.3), strategy="volume")

    # Momentum: 20%
    momentum = await get_finviz_surge_stocks(limit=int(limit * 0.2), strategy="momentum")

    # 중복 제거 + 변동률 순 정렬
    all_stocks = {}
    for stock in gainers + volume + momentum:
        code = stock["code"]
        if code not in all_stocks:
            all_stocks[code] = stock

    results = list(all_stocks.values())
    results.sort(key=lambda x: abs(x.get("change_rate", 0)), reverse=True)
    return results[:limit]
```

---

## API 엔드포인트 요약

### 📊 Stocks API

| 엔드포인트 | Method | 설명 | 캐싱 |
|----------|--------|------|------|
| `/stocks/surge` | GET | 급등주 목록 (KR/US) | 30초 |
| `/stocks/surge/finviz` | GET | Finviz 스크리너 (5개 전략) | 5분 |
| `/stocks/surge/combined` | GET | Finviz 조합 전략 | 5분 |
| `/stocks/screener/strategies` | GET | 사용 가능한 전략 정보 | - |
| `/stocks/penny-stocks` | GET | 페니스탁 필터 (US) | 5분 |
| `/stocks/{code}/score` | GET | 종목 점수 조회 | 인메모리 |
| `/stocks/{code}/daily` | GET | 일봉 차트 (90일) | 5분 |
| `/stocks/{code}/weekly` | GET | 주봉 차트 (1년) | 10분 |
| `/stocks/{code}/minute` | GET | 분봉 차트 | 1분 |

### 🚦 Signals API

| 엔드포인트 | Method | 설명 | 캐싱 |
|----------|--------|------|------|
| `/signals/entry/{code}` | GET | 진입 신호 조회 | - |
| `/signals/scan` | GET | 급등주 신호 스캔 | 3분 |
| `/signals/exit` | POST | 청산 신호 조회 | - |

**Strategy 파라미터**:
- `volume`: 거래량 돌파
- `technical`: 기술적 돌파
- `pattern`: 가격 패턴
- `rsi_golden_cross`: RSI 골든크로스 ⭐ NEW
- `combined`: 복합 전략 (기본값)

### 📈 Backtest API

| 엔드포인트 | Method | 설명 |
|----------|--------|------|
| `/backtest/run` | POST | 백테스팅 실행 |

---

## 시스템 구조 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React + Vite)                  │
│                     http://localhost:5173                    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Stocks       │  │ Signals      │  │ Backtest     │     │
│  │ Dashboard    │  │ Dashboard    │  │ Dashboard    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│           │                 │                 │             │
│           └─────────────────┴─────────────────┘             │
│                           │                                 │
└───────────────────────────┼─────────────────────────────────┘
                            │ HTTP/REST API
┌───────────────────────────┼─────────────────────────────────┐
│                           ▼                                 │
│                 Backend (FastAPI)                           │
│                 http://localhost:8000                       │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               API Routers                            │   │
│  │  • /stocks   • /signals   • /backtest               │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               Core Services                          │   │
│  │  • score_service     • signal_service               │   │
│  │  • signals (4 strategies + manager)                 │   │
│  │  • indicators (RSI, MACD, MA, BB)                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               Data Sources                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ KIS REST    │  │ Yahoo       │  │ Finviz      │ │   │
│  │  │ (KR 급등주  │  │ Finance     │  │ Screener    │ │   │
│  │  │  + 펀더멘털)│  │ (US 급등주) │  │ (US 500+)   │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  │  ┌─────────────┐                                     │   │
│  │  │ pykrx       │                                     │   │
│  │  │ (KR OHLCV   │                                     │   │
│  │  │  기술지표만)│                                     │   │
│  │  └─────────────┘                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 핵심 파일 위치

### Frontend
- **App.tsx**: 메인 앱, 마켓 선택, 필터 UI
- **pages/StocksDashboard.tsx**: 주식 리스트, 차트, 점수 표시
- **pages/SignalsDashboard.tsx**: 매매 신호 대시보드
- **pages/BacktestDashboard.tsx**: 백테스팅 대시보드

### Backend - API
- **api/routers/stocks.py**: 주식 데이터 API (급등주, 차트, 점수)
- **api/routers/signals.py**: 매매 신호 API
- **api/routers/backtest.py**: 백테스팅 API

### Backend - Core
- **core/signals.py**: 4대 진입 전략 + 3대 청산 전략
- **core/signal_service.py**: 신호 생성 서비스
- **core/score_service.py**: 종목 점수 계산
- **core/indicators.py**: 기술적 지표 엔진

### Backend - Data Sources
- **kis/rest_client.py**: 한국투자증권 API (KR)
- **us/yfinance_client.py**: Yahoo Finance (US)
- **us/finviz_screener.py**: Finviz 스크리너 (US)

---

## 변경 이력

### v2.2.0 (2026-03-04)

#### 백엔드
- ✅ **KIS REST API KR 급등주 교체** (`backend/kis/rest_client.py`)
  - 기존: pykrx → KRX 사이트 스크래핑 (LOGOUT 응답으로 인해 작동 불가)
  - 변경: KIS REST API `FHPST01720000` 트랜잭션으로 교체
  - KOSPI(`J`) + KOSDAQ(`Q`) 거래량 상위 종목 각각 조회 후 병합
  - `change_rate` 양수 종목만 필터링, 내림차순 정렬
  - KIS 토큰 23시간 캐싱으로 분당 1회 Rate Limit 방지

- ✅ **KR 종목 펀더멘털 조회 KIS REST API로 교체** (`backend/core/score_service.py`, `backend/kis/rest_client.py`)
  - **원인**: KRX가 통계 데이터 API(`MDCSTAT` 시리즈)에 실제 로그인 세션 요구하도록 정책 변경
    - `finder_stkisu` (종목 목록): 정상 동작 유지
    - `MDCSTAT03502` (PER/PBR 날짜별): `400 LOGOUT` 응답 → **전 종목 펀더멘털 조회 불가**
    - 익명 JSESSIONID(홈 방문)로는 해결 불가, 실제 로그인 세션 필요
  - **변경**: `collect_fundamental()` 에서 pykrx 제거, KIS REST API 사용
    - KIS `FHKST01010100` 트랜잭션 (`/uapi/domestic-stock/v1/quotations/inquire-price`)
    - PER, PBR, EPS, BPS 조회 → ROE 계산 (`EPS / BPS * 100`)
  - **싱글턴 패턴**: `_kis_client` 모듈 레벨 공유로 토큰 재사용 (Rate Limit 방지)
  - pykrx는 **OHLCV 데이터 조회 전용**으로 역할 축소 (`collect_technical`에서만 사용)

- ✅ **매매 신호 알럿 시스템** (`frontend/src/App.tsx`, `frontend/src/pages/SignalsDashboard.tsx`)
  - 2분마다 백그라운드 폴링으로 신규 BUY 신호 감지
  - 토스트 알럿 (화면 우상단 고정, 8초 자동 닫힘)
  - 브라우저 Notification API 연동 (권한 허용 시 OS 알림)
  - 알럿 클릭 시 매매신호 탭으로 이동 + 해당 신호 카드 스크롤

#### 프론트엔드
- ✅ **StocksDashboard 런타임 오류 수정** (`frontend/src/pages/StocksDashboard.tsx`)
  - `Cannot read properties of undefined (reading 'toFixed')` 오류
  - 펀더멘털 null 체크: `per`, `pbr`, `roe`, `eps`, `bps`
  - 기술적 지표 null 체크: `rsi`, `volatility`, `return_60d`

- ✅ **매매신호 탭 카드 UI 개선** (`frontend/src/pages/SignalsDashboard.tsx`)
  - 종목 헤더: `종목명(종목코드)` 형식으로 표시
  - 주가 표시: `[주가 : ###원]` - 별도 줄, bold + text-2xl 폰트
  - `EntrySignal` 인터페이스에 `stock_info` 필드 추가 (`api.ts`)

- ✅ **가격 조건 통화 분리** (`frontend/src/App.tsx`)
  - 한국장: `1,000원 미만` + 입력란 원(₩) 단위
  - 미국장: `$1 미만` + 입력란 달러($) 단위
  - 시장 전환 시 가격 필터 자동 초기화

### v2.1.0 (2026-03-02)
- ✅ RSI 골든크로스 전략 추가
- ✅ Finviz 스크리너 통합 (47개 → 500개+)
- ✅ 섹터 모니터링 시스템 (10개 섹터, 74개 종목)
- ✅ 페니스탁 거래량 패턴 필터
- ✅ 시스템 전체 구조 문서화

### v2.0.0 (2026-03-01)
- 초기 출시
- 4대 진입 전략 (거래량, 기술적, 패턴, 복합)
- 3대 청산 전략 (익절, 손절, 시간)
- KR/US 양시장 지원

---

**문서 최종 수정일**: 2026년 3월 4일
**버전**: 2.3.0
**작성자**: Claude Code (Anthropic)
