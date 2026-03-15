"""
Backtesting engine for trading strategies.
과거 데이터로 매매 전략을 검증하는 백테스팅 엔진
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd

from ..core.signals import SignalManager, SignalType

logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    """거래 상태"""
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Trade:
    """거래 기록"""
    code: str
    name: str
    entry_time: datetime
    entry_price: float
    quantity: int

    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    profit_loss: float = 0.0
    profit_loss_pct: float = 0.0

    status: TradeStatus = TradeStatus.OPEN

    # 진입 신호 정보
    entry_signal: Dict = field(default_factory=dict)

    # 최고가/최저가 추적
    highest_price: float = 0.0
    lowest_price: float = 0.0

    # 분할 익절/손절 추적 (내부 상태, 보고서 미포함)
    original_quantity: int = field(default=0, init=False)
    executed_tp_targets: set = field(default_factory=set)
    executed_sl_targets: set = field(default_factory=set)
    dynamic_stop_price: float = 0.0  # 동적 손절가 (1차 익절 후 본전으로 이동)
    breakeven_active: bool = False    # 1차 익절 후 break-even 발동 여부
    partial_profit_loss: float = 0.0  # 부분 청산에서 실현된 누적 손익

    def __post_init__(self):
        self.original_quantity = self.quantity
        if self.highest_price == 0.0:
            self.highest_price = self.entry_price
        if self.lowest_price == 0.0:
            self.lowest_price = self.entry_price

    def update_price_extremes(self, current_price: float):
        """최고가/최저가 업데이트"""
        self.highest_price = max(self.highest_price, current_price)
        self.lowest_price = min(self.lowest_price, current_price)

    def close(self, exit_time: datetime, exit_price: float, exit_reason: str):
        """거래 청산 (분할 청산 누적 손익 포함)"""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        self.status = TradeStatus.CLOSED

        # 총 손익 = 부분 청산 누적 손익 + 최종 청산 손익
        final_pl = (exit_price - self.entry_price) * self.quantity
        self.profit_loss = self.partial_profit_loss + final_pl
        # 수익률 = 총 손익 / 최초 진입 비용 (original_quantity 기준)
        total_cost = self.entry_price * self.original_quantity
        self.profit_loss_pct = (self.profit_loss / total_cost * 100) if total_cost > 0 else 0

    def to_dict(self) -> Dict:
        """딕셔너리 변환"""
        return {
            "code": self.code,
            "name": self.name,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "profit_loss": round(self.profit_loss, 2),
            "profit_loss_pct": round(self.profit_loss_pct, 2),
            "status": self.status.value,
            "holding_days": (self.exit_time - self.entry_time).days if self.exit_time else None,
            "max_gain_pct": round(((self.highest_price - self.entry_price) / self.entry_price) * 100, 2),
            "max_loss_pct": round(((self.lowest_price - self.entry_price) / self.entry_price) * 100, 2)
        }


@dataclass
class BacktestConfig:
    """백테스팅 설정"""
    initial_capital: float = 10000.0  # 초기 자본금
    position_size_pct: float = 0.15  # 종목당 투자 비율 (15%)
    max_positions: int = 2  # 최대 동시 보유 종목 수

    # 진입 조건
    entry_strategy: str = "combined"  # volume, technical, pattern, combined, rsi_golden_cross, weekly_rsi_swing, multi_tf_momentum_plus
    min_entry_score: float = 65.0  # 최소 진입 점수 (페이퍼트레이딩과 동일)

    # 청산 조건 — G(보수형) 전략 기본값
    # 검증: 중소형주 8종목 730일 백테스트 D/G/H 비교에서 ROI·MDD 복합 우위 확인
    take_profit_targets: List[Dict] = field(default_factory=lambda: [
        {"ratio": 0.02, "volume_pct": 0.33, "name": "1차 익절 +2%"},   # 잔여의 1/3 — 빠른 확정 & breakeven 전환
        {"ratio": 0.05, "volume_pct": 0.50, "name": "2차 익절 +5%"},   # 잔여의 1/2
        {"ratio": 0.10, "volume_pct": 1.00, "name": "3차 익절 +10%"},  # 전량
    ])
    stop_loss_targets: List[Dict] = field(default_factory=lambda: [
        {"ratio": -0.01, "volume_pct": 0.33, "name": "1차 손절 -1%"},  # 잔여의 1/3
        {"ratio": -0.02, "volume_pct": 1.00, "name": "2차 손절 -2%"},  # 전량
    ])
    stop_loss_ratio: float = -0.02  # 하위 호환용 (동적 손절가 초기값으로만 사용)
    trailing_stop_ratio: float = -0.04  # 최고가 대비 -4% (G전략: 구 D의 -5%보다 타이트)
    max_holding_days: int = 5  # 최대 보유 일수 (페이퍼트레이딩과 동일: 5일)

    # 수수료
    commission_rate: float = 0.001  # 0.1% 수수료


class Backtester:
    """백테스팅 엔진"""

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.signal_manager = SignalManager()

        # 거래 기록
        self.trades: List[Trade] = []
        self.open_positions: List[Trade] = []

        # 자본 추적
        self.capital = self.config.initial_capital
        self.cash = self.config.initial_capital
        self.portfolio_value_history: List[Dict] = []

        # 통계
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

    def calculate_position_size(self, price: float) -> int:
        """포지션 크기 계산"""
        # 사용 가능한 자본
        available_capital = self.cash

        # 종목당 투자 금액
        position_capital = self.config.initial_capital * self.config.position_size_pct

        # 실제 사용할 금액 (사용 가능한 자본 고려)
        investment = min(position_capital, available_capital)

        # 수량 계산
        quantity = int(investment / price)

        return quantity

    def can_open_position(self) -> bool:
        """포지션 오픈 가능 여부"""
        return len(self.open_positions) < self.config.max_positions

    def get_commission(self, price: float, quantity: int) -> float:
        """수수료 계산"""
        return price * quantity * self.config.commission_rate

    def open_position(self, code: str, name: str, entry_time: datetime,
                     entry_price: float, entry_signal: Dict) -> Optional[Trade]:
        """포지션 오픈"""
        if not self.can_open_position():
            return None

        quantity = self.calculate_position_size(entry_price)
        if quantity <= 0:
            return None

        # 매수 비용 (가격 + 수수료)
        cost = entry_price * quantity
        commission = self.get_commission(entry_price, quantity)
        total_cost = cost + commission

        if total_cost > self.cash:
            return None

        # 거래 생성
        trade = Trade(
            code=code,
            name=name,
            entry_time=entry_time,
            entry_price=entry_price,
            quantity=quantity,
            entry_signal=entry_signal
        )

        # 동적 손절가 초기화
        trade.dynamic_stop_price = entry_price * (1 + self.config.stop_loss_ratio)

        # 자본 업데이트
        self.cash -= total_cost

        # 포지션 추가
        self.open_positions.append(trade)
        self.trades.append(trade)
        self.total_trades += 1

        logger.info(f"[BT] OPEN: {code} x{quantity} @ ${entry_price:.2f} (commission: ${commission:.2f})")

        return trade

    def close_position(self, trade: Trade, exit_time: datetime,
                      exit_price: float, exit_reason: str, volume_pct: float = 1.0):
        """포지션 청산 (volume_pct < 1.0이면 부분 청산, 잔여 수량 기준)"""
        close_qty = trade.quantity if volume_pct >= 1.0 else max(1, int(trade.quantity * volume_pct))
        close_qty = min(close_qty, trade.quantity)

        commission = self.get_commission(exit_price, close_qty)
        self.cash += exit_price * close_qty - commission

        is_full = (close_qty >= trade.quantity)

        if is_full:
            trade.quantity = close_qty
            trade.close(exit_time, exit_price, exit_reason)
            self.open_positions.remove(trade)
            # 총 손익(부분청산 누적 포함) 기준으로 승/패 판정
            if trade.profit_loss > 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1
            logger.info(f"[BT] CLOSE: {trade.code} x{close_qty} @ ${exit_price:.2f} "
                       f"({trade.profit_loss_pct:+.2f}%) - {exit_reason}")
        else:
            pl_pct = (exit_price - trade.entry_price) / trade.entry_price * 100
            # 부분 청산 실현 손익 누적 (수수료 제외 단순 계산)
            trade.partial_profit_loss += (exit_price - trade.entry_price) * close_qty
            trade.quantity -= close_qty
            # TP 부분청산일 때만 break-even 이동 (SL 부분청산은 이동 안 함)
            tp_names = {tgt["name"] for tgt in self.config.take_profit_targets}
            if exit_reason in tp_names and not trade.breakeven_active:
                trade.dynamic_stop_price = max(trade.dynamic_stop_price, trade.entry_price)
                trade.breakeven_active = True
                logger.info(f"[BT] PARTIAL(TP): {trade.code} x{close_qty} → 잔여 x{trade.quantity} "
                           f"@ ${exit_price:.2f} ({pl_pct:+.2f}%) - {exit_reason} | 손절가 → 본전")
            else:
                logger.info(f"[BT] PARTIAL(SL): {trade.code} x{close_qty} → 잔여 x{trade.quantity} "
                           f"@ ${exit_price:.2f} ({pl_pct:+.2f}%) - {exit_reason}")
            # 부분 청산은 win/loss 카운트 없음 (포지션 단위로만 집계)

    def check_exit_conditions(self, trade: Trade, current_time: datetime,
                             current_price: float) -> Tuple[bool, Optional[str], float]:
        """청산 조건 체크 → (should_exit, reason, volume_pct)
        volume_pct: 청산 비율 (잔여 수량 기준, 1.0 = 전량)
        """
        # 가격 극값 업데이트
        trade.update_price_extremes(current_price)

        profit_ratio = (current_price - trade.entry_price) / trade.entry_price

        # 1. 분할 익절 (이미 실행된 단계는 건너뜀)
        for i, target in enumerate(self.config.take_profit_targets):
            if i in trade.executed_tp_targets:
                continue
            if profit_ratio >= target["ratio"]:
                trade.executed_tp_targets.add(i)
                return True, target["name"], target["volume_pct"]

        # 2. 손절 분기
        if trade.breakeven_active:
            # Phase B: 1차 익절 후 → break-even 손절 전량
            stop_ratio = (trade.dynamic_stop_price - trade.entry_price) / trade.entry_price
            if profit_ratio <= stop_ratio:
                return True, "손절(본전)", 1.0
        else:
            # Phase A: 1차 익절 전 → 분할 손절
            for i, sl in enumerate(self.config.stop_loss_targets):
                if i in trade.executed_sl_targets:
                    continue
                if profit_ratio <= sl["ratio"]:
                    trade.executed_sl_targets.add(i)
                    return True, sl["name"], sl["volume_pct"]

        # 3. 트레일링 스톱
        trailing_threshold = trade.highest_price * (1 + self.config.trailing_stop_ratio)
        if current_price <= trailing_threshold and trade.highest_price > trade.entry_price:
            return True, "trailing_stop", 1.0

        # 4. 시간 기반 청산
        holding_days = (current_time - trade.entry_time).days
        if holding_days >= self.config.max_holding_days:
            return True, f"time_limit_{self.config.max_holding_days}days", 1.0

        return False, None, 0.0

    def check_exit_conditions_ohlc(
        self, trade: Trade, current_date: datetime,
        bar_open: float, bar_high: float, bar_low: float, bar_close: float
    ) -> Tuple[bool, Optional[str], float, float]:
        """OHLC 바 모델로 장중 손절/익절 체크 → (should_exit, reason, volume_pct, exit_price)

        상승일(Close >= Open): 고가(H) → 저가(L) 순서로 가정 (TP 우선)
        하락일(Close < Open) : 저가(L) → 고가(H) 순서로 가정 (SL 우선)
        """
        # 장중 최고가 업데이트 (High 기준)
        trade.update_price_extremes(bar_high)

        bullish_day = bar_close >= bar_open

        if bullish_day:
            # 상승일: TP 먼저 (H 기준), 그 다음 SL (L 기준)
            result = self._check_tp_price(trade, current_date, bar_high)
            if result[0]:
                return result
            result = self._check_sl_price(trade, current_date, bar_low)
            if result[0]:
                return result
        else:
            # 하락일: SL 먼저 (L 기준), 그 다음 TP (H 기준)
            result = self._check_sl_price(trade, current_date, bar_low)
            if result[0]:
                return result
            result = self._check_tp_price(trade, current_date, bar_high)
            if result[0]:
                return result

        # 시간 기반 청산 (종가 기준)
        holding_days = (current_date - trade.entry_time).days
        if holding_days >= self.config.max_holding_days:
            return True, f"time_limit_{self.config.max_holding_days}days", 1.0, bar_close

        return False, None, 0.0, bar_close

    def _check_tp_price(self, trade: Trade, _current_date: datetime,
                        check_price: float) -> Tuple[bool, Optional[str], float, float]:
        """TP 조건 체크 (check_price = 장중 High)"""
        profit_ratio = (check_price - trade.entry_price) / trade.entry_price
        for i, target in enumerate(self.config.take_profit_targets):
            if i in trade.executed_tp_targets:
                continue
            if profit_ratio >= target["ratio"]:
                trade.executed_tp_targets.add(i)
                exit_price = trade.entry_price * (1 + target["ratio"])
                return True, target["name"], target["volume_pct"], exit_price
        return False, None, 0.0, check_price

    def _check_sl_price(self, trade: Trade, current_date: datetime,
                        check_price: float) -> Tuple[bool, Optional[str], float, float]:
        """SL 조건 체크 (check_price = 장중 Low)"""
        profit_ratio = (check_price - trade.entry_price) / trade.entry_price

        # 트레일링 스탑
        trailing_threshold = trade.highest_price * (1 + self.config.trailing_stop_ratio)
        if check_price <= trailing_threshold and trade.highest_price > trade.entry_price:
            return True, "trailing_stop", 1.0, max(check_price, trailing_threshold)

        if trade.breakeven_active:
            stop_ratio = (trade.dynamic_stop_price - trade.entry_price) / trade.entry_price
            if profit_ratio <= stop_ratio:
                return True, "손절(본전)", 1.0, trade.dynamic_stop_price
        else:
            for i, sl in enumerate(self.config.stop_loss_targets):
                if i in trade.executed_sl_targets:
                    continue
                if profit_ratio <= sl["ratio"]:
                    trade.executed_sl_targets.add(i)
                    exit_price = trade.entry_price * (1 + sl["ratio"])
                    return True, sl["name"], sl["volume_pct"], exit_price

        return False, None, 0.0, check_price

    def update_portfolio_value(self, current_date: datetime, current_prices: Dict[str, float]):
        """포트폴리오 가치 업데이트"""
        # 보유 포지션 가치
        position_value = 0.0
        for trade in self.open_positions:
            if trade.code in current_prices:
                position_value += current_prices[trade.code] * trade.quantity

        total_value = self.cash + position_value

        self.portfolio_value_history.append({
            "date": current_date,
            "cash": self.cash,
            "position_value": position_value,
            "total_value": total_value,
            "open_positions": len(self.open_positions)
        })

    async def run(self, symbols: List[Dict], start_date: datetime, end_date: datetime) -> Dict:
        """
        백테스팅 실행

        Args:
            symbols: [{"code": "AAPL", "name": "Apple Inc.", "market": "US"}, ...]
            start_date: 시작일
            end_date: 종료일

        Returns:
            백테스팅 결과
        """
        logger.info(f"[BT] Starting backtest: {start_date.date()} ~ {end_date.date()}")
        logger.info(f"[BT] Symbols: {len(symbols)}, Initial capital: ${self.config.initial_capital:,.2f}")

        # 날짜별로 반복
        current_date = start_date

        while current_date <= end_date:
            # 해당 날짜의 가격 데이터 (임시로 스킵, 실제로는 OHLCV 데이터 필요)
            # 실제 구현에서는 미리 로드한 데이터 사용

            # 1. 청산 조건 체크 (기존 포지션)
            for trade in self.open_positions[:]:  # 복사본으로 순회
                # 현재가 조회 필요 (여기서는 시뮬레이션)
                # current_price = get_price(trade.code, current_date)
                pass

            # 2. 진입 신호 체크 (신규 포지션)
            for symbol in symbols:
                if not self.can_open_position():
                    break

                # OHLCV 데이터로 신호 생성
                # ohlcv_data = get_ohlcv_data(symbol['code'], current_date)
                # signal = self.signal_manager.generate_entry_signal(ohlcv_data)
                pass

            # 3. 포트폴리오 가치 업데이트
            # current_prices = get_current_prices(symbols, current_date)
            # self.update_portfolio_value(current_date, current_prices)

            current_date += timedelta(days=1)

        # 결과 생성
        return self.generate_report()

    def generate_report(self) -> Dict:
        """백테스팅 결과 리포트 생성"""
        # 기본 통계
        total_trades = self.total_trades
        winning_trades = self.winning_trades
        losing_trades = self.losing_trades

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # 손익 계산
        closed_trades = [t for t in self.trades if t.status == TradeStatus.CLOSED]
        total_profit = sum(t.profit_loss for t in closed_trades if t.profit_loss > 0)
        total_loss = sum(t.profit_loss for t in closed_trades if t.profit_loss < 0)
        net_profit = sum(t.profit_loss for t in closed_trades)

        # 손익비
        profit_factor = abs(total_profit / total_loss) if total_loss != 0 else 0

        # 평균 손익
        avg_win = total_profit / winning_trades if winning_trades > 0 else 0
        avg_loss = total_loss / losing_trades if losing_trades > 0 else 0

        # 최종 자본
        final_capital = self.cash
        if self.portfolio_value_history:
            final_capital = self.portfolio_value_history[-1]["total_value"]

        roi = ((final_capital - self.config.initial_capital) / self.config.initial_capital) * 100

        # MDD 계산
        mdd = self.calculate_mdd()

        # 최고/최저 거래
        best_trade = max(closed_trades, key=lambda t: t.profit_loss_pct) if closed_trades else None
        worst_trade = min(closed_trades, key=lambda t: t.profit_loss_pct) if closed_trades else None

        return {
            "summary": {
                "initial_capital": self.config.initial_capital,
                "final_capital": final_capital,
                "net_profit": net_profit,
                "roi": roi,
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "max_drawdown": mdd,
            },
            "trades": [t.to_dict() for t in closed_trades],
            "open_positions": [t.to_dict() for t in self.open_positions],
            "portfolio_history": self.portfolio_value_history,
            "best_trade": best_trade.to_dict() if best_trade else None,
            "worst_trade": worst_trade.to_dict() if worst_trade else None,
            "config": {
                "entry_strategy": self.config.entry_strategy,
                "min_entry_score": self.config.min_entry_score,
                "stop_loss_ratio": self.config.stop_loss_ratio,
                "max_holding_days": self.config.max_holding_days,
            }
        }

    def calculate_mdd(self) -> float:
        """최대 낙폭(MDD) 계산"""
        if not self.portfolio_value_history:
            return 0.0

        values = [p["total_value"] for p in self.portfolio_value_history]
        peak = values[0]
        max_drawdown = 0.0

        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown * 100  # 퍼센트로 반환


# ═══════════════════════════════════════════════════════════════
# 간편 백테스팅 (과거 데이터 로드 포함)
# ═══════════════════════════════════════════════════════════════

async def run_simple_backtest(
    symbols: List[str],
    market: str,
    start_date: datetime,
    end_date: datetime,
    config: Optional[BacktestConfig] = None
) -> Dict:
    """
    간편 백테스팅 실행 - 병렬 데이터 로딩으로 최적화

    Args:
        symbols: 종목 코드 리스트
        market: "KR" | "US"
        start_date: 시작일
        end_date: 종료일
        config: 백테스팅 설정

    Returns:
        백테스팅 결과
    """
    import asyncio
    from ..core.signal_service import collect_ohlcv_data

    config = config or BacktestConfig()
    backtester = Backtester(config)

    logger.info(f"[BT] Loading historical data for {len(symbols)} symbols in parallel...")

    # 병렬로 모든 종목의 데이터 로드
    # MA120 계산 워밍업을 위해 백테스팅 기간보다 150일 더 로드
    days = (end_date - start_date).days + 150

    async def load_data(code: str):
        try:
            data = await collect_ohlcv_data(code, market, days)
            if data.empty:
                logger.warning(f"[BT] No data for {code}")
                return code, None
            return code, data
        except Exception as e:
            logger.error(f"[BT] Failed to load {code}: {e}")
            return code, None

    # 모든 데이터를 병렬로 로드
    load_tasks = [load_data(code) for code in symbols]
    loaded_data = await asyncio.gather(*load_tasks)

    # 데이터를 딕셔너리로 변환
    symbol_data = {code: data for code, data in loaded_data if data is not None}

    logger.info(f"[BT] Loaded {len(symbol_data)}/{len(symbols)} symbols successfully")

    # 각 종목별로 시뮬레이션
    for code, ohlcv_data in symbol_data.items():

        # timezone-aware 처리
        ohlcv_data.index = pd.to_datetime(ohlcv_data.index)
        if ohlcv_data.index.tz is not None:
            ohlcv_data.index = ohlcv_data.index.tz_localize(None)

        # 끝날짜만 필터 (시작 이전 데이터는 MA120 등 워밍업용으로 유지)
        ohlcv_data = ohlcv_data[ohlcv_data.index <= end_date]

        if len(ohlcv_data) < 20:
            continue

        # 각 날짜별로 진입/청산 시뮬레이션
        for i in range(20, len(ohlcv_data)):
            current_date = ohlcv_data.index[i]
            bar = ohlcv_data.iloc[i]
            bar_open = float(bar["Open"])
            bar_high = float(bar["High"])
            bar_low = float(bar["Low"])
            bar_close = float(bar["Close"])

            # 백테스팅 기간(start_date) 이전은 워밍업 구간 — 포지션/기록 없음
            in_period = current_date >= start_date

            # 기존 포지션 청산 체크 (OHLC 바 모델)
            if in_period:
                for trade in backtester.open_positions[:]:
                    if trade.code == code:
                        should_exit, exit_reason, volume_pct, exit_price = backtester.check_exit_conditions_ohlc(
                            trade, current_date, bar_open, bar_high, bar_low, bar_close
                        )
                        if should_exit:
                            backtester.close_position(trade, current_date, exit_price, exit_reason, volume_pct)

            # 신규 진입 체크
            if in_period and backtester.can_open_position():
                # 전략별 필요 데이터 기간 (신호 생성에 필요한 최소 bars)
                _strategy_window = {
                    'rsi_golden_cross': 250,
                    'weekly_rsi_swing': 350,
                    'multi_tf_momentum_plus': 150,
                }
                data_window = _strategy_window.get(config.entry_strategy, 120)
                historical_data = ohlcv_data.iloc[:i+1].tail(data_window)

                signal = backtester.signal_manager.generate_entry_signal(
                    historical_data,
                    strategy=config.entry_strategy
                )

                if signal["signal"] == SignalType.BUY and signal["score"] >= config.min_entry_score:
                    backtester.open_position(
                        code=code,
                        name=code,
                        entry_time=current_date,
                        entry_price=bar_close,
                        entry_signal=signal
                    )

            # 포트폴리오 가치 업데이트 (백테스팅 기간만)
            if in_period:
                current_prices = {trade.code: bar_close for trade in backtester.open_positions if trade.code == code}
                backtester.update_portfolio_value(current_date, current_prices)

    # 미청산 포지션 강제 청산 (각 종목의 마지막 종가 사용)
    last_prices: Dict[str, float] = {}
    for code, ohlcv_data in symbol_data.items():
        filtered = ohlcv_data[ohlcv_data.index <= end_date]
        if not filtered.empty:
            last_prices[code] = float(filtered.iloc[-1]["Close"])
    for trade in backtester.open_positions[:]:
        last_price = last_prices.get(trade.code, trade.entry_price)
        backtester.close_position(trade, end_date, last_price, "backtest_end")

    return backtester.generate_report()
