# 백테스팅 시스템 가이드

## 개요

과거 데이터로 매매 전략을 검증하는 백테스팅 시스템입니다. 실제 거래 전에 전략의 수익성과 위험성을 평가할 수 있습니다.

---

## 주요 기능

### ✅ 백테스팅 엔진 ([engine.py](backend/backtest/engine.py))
- 과거 데이터 기반 거래 시뮬레이션
- 진입/청산 신호 자동 실행
- 포지션 관리 (최대 동시 보유 종목 제한)
- 수수료 반영
- 실시간 포트폴리오 가치 추적

### ✅ 성과 분석 ([analytics.py](backend/backtest/analytics.py))
- **샤프 비율 (Sharpe Ratio)**: 위험 대비 수익률
- **소르티노 비율 (Sortino Ratio)**: 하방 위험 대비 수익률
- **칼마 비율 (Calmar Ratio)**: MDD 대비 수익률
- **최대 낙폭 (MDD)**: 최고점 대비 최대 하락폭
- **승률, 손익비, 기대값** 계산
- 거래 기간 분석
- 청산 이유 통계
- 연속 승/패 기록
- 월별 수익률

---

## API 엔드포인트

### 1. 백테스팅 실행

#### POST `/backtest/run`

단일 전략으로 백테스팅을 실행합니다.

**요청 Body (JSON):**
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

**파라미터:**
- `symbols` (array): 종목 코드 리스트
- `market` (string): "KR" | "US"
- `days` (number): 백테스팅 기간 (일)
- `initial_capital` (number): 초기 자본금
- `entry_strategy` (string): "volume" | "technical" | "pattern" | "combined"
- `min_entry_score` (number): 최소 진입 점수 (0-100)
- `stop_loss_ratio` (number): 손절 비율 (예: -0.02 = -2%)
- `max_holding_days` (number): 최대 보유 일수

**응답 예시:**
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
    "avg_win": 150.0,
    "avg_loss": -60.0,
    "max_drawdown": 8.5
  },
  "advanced_metrics": {
    "sharpe_ratio": 1.85,
    "sortino_ratio": 2.3,
    "calmar_ratio": 2.94,
    "expectancy": 55.56,
    "win_loss_ratio": 2.0
  },
  "trade_analysis": {
    "duration": {
      "avg_holding_days": 2.3,
      "min_holding_days": 1,
      "max_holding_days": 5,
      "median_holding_days": 2.0
    },
    "exit_reasons": {
      "1차 익절 +3%": 20,
      "2차 익절 +5%": 8,
      "fixed_stop_loss": 12,
      "trailing_stop": 3,
      "time_limit_5days": 2
    },
    "consecutive": {
      "max_consecutive_wins": 7,
      "max_consecutive_losses": 3,
      "current_streak": 2
    }
  },
  "monthly_returns": [
    {"month": "2025-12", "return": 5.2, "start_value": 10000, "end_value": 10520},
    {"month": "2026-01", "return": 12.3, "start_value": 10520, "end_value": 11814},
    {"month": "2026-02", "return": 5.8, "start_value": 11814, "end_value": 12500}
  ],
  "trades": [
    {
      "code": "AAPL",
      "name": "AAPL",
      "entry_time": "2025-12-15T09:30:00",
      "entry_price": 150.0,
      "quantity": 20,
      "exit_time": "2025-12-17T15:00:00",
      "exit_price": 154.5,
      "exit_reason": "1차 익절 +3%",
      "profit_loss": 90.0,
      "profit_loss_pct": 3.0,
      "status": "closed",
      "holding_days": 2,
      "max_gain_pct": 4.2,
      "max_loss_pct": -0.5
    }
  ],
  "best_trade": {
    "code": "TSLA",
    "profit_loss_pct": 15.5,
    "profit_loss": 465.0
  },
  "worst_trade": {
    "code": "NVDA",
    "profit_loss_pct": -2.0,
    "profit_loss": -60.0
  },
  "config": {
    "entry_strategy": "combined",
    "min_entry_score": 60.0,
    "stop_loss_ratio": -0.02,
    "max_holding_days": 5
  }
}
```

---

### 2. 전략 비교

#### POST `/backtest/compare`

여러 전략을 동시에 백테스팅하여 비교합니다.

**요청 Body:**
```json
{
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "market": "US",
  "days": 90,
  "strategies": ["volume", "technical", "combined"]
}
```

**응답 예시:**
```json
{
  "comparison": {
    "strategies": [
      {
        "strategy": "volume",
        "roi": 15.2,
        "sharpe_ratio": 1.45,
        "win_rate": 62.5,
        "max_drawdown": 10.2,
        "total_trades": 38,
        "profit_factor": 2.1
      },
      {
        "strategy": "technical",
        "roi": 18.7,
        "sharpe_ratio": 1.72,
        "win_rate": 65.0,
        "max_drawdown": 8.5,
        "total_trades": 40,
        "profit_factor": 2.4
      },
      {
        "strategy": "combined",
        "roi": 25.0,
        "sharpe_ratio": 1.85,
        "win_rate": 66.7,
        "max_drawdown": 8.5,
        "total_trades": 45,
        "profit_factor": 2.5
      }
    ],
    "best_roi": "combined",
    "best_sharpe": "combined",
    "best_win_rate": "combined",
    "lowest_mdd": "technical"
  },
  "details": [...]
}
```

---

## Python 사용 예시

### 기본 백테스팅

```python
import asyncio
from datetime import datetime, timedelta
from backend.backtest.engine import BacktestConfig, run_simple_backtest
from backend.backtest.analytics import PerformanceAnalytics

async def run_backtest():
    # 설정
    symbols = ["AAPL", "MSFT", "GOOGL", "TSLA"]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    config = BacktestConfig(
        initial_capital=10000.0,
        entry_strategy="combined",
        min_entry_score=60.0,
        stop_loss_ratio=-0.02,
        max_holding_days=5
    )

    # 백테스팅 실행
    result = await run_simple_backtest(
        symbols=symbols,
        market="US",
        start_date=start_date,
        end_date=end_date,
        config=config
    )

    # 향상된 분석
    enhanced_result = PerformanceAnalytics.generate_enhanced_report(result)

    # 결과 출력
    summary = enhanced_result['summary']
    print(f"ROI: {summary['roi']:.2f}%")
    print(f"승률: {summary['win_rate']:.2f}%")
    print(f"샤프 비율: {enhanced_result['advanced_metrics']['sharpe_ratio']:.2f}")

    return enhanced_result

asyncio.run(run_backtest())
```

### 전략 비교

```python
from backend.backtest.analytics import compare_strategies

async def compare():
    strategies = ["volume", "technical", "combined"]
    results = []

    for strategy in strategies:
        config = BacktestConfig(entry_strategy=strategy)
        result = await run_simple_backtest(
            symbols=["AAPL", "MSFT"],
            market="US",
            start_date=start_date,
            end_date=end_date,
            config=config
        )
        enhanced = PerformanceAnalytics.generate_enhanced_report(result)
        results.append(enhanced)

    # 비교
    comparison = compare_strategies(results)
    print(f"최고 ROI 전략: {comparison['best_roi']}")
    print(f"최고 샤프 비율: {comparison['best_sharpe']}")

asyncio.run(compare())
```

---

## 백테스팅 설정 (BacktestConfig)

```python
from backend.backtest.engine import BacktestConfig

config = BacktestConfig(
    # 자본 관리
    initial_capital=10000.0,        # 초기 자본금
    position_size_pct=0.3,          # 종목당 투자 비율 (30%)
    max_positions=3,                # 최대 동시 보유 종목

    # 진입 조건
    entry_strategy="combined",      # 전략: volume, technical, pattern, combined
    min_entry_score=60.0,           # 최소 진입 점수 (0-100)

    # 청산 조건
    take_profit_targets=[           # 익절 목표
        {"ratio": 0.03, "volume_pct": 0.5, "name": "1차 익절 +3%"},
        {"ratio": 0.05, "volume_pct": 0.3, "name": "2차 익절 +5%"},
        {"ratio": 0.10, "volume_pct": 0.2, "name": "3차 익절 +10%"},
    ],
    stop_loss_ratio=-0.02,          # 손절 비율 (-2%)
    trailing_stop_ratio=-0.03,      # 트레일링 스톱 (-3%)
    max_holding_days=5,             # 최대 보유 일수

    # 수수료
    commission_rate=0.001           # 0.1% 수수료
)
```

---

## 성과 지표 해석

### 1. 수익률 지표

#### ROI (Return on Investment)
```
ROI = (최종 자본 - 초기 자본) / 초기 자본 × 100%
```
- **의미**: 투자 대비 수익률
- **기준**: 10% 이상 양호, 20% 이상 우수

#### 승률 (Win Rate)
```
승률 = 수익 거래 / 총 거래 × 100%
```
- **의미**: 성공적인 거래 비율
- **기준**: 50% 이상 양호, 60% 이상 우수

#### 손익비 (Profit Factor)
```
손익비 = 총 수익 / 총 손실
```
- **의미**: 수익과 손실의 비율
- **기준**: 1.5 이상 양호, 2.0 이상 우수

### 2. 위험 조정 수익률

#### 샤프 비율 (Sharpe Ratio)
```
Sharpe = (평균 수익률 - 무위험 수익률) / 수익률 표준편차
```
- **의미**: 위험 대비 수익률
- **기준**:
  - < 1.0: 낮음
  - 1.0 ~ 2.0: 양호
  - > 2.0: 우수

#### 소르티노 비율 (Sortino Ratio)
```
Sortino = (평균 수익률 - 무위험 수익률) / 하방 편차
```
- **의미**: 하방 위험 대비 수익률 (샤프보다 엄격)
- **기준**: 샤프 비율과 유사하나 일반적으로 더 높음

#### 칼마 비율 (Calmar Ratio)
```
Calmar = 연간 수익률 / 최대 낙폭(MDD)
```
- **의미**: MDD 대비 수익률
- **기준**:
  - < 1.0: 낮음
  - 1.0 ~ 3.0: 양호
  - > 3.0: 우수

### 3. 리스크 지표

#### 최대 낙폭 (MDD - Maximum Drawdown)
```
MDD = (최고점 - 최저점) / 최고점 × 100%
```
- **의미**: 최고점 대비 최대 하락폭
- **기준**:
  - < 10%: 낮은 위험
  - 10% ~ 20%: 중간 위험
  - > 20%: 높은 위험

#### 기대값 (Expectancy)
```
기대값 = (승률 × 평균 수익) + (패율 × 평균 손실)
```
- **의미**: 1회 거래당 기대 수익
- **기준**: 양수이면 장기적으로 수익 가능

---

## 테스트 실행

```bash
python test_backtest.py
```

### 예상 출력

```
================================================================================
  백테스팅 결과 요약
================================================================================

💰 초기 자본금: $10,000.00
💵 최종 자본금: $12,500.00
📈 순수익: $2,500.00
📊 수익률(ROI): +25.00%

📋 총 거래 수: 45
✅ 수익 거래: 30
❌ 손실 거래: 15
🎯 승률: 66.67%
💹 손익비: 2.50
📉 최대 낙폭(MDD): 8.50%

💚 평균 수익: $150.00
💔 평균 손실: $-60.00

================================================================================
  고급 성과 지표
================================================================================
📊 샤프 비율: 1.85
📊 소르티노 비율: 2.30
📊 칼마 비율: 2.94
💰 기대값: $55.56
⚖️  승패 비율: 2.00
```

---

## 백테스팅 베스트 프랙티스

### 1. 충분한 데이터 사용
- **최소 기간**: 90일 이상
- **권장 기간**: 180~365일 (계절성 반영)
- **종목 수**: 10개 이상 (통계적 유의성)

### 2. 현실적인 설정
- **수수료 반영**: 실제 거래 수수료 적용 (0.1~0.3%)
- **슬리피지 고려**: 시장가 주문 시 가격 차이
- **최소 거래 금액**: 100주 이상

### 3. 과적합 방지
- **In-sample / Out-of-sample 분리**: 70%/30%
- **Walk-forward 분석**: 주기적으로 재검증
- **파라미터 최적화 주의**: 과도한 최적화는 과적합 유발

### 4. 다양한 시장 환경 테스트
- **상승장 / 하락장 / 횡보장**
- **변동성 높은 시기 / 낮은 시기**
- **여러 종목 / 섹터**

---

## 한계점 및 주의사항

### ⚠️  백테스팅 한계
1. **과거 성과 ≠ 미래 수익**: 과거 결과가 미래를 보장하지 않음
2. **Look-ahead Bias**: 미래 정보를 사용하지 않도록 주의
3. **Survivorship Bias**: 상장폐지된 종목 고려 필요
4. **시장 충격(Market Impact)**: 대량 주문 시 가격 영향 미반영
5. **유동성 리스크**: 실제 거래 가능 여부 고려 필요

### 🔧 개선 방향
- Monte Carlo 시뮬레이션
- 슬리피지 모델 추가
- 복수 전략 조합
- 동적 포지션 사이징
- 리스크 패리티 적용

---

## 다음 단계

1. **파라미터 최적화** - 최적의 손절/익절 비율 찾기
2. **워크포워드 분석** - 시간대별 성과 검증
3. **포트폴리오 백테스팅** - 여러 전략 조합
4. **실시간 페이퍼 트레이딩** - 가상 계좌로 실전 검증

자세한 전략은 [DAY_TRADING_STRATEGY.md](DAY_TRADING_STRATEGY.md)를 참고하세요.
