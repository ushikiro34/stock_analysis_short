# 매매 전략 시스템 변경 이력 (2026-03-08)

## 개요

페이퍼 트레이딩 및 백테스팅 엔진에 분할 익절/손절, Break-even 보호, 진입 조건 강화를 적용한 4단계 전략 고도화.

---

## 전략 진화 요약

| 전략 | 익절 | 손절 | 특징 |
|------|------|------|------|
| **A (구)** | +3% 전량 | -2% 전량 | 기존 단순 전략 |
| **B (분할TP)** | +3%(1/3) → +7%(1/2) → +15%(전량) | -2% 전량 | 분할 익절 도입 |
| **C (B+본전손절)** | 분할 | 1차 TP 후 → 진입가 손절 | Break-even 보호 추가 |
| **D (C+분할SL)** | 분할 | Phase A: -1%(1/3) → -2%(전량) / Phase B: 본전 | 분할 손절 추가 |

---

## 핵심 로직: Phase A/B 이중 손절 구조

```
진입
 │
 ├─ [Phase A: 1차 TP 미발동 구간]
 │    ├─ -1% 도달 → 보유량의 1/3 부분 손절
 │    └─ -2% 도달 → 잔량 전량 손절
 │
 ├─ 1차 TP (+3%) 발동 → dynamic_stop = entry_price (본전)
 │    breakeven_active = True
 │
 └─ [Phase B: 1차 TP 발동 이후]
      └─ 현재가 ≤ 진입가 → 전량 손절(본전)
```

---

## 변경된 파일

### 1. `backend/core/paper_engine.py`

#### PaperConfig 추가 항목
```python
stop_loss_targets: List[dict] = field(default_factory=lambda: [
    {"ratio": -0.01, "volume_pct": 0.33, "name": "1차 손절 -1%"},
    {"ratio": -0.02, "volume_pct": 1.00, "name": "2차 손절 -2%"},
])
entry_min_change_rate: float = 3.0   # 진입 최소 상승률(%)
entry_max_change_rate: float = 15.0  # 진입 최대 상승률(%)
entry_min_volume: int = 100_000      # 최소 거래량
```

#### PaperPosition 추가 항목
```python
executed_sl_targets: set = field(default_factory=set)  # 실행된 분할 손절 인덱스
dynamic_stop_price: float = 0.0                        # 현재 손절가
breakeven_active: bool = False                         # Phase B 전환 여부
```

#### 신규 메서드: `_passes_entry_filter()`
- `change_rate`: 3%~15% 범위 확인
- `volume`: 100,000주 이상 확인
- 조건 미충족 시 진입 스킵

#### `_check_exit()` Phase A/B 분기
- Phase B (`breakeven_active=True`): 현재가 ≤ `dynamic_stop_price` → 전량 청산
- Phase A: `stop_loss_targets`를 순서대로 체크, 부분 청산

#### `_do_close()` TP/SL 구분
- 청산 사유가 TP 목표명과 일치할 때만 `dynamic_stop_price`를 진입가로 상향
- SL 부분 청산은 break-even 이동하지 않음

---

### 2. `backend/backtest/engine.py`

#### BacktestConfig 추가 항목
```python
stop_loss_targets: list = field(default_factory=lambda: [
    {"ratio": -0.01, "volume_pct": 0.33, "name": "1차 손절 -1%"},
    {"ratio": -0.02, "volume_pct": 1.00, "name": "2차 손절 -2%"},
])
```

#### Trade 추가 필드
```python
executed_sl_targets: set = field(default_factory=set)
breakeven_active: bool = False
```

#### `check_exit_conditions()` 동일한 Phase A/B 로직 적용

#### `close_position()` TP/SL 구분 동일 적용

---

### 3. `backend/compare_strategies.py` (신규 작성)

A/B/C/D 4개 전략을 동일 분봉 데이터로 비교하는 분석 도구.

#### 사용법
```bash
# DB 기반 (오늘 체결된 페이퍼 거래 비교)
python -m backend.compare_strategies

# 특정 종목 직접 테스트
python -m backend.compare_strategies --code 043200
python -m backend.compare_strategies --code 043200 --price 1045
```

#### 출력 예시
```
[043200] 종목명  진입: 1,045원
   A(구 +3%전량)  : -2.97%  손절 -2%@1,014(-2.97%) 09:15
   B(분할TP)      : -2.97%  손절 -2%@1,014(-2.97%) 09:15
   C(B+본전손절)  : -2.97%  손절 -2%@1,014(-2.97%) 09:15
   D(C+분할SL)    : -1.67%  1차손절@1,035(-0.96%) 2차손절@1,014(-2.97%)
   => 승자: D (-1.67%)
```

#### `simulate()` 함수 파라미터
| 파라미터 | 설명 |
|---------|------|
| `entry_price` | 진입가 |
| `candles` | 분봉 리스트 |
| `targets` | 익절 목표 리스트 |
| `use_breakeven` | True → 1차 TP 후 본전 손절 |
| `use_split_sl` | True → Phase A 분할 손절 적용 |

---

### 4. `backend/kis/rest_client.py`

#### 신규 메서드: `get_full_day_minute_chart()`
```python
async def get_full_day_minute_chart(self, code: str, since_hour: str = "090000") -> list:
```
- 기존 `get_minute_chart()`은 최근 30개 캔들만 반환
- 이 메서드는 최대 10회 페이지네이션으로 장 시작부터 전체 분봉 수집
- `since_hour` 이후의 캔들만 필터링하여 반환

---

## 전략 파라미터 요약

### 익절 목표 (NEW_TARGETS)
| 단계 | 목표 수익률 | 매도 비율 |
|------|------------|---------|
| 1차 | +3% | 1/3 |
| 2차 | +7% | 1/2 (잔량 대비) |
| 3차 | +15% | 전량 |

### 손절 목표 (SL_TARGETS)
| 단계 | 기준 손실률 | 매도 비율 |
|------|-----------|---------|
| 1차 (Phase A) | -1% | 1/3 |
| 2차 (Phase A) | -2% | 전량 |
| Phase B | 진입가(본전) | 전량 |

### 진입 필터
| 조건 | 값 |
|------|---|
| 최소 당일 상승률 | 3% |
| 최대 당일 상승률 | 15% |
| 최소 거래량 | 100,000주 |

---

## 기대 효과

| 개선 항목 | 이전 | 이후 |
|---------|------|------|
| 급등 후 즉시 하락 시 손실 | 전량 -2% | 분할 -0.96% ~ -2% (평균 약 -1.5%) |
| 급등 후 추가 상승 시 이익 보호 | 1차 TP 수익 반납 가능 | 1차 TP 후 본전 손절로 최소 0% 보장 |
| 과열 종목 진입 | 필터 없음 | +15% 초과 종목 진입 차단 |
| 거래량 미확인 진입 | 필터 없음 | 100,000주 미만 종목 제외 |

---

## 주의사항

- **Phase A → B 전환**: 1차 TP(+3%) 부분 청산이 실행되어야만 전환됨. SL 부분 청산은 전환 조건 아님.
- **트레일링 스톱**: 최고가 대비 -5% (변경 없음). Phase A/B와 별개로 동작하며 Phase B에서는 비활성.
- **분할 손절은 Phase A에서만**: `breakeven_active=True`가 되면 분할 손절 로직 비활성, 본전 단일 손절로 대체.
- **KIS API 시간 제약**: 장 마감 후 토큰 갱신 불가로 `compare_strategies` 테스트는 장중에만 가능.
