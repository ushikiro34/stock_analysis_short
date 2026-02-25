# 1달러 미만 주식 필터링 API 가이드

## 개요

미국 주식 중 특정 거래량 패턴을 보이는 1달러 미만 주식을 필터링하는 기능입니다.

## 필터링 조건

### 주요 조건
1. **주가**: 1달러 미만 (< $1.00)
2. **당일 거래량 급증**: 전일 대비 2배 이상
3. **거래량 패턴**: 최근 2일(D-1, D-2)의 거래량이 그 이전(D-3)보다 작음

### 거래량 패턴 설명
```
D-3 (3일 전): 기준 거래량
D-2 (2일 전): D-3보다 작음 (하락)
D-1 (전일):   D-3보다 작음 (하락 지속)
D-0 (당일):   D-1 대비 2배 이상 급증
```

이 패턴은 거래량이 감소하다가 갑자기 급증하는 주식을 찾습니다.

## API 엔드포인트

### GET `/stocks/penny-stocks`

1달러 미만 주식 중 거래량 급증 종목 조회

#### 요청 예시
```bash
curl http://localhost:8000/stocks/penny-stocks
```

#### 응답 형식
```json
[
  {
    "code": "AAPL",
    "name": "Apple Inc.",
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

#### 응답 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `code` | string | 종목 코드 (티커) |
| `name` | string | 회사명 |
| `price` | number | 현재 주가 (달러) |
| `change_rate` | number | 변동률 (%) |
| `volume` | integer | 당일 거래량 |
| `change_price` | number | 변동 가격 (달러) |
| `volume_pattern` | object | 거래량 패턴 상세 정보 |
| `volume_pattern.d0` | integer | 당일 거래량 |
| `volume_pattern.d1` | integer | 전일 거래량 |
| `volume_pattern.d2` | integer | 2일 전 거래량 |
| `volume_pattern.d3` | integer | 3일 전 거래량 |
| `volume_pattern.surge_ratio` | number | 거래량 급증 배율 (d0/d1) |

#### 캐싱
- **캐시 시간**: 5분 (300초)
- 동일한 요청은 5분 동안 캐시된 데이터를 반환합니다.

#### 제한사항
- 최대 50개 종목 반환
- yfinance의 screener 데이터 사용 (day_gainers, most_actives)
- 미국 시장 휴장일에는 데이터가 없을 수 있습니다

## 백엔드 함수

### `get_penny_stocks_with_volume_pattern(limit: int = 50)`

위치: `backend/us/yfinance_client.py`

#### 파라미터
- `limit` (int, optional): 최대 반환 종목 수, 기본값: 50

#### 반환값
- `list[dict]`: 필터링된 주식 리스트 (거래량 급증 배율 높은 순으로 정렬)

#### 사용 예시
```python
from backend.us.yfinance_client import get_penny_stocks_with_volume_pattern

# 비동기 함수 호출
results = await get_penny_stocks_with_volume_pattern(limit=30)

for stock in results:
    print(f"{stock['code']}: ${stock['price']}, 급증 {stock['volume_pattern']['surge_ratio']}배")
```

## 테스트

### 테스트 스크립트 실행
```bash
python test_penny_stocks.py
```

### 예상 출력
```
============================================================
1달러 미만 미국 주식 필터링 테스트
============================================================

필터 조건:
  1. 주가 < $1
  2. 당일 거래량 >= 전일 거래량 x 2 (급증)
  3. D-2, D-1 거래량 < D-3 거래량

데이터 수집 중...

✅ 총 5개 종목 발견

----------------------------------------------------------------------------------------------------
종목코드     회사명                          가격($)    변동률(%)      당일거래량        급증배율
----------------------------------------------------------------------------------------------------
ABCD       Example Corp                 $0.75      +25.00%      10,000,000      3.50x
...
```

## 주의사항

1. **엄격한 필터**: 3가지 조건을 모두 만족해야 하므로 결과가 적을 수 있습니다.
2. **시장 시간**: 미국 주식 시장 개장 시간에만 실시간 데이터가 업데이트됩니다.
3. **데이터 소스**: yfinance의 screener 데이터를 사용하므로 모든 1달러 미만 주식을 검색하지 않고, 급등주와 거래량 상위 종목 중에서만 필터링합니다.
4. **API Rate Limit**: yfinance API 호출 제한이 있을 수 있으니 캐싱을 활용하세요.

## 향후 개선 사항

- [ ] 조건 커스터마이징 (쿼리 파라미터로 가격 범위, 급증 배율 설정)
- [ ] 더 넓은 범위의 주식 검색 (전체 미국 주식 스캔)
- [ ] 거래량 패턴 시각화
- [ ] 알림 기능 (조건 만족 시 알림)
- [ ] 백테스팅 데이터 제공
