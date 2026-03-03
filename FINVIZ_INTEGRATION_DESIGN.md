# Finviz Integration Design Document

## 📋 개요

Yahoo Finance 스크리너의 한계(최대 47개)를 극복하기 위해 Finviz 스크리너를 통합하여 200+ 종목 발굴 능력을 확보합니다.

**작성일**: 2026-03-02
**목표**: BNAI, BATL 같은 고수익 종목을 자동으로 발견할 수 있는 강력한 스크리닝 시스템 구축

---

## 🎯 목표

### 1. 문제점
- ❌ Yahoo Finance: day_gainers(25) + most_actives(25) = 최대 47개
- ❌ BNAI (+1015%), BATL (+380%) 같은 종목 누락
- ❌ 페니스탁, 소형주 발견 어려움

### 2. 해결책
- ✅ Finviz 스크리너: 60+ 필터, 8000+ 종목
- ✅ 다양한 스크리닝 전략 (가격, 거래량, 패턴, 기술적 지표)
- ✅ Python 라이브러리 지원 (`finvizfinance`)

---

## 🏗️ 아키텍처 설계

### 1. 모듈 구조

```
backend/
├── us/
│   ├── yfinance_client.py          # 기존: Yahoo Finance (유지)
│   ├── finviz_screener.py          # 신규: Finviz 스크리너 ⭐
│   └── __init__.py
│
├── api/routers/
│   ├── stocks.py                   # 업데이트: Finviz 엔드포인트 추가
│   └── screener.py                 # 신규: 스크리너 전용 라우터 (선택)
│
└── core/
    └── screener_aggregator.py      # 신규: 여러 스크리너 통합 (선택)
```

---

## 📦 Dependencies

### 설치 필요
```bash
pip install finvizfinance
# 또는
pip install finviz
```

### 버전 정보
- `finvizfinance`: v1.3.0 (2026-01-03 최신)
- Python: >= 3.9

---

## 🔧 구현 상세 설계

### 1. Core Module: `finviz_screener.py`

#### 1.1 기본 스크리너 함수
```python
async def get_finviz_surge_stocks(
    limit: int = 100,
    strategy: str = "gainers"
) -> list[dict]:
    """
    Finviz 스크리너로 급등주 발굴

    Args:
        limit: 반환할 최대 종목 수 (10-500)
        strategy: 스크리닝 전략
            - "gainers": 가격 급등주
            - "breakout": 신고가 돌파
            - "volume": 거래량 급증
            - "momentum": 모멘텀 종목
            - "penny": 페니스탁 (<$1)

    Returns:
        [
            {
                "code": "AAPL",
                "name": "Apple Inc.",
                "price": 150.25,
                "change": 3.45,
                "change_pct": 2.35,
                "volume": 75000000,
                "market_cap": 2.5T,
                "sector": "Technology",
                "industry": "Consumer Electronics"
            },
            ...
        ]
    """
```

#### 1.2 스크리닝 전략별 필터

**A. Gainers (가격 급등주)**
```python
filters = {
    'Change': 'Up',                    # 상승 종목만
    'Volume': 'Over 500K',             # 거래량 50만 이상
    'Price': 'Over $0.1',              # 극단적 페니스탁 제외
    'Market Cap.': '+Small (over $300mln)'  # 시가총액 3억 이상
}
```

**B. Breakout (신고가 돌파)**
```python
filters = {
    'Technical': 'Horizontal S/R',     # 저항선 돌파
    'Change': 'Up',
    'Price': 'Over $1',
    'Volume': 'Over 1M',
    '20-Day Simple Moving Average': 'Price above SMA20'
}
```

**C. Volume Surge (거래량 급증)**
```python
filters = {
    'Relative Volume': 'Over 2',       # 평균 대비 2배 이상
    'Volume': 'Over 1M',
    'Average Volume': 'Over 500K',
    'Change': 'Up'
}
```

**D. Momentum (모멘텀 종목)**
```python
filters = {
    'Performance': 'Week Up',          # 주간 상승
    'RSI (14)': 'Overbought (60)',    # RSI 60 이상
    'Volume': 'Over 500K',
    '20-Day Simple Moving Average': 'Price above SMA20'
}
```

**E. Penny Stocks (페니스탁)**
```python
filters = {
    'Price': 'Under $1',
    'Volume': 'Over 1M',
    'Change': 'Up 5%',                # 5% 이상 상승
    'Relative Volume': 'Over 1.5'     # 거래량 1.5배 이상
}
```

#### 1.3 데이터 변환 함수
```python
def _convert_to_standard_format(finviz_data: pd.DataFrame) -> list[dict]:
    """
    Finviz DataFrame을 시스템 표준 포맷으로 변환

    Finviz 컬럼 -> 시스템 컬럼 매핑:
    - Ticker -> code
    - Company -> name
    - Price -> price
    - Change -> change_pct
    - Volume -> volume
    - Market Cap -> market_cap
    - Sector -> sector
    - Industry -> industry
    """
```

---

### 2. API Router: `stocks.py` 업데이트

#### 2.1 새 엔드포인트 추가
```python
@router.get("/surge/finviz", response_model=List[SurgeStockResponse])
async def get_finviz_surge_stocks(
    strategy: str = "gainers",
    limit: int = 100,
    min_volume: int = 500000,
    min_price: float = 0.1,
    max_price: Optional[float] = None
):
    """
    Finviz 스크리너로 급등주 발굴

    Args:
        strategy: 스크리닝 전략 (gainers, breakout, volume, momentum, penny)
        limit: 최대 종목 수 (10-500)
        min_volume: 최소 거래량
        min_price: 최소 주가
        max_price: 최대 주가 (페니스탁용)

    Returns:
        급등주 목록 (최대 500개)
    """
```

#### 2.2 통합 엔드포인트 (선택사항)
```python
@router.get("/surge/all", response_model=List[SurgeStockResponse])
async def get_all_surge_stocks(
    limit: int = 100,
    sources: List[str] = ["yfinance", "finviz"]
):
    """
    여러 스크리너 통합 결과

    - Yahoo Finance: day_gainers + most_actives (~47개)
    - Finviz: gainers + volume (~200개)

    중복 제거 후 change_rate 높은 순 정렬
    """
```

---

### 3. 캐싱 전략

#### 3.1 캐시 구조
```python
_finviz_cache = {
    "gainers": {"data": [], "ts": 0},
    "breakout": {"data": [], "ts": 0},
    "volume": {"data": [], "ts": 0},
    "momentum": {"data": [], "ts": 0},
    "penny": {"data": [], "ts": 0}
}
```

#### 3.2 캐시 만료 시간
- **Gainers/Volume**: 60초 (빠른 변화)
- **Breakout/Momentum**: 300초 (5분)
- **Penny**: 300초 (5분)

---

## 📊 데이터 포맷 표준화

### 공통 응답 포맷
```python
{
    "code": str,              # 티커 심볼
    "name": str,              # 회사명
    "price": float,           # 현재가
    "change_price": float,    # 변동 금액
    "change_rate": float,     # 변동률 (%)
    "volume": int,            # 거래량
    "market_cap": str,        # 시가총액 (optional)
    "sector": str,            # 섹터 (optional)
    "industry": str,          # 산업 (optional)
    "source": str             # 데이터 출처 ("finviz" or "yfinance")
}
```

---

## 🧪 테스트 계획

### 1. 단위 테스트
```python
# test_finviz_screener.py

async def test_get_gainers():
    """가격 급등주 스크리닝 테스트"""
    results = await get_finviz_surge_stocks(limit=50, strategy="gainers")
    assert len(results) > 0
    assert len(results) <= 50
    assert all(r["change_rate"] > 0 for r in results)

async def test_get_penny_stocks():
    """페니스탁 스크리닝 테스트"""
    results = await get_finviz_surge_stocks(limit=50, strategy="penny")
    assert all(r["price"] < 1.0 for r in results)
    assert all(r["volume"] > 1000000 for r in results)

async def test_data_format():
    """데이터 포맷 검증"""
    results = await get_finviz_surge_stocks(limit=10)
    required_fields = ["code", "name", "price", "change_rate", "volume"]
    assert all(all(f in r for f in required_fields) for r in results)
```

### 2. 통합 테스트
```bash
# API 엔드포인트 테스트
curl "http://localhost:8000/stocks/surge/finviz?strategy=gainers&limit=100"
curl "http://localhost:8000/stocks/surge/finviz?strategy=penny&limit=50"
curl "http://localhost:8000/stocks/surge/all?limit=100"
```

### 3. 성능 테스트
- **응답 시간**: < 3초 (첫 요청), < 0.1초 (캐시)
- **데이터 품질**: change_rate 정확도, 중복 제거
- **종목 수**: 100개 이상 확보 가능 여부

---

## ⚠️ 주의사항 및 제약

### 1. Terms of Service
- Finviz 무료 버전은 스크래핑 제한 가능
- 너무 빈번한 요청 시 IP 차단 위험
- **권장**: 캐싱 + Rate Limiting 적용

### 2. 데이터 지연
- 무료 Finviz: 15-20분 지연
- Elite 버전($24.96/월): 실시간

### 3. Rate Limiting 구현
```python
from time import time
from collections import deque

# 분당 최대 10회 요청
_request_times = deque(maxlen=10)

def check_rate_limit():
    now = time()
    if len(_request_times) == 10:
        if now - _request_times[0] < 60:
            raise Exception("Rate limit exceeded")
    _request_times.append(now)
```

---

## 🚀 구현 우선순위

### Phase 1: 기본 구현 (1-2시간)
- [x] TODO 리스트 작성
- [ ] `finviz_screener.py` 생성
- [ ] `get_finviz_surge_stocks()` 구현 (gainers 전략만)
- [ ] API 엔드포인트 추가
- [ ] 기본 테스트

### Phase 2: 전략 확장 (1시간)
- [ ] 5가지 스크리닝 전략 구현
- [ ] 캐싱 시스템 적용
- [ ] Rate Limiting 적용

### Phase 3: 통합 및 최적화 (1시간)
- [ ] Yahoo Finance + Finviz 통합 엔드포인트
- [ ] 중복 제거 로직
- [ ] 성능 최적화
- [ ] 문서 업데이트

---

## 📈 기대 효과

### 1. 종목 발굴 능력
- **Before**: Yahoo Finance 47개
- **After**: Finviz 200-500개
- **증가율**: 400-1000% 향상

### 2. 발견 가능한 종목 예시
- BNAI (+1015%): ✅ Finviz "gainers" 전략으로 포착
- BATL (+380%): ✅ Finviz "volume" 전략으로 포착
- 페니스탁: ✅ 전용 "penny" 전략

### 3. 시스템 가치 향상
- 더 많은 매매 기회 발굴
- 섹터별 스크리닝 가능
- 기술적 패턴 필터링

---

## 📚 참고 자료

### Python 라이브러리
- **finvizfinance**: https://github.com/lit26/finvizfinance
- **finviz**: https://github.com/mariostoev/finviz

### Finviz 필터 가이드
- Screener 필터: https://finviz.com/screener.ashx
- Elite Features: https://finviz.com/elite

### API 문서
- finvizfinance docs: https://finvizfinance.readthedocs.io/

---

## 🔄 향후 확장 계획

### 1. 추가 스크리닝 전략
- Gap Up/Down (갭 상승/하락)
- MACD 골든크로스
- 볼린저 밴드 돌파
- Cup & Handle 패턴

### 2. 다중 소스 통합
- Yahoo Finance (무료, 47개)
- Finviz (무료, 200-500개)
- Whale Wisdom (기관 투자자 추적)
- SEC EDGAR (공시 기반)

### 3. AI/ML 통합
- 스크리닝 결과를 학습 데이터로 활용
- 고수익 종목 패턴 학습
- 자동 전략 최적화

---

**작성자**: Stock Analysis System
**버전**: 1.0
**상태**: 설계 완료, 구현 대기
