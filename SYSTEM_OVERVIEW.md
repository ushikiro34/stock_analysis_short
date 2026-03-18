# 매매 전략 시스템 변경 이력 (최종 업데이트: 2026-03-15)

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

---

# 투자일지 AI 분석 기능 추가 (2026-03-12)

## 개요

투자일지(PaperTrade) 데이터를 기반으로 Groq AI(Llama-3.3-70b)가 7개 섹션으로 거래를 자동 분석하는 모달 기능 추가. SSE 스트리밍으로 실시간 출력.

---

## 아키텍처

```
사용자 (종목명 클릭)
  └→ GET /paper/journal/{trade_id}/analyze
        ├─ pykrx: OHLCV 최근 25거래일 조회
        ├─ Naver Finance: 매수일 ±3일 뉴스 크롤링 (최대 3개)
        ├─ 프롬프트 조립 (거래정보 + OHLCV + 뉴스링크)
        └─ Groq API 스트리밍 → SSE → 프론트 ReadableStream
```

---

## 추가된 파일 및 변경 내용

### `backend/api/routers/paper_trading.py`

#### 신규 엔드포인트: `GET /paper/journal/{trade_id}/analyze`
- OHLCV 조회, 뉴스 크롤링, 프롬프트 빌드, SSE 스트리밍을 단일 함수에서 처리
- `StreamingResponse(media_type="text/event-stream")` 반환

#### 뉴스 크롤링: `_fetch_naver_news(code, target_dt)`
```python
# Naver Finance: https://finance.naver.com/item/news_news.naver?code={code}
# 매수일 기준 -3일 ~ 당일 범위의 뉴스 최대 3개 반환
# 반환: [{"title": ..., "link": ..., "date": ...}, ...]
```
- 뉴스 있으면 → 실제 링크를 프롬프트에 주입 (AI 링크 할루시네이션 방지)
- 뉴스 없으면 → "검색되지 않음" 안내 후 일반 서술 요청

#### 다국어 혼용 필터: `_clean_foreign(text)`

Llama 모델의 다국어 코드 스위칭(code-switching) 현상을 사후 처리로 차단.

| 처리 단계 | 대상 | 예시 |
|---------|------|------|
| 1) CJK 제거 | 한자·히라가나·가타카나 | 漢字, あいう, アイウ |
| 2) 키릴 제거 | 러시아어 등 | лиценз |
| 3) 라틴 이형 제거 | 베트남어·유럽어 악센트 | tăng, café |
| 4) 마크다운 이탤릭 영문 제거 | `_word_` 패턴 | `_recently_` |
| 5) 영문 단어 제거 (허용 약어 보호) | 소문자·혼용 단어 | minimize, hedge |
| 6) 연속 공백 정리 | — | `기술력과  에 있으며` → `기술력과 에 있으며` |

**허용 약어 (30종)**: OHLCV, OHLC, ETF, PER, PBR, ROE, ROA, EPS, BPS, KOSPI, KOSDAQ, EV, EBITDA, IPO, GDP, CPI, PPI, FOMC, FED, ECB, BOK, KRW, USD, EUR, YOY, QOQ, MOM, RSI, MACD, MA, EMA, SMA, ATR, OBV, M&A

#### 줄 단위 스트리밍 버퍼
```python
# 청크 단위 필터 → 줄 단위 필터로 변경
# 이유: "OHLC" + "V" 청크 분리 시 \bOHLCV\b 매칭 실패 방지
line_buf = ""
async for chunk in stream:
    line_buf += chunk.content
    lines = line_buf.split("\n")
    line_buf = lines.pop()          # 미완성 마지막 줄 유지
    for line in lines:
        filtered = _clean_foreign(line)
        yield SSE(filtered + "\n")
# 스트림 종료 후 잔여 버퍼 처리
```

#### AI 프롬프트 구조 (7개 섹션)

| 섹션 | 내용 |
|------|------|
| 1. 종목 및 섹터 정보 | 사업 개요, 경쟁사, 수익 구조, 섹터 흐름 |
| 2. 종목 관련 뉴스 및 이슈 | 크롤링된 실제 뉴스 링크 + 이슈 정리 |
| 3. 차트 패턴 분석 | OHLCV 기반 캔들·추세·지지저항 |
| 4. 당일 종가 분석 | 시고저종 위치, 거래량, 마감 특성 |
| 5. 주가 종합 분석 | 기술적 + 수급 통합 분석 |
| 6. 익일 주가 흐름 예상 | 상승/하락/보합 시나리오별 목표가 |
| 7. 거래 분석 및 교훈 | 타이밍 평가, 잘된 점/아쉬운 점, 교훈 |

---

### `frontend/src/pages/InvestmentJournalDashboard.tsx`

#### AI 분석 모달 (`AnalysisModal` 컴포넌트)
- 92vw × 90vh 오버레이 모달
- 헤더: 종목명, 시장, 매수가→매도가, 손익 배지
- 본문: `parseAnalysisSections()` → `### N.` 패턴으로 분리 → 2열 그리드 카드
- 스트리밍 진행 중: `Loader2` 스피너 + "분석 중..." 표시
- 오류 시: 빨간색 에러 박스

#### 섹션 헤더 파싱 버그 수정
```typescript
// 수정 전: 숫자+점+첫단어 제거 → "🏭 및 섹터 정보" (첫 단어 누락)
title.replace(/^\d+\.\s*[^\s]+\s*/, '').trim()

// 수정 후: 숫자+점만 제거 → "🏭 종목 및 섹터 정보"
title.replace(/^\d+\.\s*/, '').trim()
```

---

## 의존성 추가

| 패키지 | 용도 |
|--------|------|
| `groq` | Groq API 클라이언트 (AsyncGroq) |
| `beautifulsoup4` | Naver Finance HTML 파싱 |
| `google-generativeai` | (설치됨, 현재 미사용 — Gemini 전환 검토용) |

### 환경 변수 추가 (`.env`)
```
GROQ_API_KEY=...        # 필수 — Groq 무료 API
GEMINI_API_KEY=...      # 선택 — Gemini 전환 시 사용
```

---

# 컵앤핸들 패턴 UI 통합 + 백테스팅 OHLC 바 모델 (2026-03-15)

## 1. 컵앤핸들(Cup & Handle) UI 개선

### 배경

컵앤핸들 패턴을 종합점수에 반영하지 않고 별도 알림으로 표시. expired 상태 종목도 주식분석 탭에 실시간으로 표시하도록 개선.

### breakout_status 4단계

| 상태 | 의미 | 표시 색상 |
|------|------|---------|
| `fresh` | 돌파 발생 (3일 이내) | 보라 |
| `pre` | 돌파 임박 | 주황 |
| `expired` | 돌파 실패 / 기간 초과 | 회색 |
| `forming` | 컵 형성 중 | — |

`is_cup_handle = True` 조건: `score >= 60` AND `breakout_status in ("fresh", "pre")`

### 변경된 파일

#### `backend/core/signal_service.py`
- `cup_handle_confirmed=False`이어도 `cup_handle` 데이터가 있으면 항상 반환 (이전: None 반환)
```python
"cup_handle": cup_handle_data if cup_handle_data else None,  # expired도 포함
```

#### `frontend/src/lib/api.ts`
- `EntrySignal` 타입에 `breakout_status` 필드 추가
- `fetchEntrySignal(code, market, strategy)` 함수 추가
```typescript
cup_handle?: { score: number; reasons: string[]; cup_depth_pct?: number; handle_days?: number; breakout_status?: string };
export const fetchEntrySignal = (code, market, strategy = 'pattern'): Promise<EntrySignal> =>
    get(`/signals/entry/${code}?market=${market}&strategy=${strategy}`);
```

#### `frontend/src/pages/StocksDashboard.tsx`
- 종목 선택 시 pattern 전략으로 C&H 데이터 독립 fetch
- 종목명 옆 C&H 배지 표시 (fresh=보라, pre=주황, expired=회색)
- 오른쪽 패널에 "☕ 컵앤핸들" 카드 추가 (점수, 상태, 컵 깊이, 핸들 기간, 상세 이유 포함)
- `<CandleChart key={`${stockCode}-${chartMode}`}>` — 종목/모드 변경 시 차트 완전 재생성

#### `frontend/src/pages/SignalsDashboard.tsx`
- `cup_handle_confirmed` 여부 관계없이 `cup_handle` 데이터가 있으면 C&H 박스 표시
- expired: 회색 스타일, confirmed(fresh/pre): 보라 스타일로 구분

---

## 2. 차트 줌/위치 초기화 버그 수정

### 문제

차트를 확대하거나 위치를 이동한 후 데이터 폴링 갱신(30초)이 발생하면 뷰포트가 초기 상태로 리셋되는 현상.

### 원인

`useEffect([data])`에서 매번 `chart.remove()` + `createChart()` 를 호출하여 차트 전체가 재생성되었기 때문.

### 수정: `frontend/src/components/CandleChart.tsx`

완전 재작성. 차트 생성과 데이터 갱신을 분리.

```typescript
// 차트 생성 — 마운트 시 1회
useEffect(() => {
    const chart = createChart(containerRef.current, { ... });
    const series = chart.addCandlestickSeries({ ... });
    chartRef.current = chart;
    seriesRef.current = series;
    firstDataRef.current = true;
    const ro = new ResizeObserver(handleResize);
    ro.observe(containerRef.current);
    return () => { ro.disconnect(); chart.remove(); };
}, []);

// 데이터 갱신 — series.setData()만 호출 (뷰포트 유지)
useEffect(() => {
    if (!seriesRef.current || data.length === 0) return;
    seriesRef.current.setData(data);
    if (firstDataRef.current && chartRef.current) {
        chartRef.current.timeScale().fitContent();  // 최초만 fitContent
        firstDataRef.current = false;
    }
}, [data]);
```

- `window.addEventListener('resize')` → `ResizeObserver`로 교체

---

## 3. 주봉/분봉 데이터 문제 수정

### 문제

- 주봉: "데이터 없음" 오류
- 분봉: 30봉만 반환 (장중 데이터 부족)

### 수정: `backend/api/routers/stocks.py`

#### 주봉 (`/stocks/{code}/weekly`)
- 원인: pykrx `get_market_ohlcv_by_date` 파라미터명이 `freq` (`frequency` 아님), `'w'` 미지원
- 수정: `freq="d"` (일봉)로 조회 후 pandas `resample("W-FRI")`로 주봉 변환

```python
df_w = df.resample("W-FRI").agg({
    "시가": "first", "고가": "max", "저가": "min", "종가": "last", "거래량": "sum"
}).dropna(subset=["거래량"])
```

#### 분봉 (`/stocks/{code}/minute`)
- 원인: `kis_client.get_minute_chart()` = 최근 30봉 한계
- 수정: `kis_client.get_full_day_minute_chart()` — 최대 10회 페이지네이션으로 장 전체 분봉 수집

---

## 4. 최적화 → 백테스팅 파라미터 자동 연동

### 기존 문제

최적화 탭의 "파라미터 복사" 버튼이 클립보드 복사만 하여 백테스팅 입력 필드에 직접 적용 불가.

### 수정 흐름

```
OptimizeDashboard
  "백테스팅에 적용 →" 버튼 클릭
  └→ onApplyParams({ symbols, days, stopLoss, minScore, maxHoldingDays, _appliedAt })
       └→ App.tsx: handleApplyOptimizedParams()
            ├→ setOptimizedParams(params)
            └→ setActiveTab('backtest')  // 탭 자동 전환
                 └→ BacktestDashboard: useEffect([optimizedParams._appliedAt])
                      ├→ 폼 자동 적용
                      └→ "✅ 최적화 파라미터가 적용되었습니다" 배너 4초 표시
```

#### 변경된 파일

| 파일 | 변경 내용 |
|------|---------|
| `frontend/src/App.tsx` | `OptimizedParams` 인터페이스, `optimizedParams` 상태, `handleApplyOptimizedParams` 콜백 |
| `frontend/src/pages/OptimizeDashboard.tsx` | "파라미터 복사" → "백테스팅에 적용 →" 버튼, `onApplyParams` prop |
| `frontend/src/pages/BacktestDashboard.tsx` | `optimizedParams` prop, `useEffect` 자동 적용, `appliedBanner` 상태 |

---

## 5. 백테스팅 엔진 OHLC 바 모델 도입

### 배경

백테스팅 0% 승률 vs 페이퍼트레이딩 수익 차이 원인 분석:

| 항목 | 백테스팅 (수정 전) | 페이퍼트레이딩 |
|------|-----------|------------|
| 진입 최소 점수 | 60점 | 65점 |
| 최대 보유 기간 | 7일 | 5일 |
| 손절/익절 체크 | 종가만 | 실시간 (분봉) |
| 장중 가격 시뮬레이션 | 없음 | 있음 |

### OHLC 바 모델 원리

일봉 High/Low로 장중 손절·익절을 시뮬레이션.

```
상승일 (Close >= Open): TP 먼저 체크 → SL 체크
하락일 (Close < Open):  SL 먼저 체크 → TP 체크
```

### 수정: `backend/backtest/engine.py`

#### 기본값 조정
```python
min_entry_score: float = 65.0  # 60 → 65 (페이퍼트레이딩과 동일)
max_holding_days: int = 5      # 7 → 5 (페이퍼트레이딩과 동일)
```

#### 신규 메서드: `check_exit_conditions_ohlc()`

```python
def check_exit_conditions_ohlc(
    self, trade, current_date, bar_open, bar_high, bar_low, bar_close
) -> Tuple[bool, Optional[str], float, float]:
    trade.update_price_extremes(bar_high)
    bullish_day = bar_close >= bar_open
    if bullish_day:
        result = self._check_tp_price(trade, current_date, bar_high)
        if result[0]: return result
        result = self._check_sl_price(trade, current_date, bar_low)
        if result[0]: return result
    else:
        result = self._check_sl_price(trade, current_date, bar_low)
        if result[0]: return result
        result = self._check_tp_price(trade, current_date, bar_high)
        if result[0]: return result
    holding_days = (current_date - trade.entry_time).days
    if holding_days >= self.config.max_holding_days:
        return True, f"time_limit_{self.config.max_holding_days}days", 1.0, bar_close
    return False, None, 0.0, bar_close
```

#### `run_simple_backtest` 루프 수정

```python
# 수정 전
current_price = ohlcv_data.iloc[i]["Close"]
should_exit, exit_reason, volume_pct = backtester.check_exit_conditions(trade, current_date, current_price)
if should_exit:
    backtester.close_position(trade, current_date, current_price, exit_reason, volume_pct)

# 수정 후
bar = ohlcv_data.iloc[i]
bar_open, bar_high, bar_low, bar_close = float(bar["Open"]), float(bar["High"]), float(bar["Low"]), float(bar["Close"])
should_exit, exit_reason, volume_pct, exit_price = backtester.check_exit_conditions_ohlc(
    trade, current_date, bar_open, bar_high, bar_low, bar_close)
if should_exit:
    backtester.close_position(trade, current_date, exit_price, exit_reason, volume_pct)
```

#### 강제 청산 개선

```python
# 수정 전: entry_price 사용 (실제 가격 반영 안 됨)
last_price = trade.entry_price

# 수정 후: 각 종목 실제 마지막 종가 사용
last_prices = {code: float(data[data.index <= end_date].iloc[-1]["Close"]) for code, data in symbol_data.items()}
last_price = last_prices.get(trade.code, trade.entry_price)
```

### 기대 효과

- 페이퍼트레이딩과 동일한 진입 기준(65점) 적용 → 과거 수익 기록 재현 가능
- 장중 손절/익절 시뮬레이션으로 종가 기준보다 현실적인 결과
- 강제 청산 가격 정확도 향상
