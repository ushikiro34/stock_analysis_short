# 매매 전략 시스템 변경 이력 (최종 업데이트: 2026-03-11)

## 개요

페이퍼 트레이딩 및 백테스팅 엔진에 분할 익절/손절, Break-even 보호, 진입 조건 강화를 적용한 4단계 전략 고도화.

---

## 전략 진화 요약

| 전략 | 익절 | 손절 | 트레일 | 보유 | 특징 |
|------|------|------|--------|------|------|
| **A (구)** | +3% 전량 | -2% 전량 | -5% | - | 기존 단순 전략 |
| **B (분할TP)** | +3%(1/3)→+7%(1/2)→+15%(전량) | -2% 전량 | -5% | - | 분할 익절 도입 |
| **C (B+본전손절)** | 분할 | 1차 TP 후 → 진입가 손절 | -5% | - | Break-even 보호 추가 |
| **D (C+분할SL)** | +3%(1/3)→+7%(1/2)→+15%(전량) | -1%(1/3)→-2%(전량) / Phase B: 본전 | -5% | 10일 | 분할 손절 추가 |
| **G (보수형)** ✅ **현재** | +2%(1/3)→+5%(1/2)→+10%(전량) | -1%(1/3)→-2%(전량) / Phase B: 본전 | **-4%** | **7일** | 빠른 확정·타이트 트레일 |

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

---

# 백테스트 엔진 버그 수정 (2026-03-10)

> 상세 내용: `BACKTEST_ENGINE_FIXES.md`

## 수정 내용

### 1. `backend/backtest/engine.py` — 전략별 데이터 윈도우 동적 설정

신규 진입 체크 시 `tail(120)` 하드코딩으로 RSI 계열 전략이 항상 "데이터 부족" 반환하던 문제 수정.

```python
# 수정 전
historical_data = ohlcv_data.iloc[:i+1].tail(120)

# 수정 후
_strategy_window = {'rsi_golden_cross': 250, 'weekly_rsi_swing': 350}
data_window = _strategy_window.get(config.entry_strategy, 120)
historical_data = ohlcv_data.iloc[:i+1].tail(data_window)
```

### 2. `backend/backtest/engine.py` — 승률 계산 및 손익 합산 버그 수정

분할 청산(TP/SL)이 발생할 때마다 `winning_trades`가 중복 집계되어 승률이 100% 초과하던 버그 수정.
아울러 부분 청산 실현 손익이 최종 `profit_loss`에 누락되던 문제도 함께 수정.

| 수정 항목 | 수정 전 | 수정 후 |
|---------|--------|--------|
| `Trade.partial_profit_loss` 필드 | 없음 | 부분 청산 누적 손익 저장 |
| `Trade.close()` 손익 계산 | 잔여 수량만 계산 | 부분청산 누적 + 최종 청산 합산 |
| `close_position()` 승/패 집계 | 부분청산마다 `winning_trades += 1` | 포지션 완전 종료 시에만 집계 |

**수정 전후 승률 비교 (010170, 730일 백테스트)**

| 전략 | 수정 전 승률 | 수정 후 승률 | 수정 후 ROI | PF |
|------|------------|------------|------------|-----|
| combined | 187.5% ❌ | 50.0% ✅ | 9.58% | 1.68 |
| rsi_golden_cross | 미작동(0건) ❌ | 46.0% ✅ | 90.6% | 2.03 |
| weekly_rsi_swing | 미작동(0건) ❌ | 60.0% ✅ | 9.23% | 5.42 |

## 신규 전략: `weekly_rsi_swing`

주봉 RSI 30 돌파 후 일봉 MA50/200 골든크로스 확인 스윙 전략. `backend/core/signals.py`에 `WeeklyRSISwingSignal` 클래스로 구현.

| 항목 | 내용 |
|------|------|
| 최소 데이터 | 310일 (MA200 + 주봉RSI 버퍼) |
| 진입 조건 | 주봉 RSI가 30 이하에서 30 초과로 상승 |
| 확인 조건 | 일봉 MA50 > MA200 (골든크로스) → 점수 +35 추가 |
| 관련 파일 | `signals.py`, `signal_service.py` (days=350 분기) |

---

# 매도 전략 G(보수형) 기본값 적용 (2026-03-11)

## 배경

D(현재) / G(보수형) / H(하이브리드) 3전략을 중소형주 8종목 × 730일 백테스트로 비교 검증한 결과 G(보수형)이 ROI·MDD 복합 기준에서 우위.

## 검증 결과 요약

| 전략 | 평균ROI | 총거래 | 평균승률 | 평균MDD | 평균PF | 수익종목 |
|------|--------|--------|---------|--------|--------|---------|
| D (구 기본값) | +1.98% | 102 | 42.9% | 6.02% | 1.98 | 5/8 |
| **G (신 기본값)** | **+2.33%** | 102 | 41.6% | **5.68%** | 1.83 | 4/8 |
| H (하이브리드) | +1.90% | 102 | 42.4% | 5.93% | 1.82 | 5/8 |

## 변경된 기본값

| 파라미터 | D (구) | G (신) |
|---------|--------|--------|
| 1차 TP | +3% (1/3) | **+2% (1/3)** |
| 2차 TP | +7% (1/2) | **+5% (1/2)** |
| 3차 TP | +15% (전량) | **+10% (전량)** |
| 손절 | -1%(1/3) / -2%(전량) | 동일 유지 |
| 트레일링 스톱 | -5% | **-4%** |
| 최대 보유 | 10일 | **7일** |

## 변경된 파일

- `backend/backtest/engine.py` — `BacktestConfig` 기본값
- `backend/core/paper_engine.py` — `PaperConfig` 기본값

## G 전략의 핵심 원리

```
1차 TP +2%(빠른 확정) → breakeven 즉시 전환
  └→ 이후 손실 리스크 제거 + trail -4% 타이트 보호
     └→ 추가 상승 시 +5%/+10% 대기, 하락 시 본전 청산
```

D 대비 1차 TP가 낮아 breakeven 전환 빈도가 높아지고, 트레일링이 타이트해 이익 보호 시점이 빨라짐. 대신 대형 추세형 종목(한미반도체·알테오젠)에서는 D가 소폭 우위.

---

# M+ 전략 신규 추가 (2026-03-11)

## 개요

다중 타임프레임 모멘텀 전략(M+)을 일봉 데이터 근사로 구현하여 신규 전략으로 추가.

## M+ 전략 구조

```
1단계 (관심): 일봉 RSI 30 상향 돌파 → 과매도 탈출 신호
2단계 (진입): MA20 > MA60 골든크로스 + MACD histogram > 0 → 상승 강도 확인
3단계 (보조): 전일 고가 갱신 → 15분봉 전고점 돌파 근사
```

## 기존 RSI GC 전략 대비 차이

| 항목 | rsi_golden_cross | multi_tf_momentum_plus (M+) |
|------|---------|-------|
| MA 기준 | MA50 / MA200 (장기) | MA20 / MA60 (단기) |
| MACD 조건 | 없음 | **histogram > 0 (필수)** |
| 진입 빈도 | 높음 | 낮음 (~50% 감소) |
| 핵심 차별점 | - | MACD 오실레이터 양전 필터 |

## 백테스트 검증 결과 (3종목 × 730일, G 전략 매도)

| 종목 | RSI GC 건수 | RSI GC ROI | RSI GC PF | RSI GC MDD | M+ 건수 | M+ ROI | M+ PF | M+ MDD | 우위 |
|------|------------|-----------|----------|-----------|--------|-------|------|--------|------|
| 010170 | 108 | +42.76% | 1.85 | 9.20% | 52 | +3.45% | 1.18 | 15.66% | RSI GC |
| 043200 | 75 | +10.29% | 1.34 | 17.16% | 31 | +33.75% | 2.34 | 14.66% | M+ |
| 900140 | 40 | -5.21% | 0.61 | 7.86% | 20 | -2.19% | 0.74 | 3.11% | M+ |
| **평균** | 74건 | **+15.95%** | — | 11.41% | 34건 | **+11.67%** | — | **11.14%** | RSI GC |

## 결론

- **평균 ROI**: RSI GC 우위 (+15.95% vs +11.67%)
- **리스크 관리**: M+가 우위 — 손실 종목에서 MDD 절반 수준 (900140: 7.86%→3.11%)
- **선별성**: M+가 MACD 필터로 거래 수 ~50% 감소, 더 선별적 진입
- **상승 강한 종목**: M+ 우위 (043200 ROI +33.75% vs RSI GC +10.29%)
- **고빈도 상승 종목**: RSI GC 우위 (010170 ROI +42.76% vs M+ +3.45%)

### 전략 선택 가이드

| 상황 | 추천 전략 |
|------|---------|
| 장기 골든크로스 종목, 고빈도 매매 선호 | rsi_golden_cross |
| 리스크 최소화, 선별적 진입 선호 | multi_tf_momentum_plus (M+) |
| 상승 강도 확인 후 진입 원할 때 | multi_tf_momentum_plus (M+) |

## 추가된 파일

- `backend/core/signals.py` — `MultiTFMomentumPlusSignal` 클래스 추가
- `backend/core/signal_service.py` — M+ 전략 days=150 분기 추가
- `backend/backtest/engine.py` — `_strategy_window['multi_tf_momentum_plus'] = 150` 추가

---

# 진입 신호 강화: Case1+2 추격 차단 필터 + 포지션 보수화 (2026-03-11)

## 배경

모의 투자 결과 분석에서 083640 종목이 당일 +9.46% 급등 시 volume 신호(100점)가 combined에 그대로 반영되어 추격 매수 진입 후 손실이 발생. 이를 방지하기 위해 두 가지 진입 필터를 도입하고, 동시 보유 종목 수와 포지션 비율을 축소.

## Case 1: 당일 급등 추격 차단 게이트

`VolumeBreakoutSignal.check_signal()` 에 추가.

```python
price_change_pct = (current_price - prev_close) / prev_close * 100
chase_blocked = price_change_pct >= 5.0

if chase_blocked:
    signal = SignalType.HOLD  # 점수와 무관하게 차단
    chase_blocked = True
```

- 당일 가격 상승률 **≥ 5%** 이면 거래량·기술 점수와 무관하게 volume 신호를 HOLD로 전환
- `chase_blocked` 플래그를 반환 dict에 포함

### combined 전략 전파

```python
# SignalManager.generate_entry_signal() — combined 분기
if volume_result.get("chase_blocked", False):
    return {"signal": HOLD, "score": 0, ...}  # 즉시 HOLD 반환
```

- volume 신호가 개별 HOLD를 반환해도 combined은 score 가중평균만 쓰는 버그 존재
- early-return 로직으로 combined 전체를 HOLD 처리

## Case 2: 전고점 가짜 돌파 감지 패널티

`VolumeBreakoutSignal.check_signal()` — 기존 score 계산 이후 적용.

```python
if len(ohlcv_data) >= 21:
    recent_window = ohlcv_data.iloc[-21:-1]          # 당일 제외 20일
    recent_high_val = recent_window["High"].max()
    if current_price > recent_high_val:              # 20일 고점 돌파
        high_day_volume = recent_window.loc[recent_window["High"].idxmax(), "Volume"]
        vol_vs_high = current_volume / high_day_volume
        if vol_vs_high < 0.8:
            score = max(0, score - 25)               # 가짜 돌파 패널티
        else:
            score = min(100, score + 10)             # 거래량 확인 돌파 보너스
```

- 20일 최고가(High) 돌파 시 해당 고점 날의 거래량과 비교
- 현재 거래량이 고점 날 거래량의 **80% 미만** → 가짜 돌파로 판정, -25점 패널티
- 80% 이상 → 거래량 확인 돌파, +10점 보너스

`PricePatternSignal.detect_consolidation_breakout()` 에도 적용:

```python
consolidation_avg_vol = consolidation["Volume"].mean()
if consolidation_avg_vol > 0 and current["Volume"] < consolidation_avg_vol:
    return False  # 횡보 돌파 거래량 미달 → 가짜 돌파
```

## 포지션 보수화: max_positions & position_size_pct 축소

### 배경

Case1+2 적용 후 백테스트(14종목 × 365일) 결과 단일 갭하락 거래(-5.34%)가 MDD를 9.16%까지 끌어올림. 포지션 사이즈 축소로 개별 거래 손실의 포트폴리오 영향을 완화.

### 설정 변경

| 파라미터 | 변경 전 | 변경 후 |
|---------|--------|--------|
| `max_positions` | 3 | **2** |
| `position_size_pct` | 0.30 (30%) | **0.15 (15%)** |
| 최대 자본 노출 | 90% | **30%** |

### 변경된 파일

- `backend/backtest/engine.py` — `BacktestConfig` 기본값
- `backend/core/paper_engine.py` — `PaperConfig` 기본값
- `backend/api/routers/paper_trading.py` — `StartConfig` 기본값

## 백테스트 검증 결과 (14종목 × 365일, combined + G전략 매도)

| 구분 | 총 거래 | ROI | MDD | PF | 승률 |
|------|--------|-----|-----|-----|------|
| 기존 (Case1+2 없음, max3/30%) | 108건 | +2.48% | 2.57% | 1.56 | — |
| Case1+2만 적용 (max3/30%) | 39건 | +4.78% | 9.16% | 1.43 | 51.3% |
| **최종 (Case1+2 + max2/15%)** | **34건** | **+2.80%** | **3.49%** | **1.54** | **52.9%** |

- **거래 수 69% 감소** (108 → 34): 추격 매수 및 가짜 돌파 진입 제거
- **ROI 소폭 개선** (+2.48% → +2.80%): 필터링으로 거래 품질 향상
- **MDD 원상 복귀 수준** (2.57% → 3.49%): 잔여 MDD는 갭하락 리스크(손절 범위 초과)
- **PF 유사 유지** (1.56 → 1.54)

## 주의사항

- **갭하락 리스크**: 스톱로스 -2% 설정에도 장 시작 시 갭으로 -5% 이상 손실 가능. 이는 position_size 축소로 영향을 줄이는 것이 현실적 대응.
- **Case 1 임계값 (5%)**: 한국 소형주 특성상 5%는 비교적 낮은 임계값. 83640의 +9.46%는 차단되나 5~8% 구간 거래는 여전히 허용됨.
- **Case 2 임계값 (80%)**: 20일 고점 당시 거래량의 80%를 기준으로 함. 시장 상황에 따라 조정 가능.
