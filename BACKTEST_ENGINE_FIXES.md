# 백테스트 엔진 버그 수정 이력 (2026-03-10)

## 개요

백테스트 엔진(`backend/backtest/engine.py`)의 두 가지 주요 버그를 수정.
- **버그 1**: 전략별 데이터 윈도우 고정 (`tail(120)`) → RSI 전략 무력화
- **버그 2**: 분할 청산 시 승률(`win_rate`) 100% 초과 오류 및 손익 합산 누락

---

## 버그 1: `tail(120)` 하드코딩

### 위치
`engine.py` 신규 진입 체크 루프 (구 line 535)

### 원인
```python
# 수정 전: 전략 무관 120개 행 고정
historical_data = ohlcv_data.iloc[:i+1].tail(120)
```

RSI 관련 전략들은 MA200 계산 등으로 120행보다 훨씬 많은 데이터가 필요하여
항상 "데이터 부족" 신호를 반환하고 거래가 0건으로 집계됨.

| 전략 | 최소 필요 bars | 기존 window | 결과 |
|------|--------------|------------|------|
| combined / volume / technical | ~120 | 120 | 정상 |
| rsi_golden_cross | MA200 + RSI버퍼 ≈ 250 | 120 | **0건** |
| weekly_rsi_swing | MA200 + 주봉RSI(14주) ≈ 310+ | 120 | **0건** |

### 수정 내용
```python
# 수정 후: 전략별 필요 데이터 기간 동적 설정
_strategy_window = {
    'rsi_golden_cross': 250,
    'weekly_rsi_swing': 350,
}
data_window = _strategy_window.get(config.entry_strategy, 120)
historical_data = ohlcv_data.iloc[:i+1].tail(data_window)
```

---

## 버그 2: 승률 계산 오류 및 손익 누락

### 위치
`Backtester.close_position()` + `Trade.close()` + `Trade` 클래스

### 원인 (복합 버그)

#### 2-A: `winning_trades` 과다 집계
분할 청산(TP/SL)이 실행될 때마다 `self.winning_trades += 1`이 호출되어
포지션 1개 진입에 대해 2~4건이 집계됨.

```python
# 수정 전: 부분 청산 시에도 무조건 winning_trades 증가
else:  # 부분 청산
    trade.quantity -= close_qty
    ...
    self.winning_trades += 1  # ← 버그: 부분 청산마다 카운트
```

결과: `winning_trades / total_trades * 100` → 187.5%, 200% 등 비정상 값

#### 2-B: 분할 청산 손익 미합산
`Trade.close()`에서 손익 계산이 최종 청산 수량(`self.quantity`)만 고려.
1차 TP에서 팔린 수량의 이익이 최종 `profit_loss`에서 누락됨.

```python
# 수정 전: 잔여 수량 기준만 계산
self.profit_loss = (exit_price - self.entry_price) * self.quantity
self.profit_loss_pct = ((exit_price - self.entry_price) / self.entry_price) * 100
```

예시: 300주 진입 → 1차 TP(100주 매도 +3%) → 최종 청산(200주 -1%)
- **수정 전**: `profit_loss = (exit_price - entry) * 200` (1차 TP 수익 무시)
- **수정 후**: `profit_loss = 1차TP_실현손익 + (exit_price - entry) * 200`

### 수정 내용

#### Trade 클래스: `partial_profit_loss` 필드 추가
```python
partial_profit_loss: float = 0.0  # 부분 청산에서 실현된 누적 손익
```

#### Trade.close(): 총 손익 계산 수정
```python
def close(self, exit_time, exit_price, exit_reason):
    ...
    # 총 손익 = 부분 청산 누적 손익 + 최종 청산 손익
    final_pl = (exit_price - self.entry_price) * self.quantity
    self.profit_loss = self.partial_profit_loss + final_pl
    # 수익률 = 총 손익 / 최초 진입 비용 (original_quantity 기준)
    total_cost = self.entry_price * self.original_quantity
    self.profit_loss_pct = (self.profit_loss / total_cost * 100) if total_cost > 0 else 0
```

#### close_position(): 부분 청산 처리 수정
```python
if is_full:
    trade.close(exit_time, exit_price, exit_reason)
    self.open_positions.remove(trade)
    # 총 손익 기준으로 승/패 판정 (부분청산 포함)
    if trade.profit_loss > 0:
        self.winning_trades += 1
    else:
        self.losing_trades += 1
else:
    # 부분 청산 실현 손익 누적
    trade.partial_profit_loss += (exit_price - trade.entry_price) * close_qty
    trade.quantity -= close_qty
    ...
    # win/loss 카운트 없음 (포지션 단위로만 집계)
```

---

## 수정 전후 비교 (010170, 730일 백테스트)

### 수정 전
| 전략 | ROI | 거래수 | 승률 | 비고 |
|------|-----|--------|------|------|
| combined | 9.58% | 24 | **187.5%** | 승률 비정상 |
| rsi_golden_cross | - | **0** | - | 데이터 부족으로 미발동 |
| weekly_rsi_swing | - | **0** | - | 데이터 부족으로 미발동 |

### 수정 후
| 전략 | ROI | 거래수 | 승/패 | 승률 | 최대낙폭 | PF |
|------|-----|--------|-------|------|---------|-----|
| combined | 9.58% | 24 | 12/12 | **50.0%** | 10.04% | 1.68 |
| rsi_golden_cross | 90.60% | 113 | 52/61 | **46.0%** | 17.48% | 2.03 |
| weekly_rsi_swing | 9.23% | 5 | 3/2 | **60.0%** | 2.22% | 5.42 |

---

## 종목 010170 전략별 분석 결과

백테스트 기간: 2024-03-07 ~ 2026-03-07 (730일), 초기 자본 100만원

### 종합전략 (combined)
- **특성**: 중간 빈도(24회), 균형형 리스크
- **진입 구간**: 2024년 초반 ~ 2026년 2월 분산
- **특이사항**: 2026년 2월 급등 2건(+13%, +20%)이 전체 수익 견인
- **평가**: 검증된 안정형. 손익비 1.68로 소폭 우위

### RSI 골든크로스 (rsi_golden_cross)
- **특성**: 고빈도(113회), 고수익/고위험
- **진입 구간**: 2025년 7월부터 활성화 (250일 데이터 확보 시점)
- **특이사항**:
  - 2025년 9~12월 급등 구간에서 +18~+29% 대형 수익 다수
  - 하락 전환 시 연속 손절 (2025.11월 10건 연속 손절)
  - 실전 적용 시 수수료/슬리피지로 ROI 상당 감소 예상
- **평가**: 백테스트 ROI 90.6%이나 과매매(113회) 우려. 손익비 2.03

### 주봉 RSI 스윙 (weekly_rsi_swing) ← 신규 전략
- **특성**: 초저빈도(5회), 보수형
- **진입 구간**: 2025년 4~6월 (주봉 RSI 30 돌파 구간) 집중
- **진입 근거**: 2024년 가을 이후 주봉 RSI가 30 이하로 내려간 뒤 반등 신호
- **특이사항**:
  - 최대낙폭 2.22%로 세 전략 중 최저 리스크
  - 손익비(PF) 5.42 — 이길 때 크게, 질 때 작게
  - 2025년 하반기 급등(700원→4,700원) 구간은 미참여 (이미 RSI 과매수)
- **평가**: 저빈도이나 리스크 대비 수익률 최우수. 손익비 5.42

### 결론
- **안정 우선**: 주봉 RSI 스윙 (낙폭 2.22%, PF 5.42)
- **수익 우선**: RSI 골든크로스 (ROI 90.6%, 단 고빈도/고리스크)
- **기본값 유지**: 종합전략 (균형형, 검증된 다종목 대응력)

---

## 관련 파일

- `backend/backtest/engine.py` — 수정된 메인 파일
- `backend/core/signals.py` — WeeklyRSISwingSignal 추가 (별도 작업)
- `backend/core/signal_service.py` — 전략별 days 분기 (별도 작업)
