"""
Paper Trading Engine — 실시간 데이터 기반 가상 자동매매 시뮬레이션
실제 주문 없이 KIS API의 리얼 데이터로 자동매매를 시뮬레이션한다.
"""
import logging
from datetime import datetime, time, timezone
from typing import List, Optional, Tuple
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, or_, and_

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
except ImportError:
    import pytz
    KST = pytz.timezone("Asia/Seoul")


# ── 설정 ─────────────────────────────────────────────────────

@dataclass
class PaperConfig:
    initial_capital: float = 10_000_000.0  # 1000만원
    position_size_pct: float = 0.15         # 종목당 15%
    max_positions: int = 2
    strategy: str = "combined"
    min_score: float = 65.0
    market: str = "KR"
    stop_loss_ratio: float = -0.04          # -4% 손절 (동적 손절가 초기값)
    trailing_stop_ratio: float = -0.05      # 최고가 대비 -5%
    take_profit_targets: List[dict] = field(default_factory=lambda: [
        {"ratio": 0.03, "volume_pct": 0.33, "name": "1차 익절 +3%"},   # 잔여의 1/3
        {"ratio": 0.07, "volume_pct": 0.50, "name": "2차 익절 +7%"},   # 잔여의 1/2
        {"ratio": 0.12, "volume_pct": 1.00, "name": "3차 익절 +12%"},  # 전량
    ])
    stop_loss_targets: List[dict] = field(default_factory=lambda: [
        {"ratio": -0.02, "volume_pct": 0.50, "name": "1차 손절 -2%"},  # 잔여의 1/2
        {"ratio": -0.04, "volume_pct": 1.00, "name": "2차 손절 -4%"},  # 전량
    ])
    # 진입 필터 (get_volume_rank 기준)
    entry_min_change_rate: float = 3.0    # 등락률 하한 (%)
    entry_max_change_rate: float = 15.0   # 등락률 상한 (%) — 과열 제외
    entry_min_volume: int = 100_000       # 최소 거래량 (주)
    max_holding_hours: int = 24 * 5       # 최대 5일 보유
    commission_rate: float = 0.001        # 0.1%
    # 급등 전 시그널 모드
    pre_surge_mode: bool = False          # True = 급등 전 시그널 기반 진입
    # pre_surge 전용 손익 설정 (일반보다 높은 목표 — 급등 전 진입이므로 큰 수익 기대)
    pre_surge_take_profit_targets: List[dict] = field(default_factory=lambda: [
        {"ratio": 0.08,  "volume_pct": 0.33, "name": "급등전 1차 익절 +8%"},
        {"ratio": 0.18,  "volume_pct": 0.50, "name": "급등전 2차 익절 +18%"},
        {"ratio": 0.30,  "volume_pct": 1.00, "name": "급등전 3차 익절 +30%"},
    ])
    pre_surge_stop_loss_targets: List[dict] = field(default_factory=lambda: [
        {"ratio": -0.03, "volume_pct": 0.50, "name": "급등전 1차 손절 -3%"},
        {"ratio": -0.05, "volume_pct": 1.00, "name": "급등전 2차 손절 -5%"},
    ])
    pre_surge_trailing_stop_ratio: float = -0.08  # 고점 대비 -8% (넓게 — 급등 추세 유지)
    pre_surge_max_holding_hours: int = 24 * 7     # 최대 7일 (급등 대기)


# ── 인메모리 포지션 레코드 ────────────────────────────────────

@dataclass
class PaperPosition:
    """메모리 내 오픈 포지션"""
    db_id: Optional[int]        # PaperTrade.id (DB 저장 후 할당)
    code: str
    name: str
    market: str
    entry_time: datetime
    entry_price: float
    quantity: int
    highest_price: float
    entry_score: float = 0.0
    executed_tp_targets: set = field(default_factory=set)  # 실행된 익절 단계 인덱스
    executed_sl_targets: set = field(default_factory=set)  # 실행된 손절 단계 인덱스
    dynamic_stop_price: float = 0.0  # 동적 손절가 (1차 익절 후 본전으로 이동)
    breakeven_active: bool = False    # 1차 익절 후 break-even 발동 여부
    is_presurge: bool = False         # True = 급등 전 시그널 진입 (전용 손익 설정 사용)
    # ── 저항 거래량 추적 (2순위: 저항가 근처 거래량 미달 시 익절) ──
    resistance_price: float = 0.0    # 진입 시 감지된 저항 가격대
    resistance_volume: float = 0.0   # 저항 캔들 최대 거래량 (기준값)
    # ── 신규 로직 추적 (분석용) ──────────────────────────────────
    has_cup_handle: bool = False         # 진입 시 컵앤핸들 감지 여부
    cup_handle_status: str = ""          # fresh/pre/forming
    has_candle_vol_signal: bool = False  # 버팀 진입 신호 여부
    entry_reasons: list = field(default_factory=list)  # 진입 사유 목록

    def update_highest(self, price: float):
        self.highest_price = max(self.highest_price, price)

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.entry_price) * self.quantity

    def unrealized_pnl_pct(self, current_price: float) -> float:
        return (current_price - self.entry_price) / self.entry_price * 100

    def holding_hours(self) -> float:
        now = datetime.now(timezone.utc)
        entry = self.entry_time if self.entry_time.tzinfo else self.entry_time.replace(tzinfo=timezone.utc)
        return (now - entry).total_seconds() / 3600

    def to_dict(self, current_price: Optional[float] = None) -> dict:
        pnl = self.unrealized_pnl(current_price) if current_price else None
        pnl_pct = self.unrealized_pnl_pct(current_price) if current_price else None
        return {
            "id": self.db_id,
            "code": self.code,
            "name": self.name,
            "market": self.market,
            "entry_time": self.entry_time.isoformat() + 'Z',  # UTC naive → UTC 명시
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "highest_price": self.highest_price,
            "entry_score": self.entry_score,
            "current_price": current_price,
            "unrealized_pnl": round(pnl, 0) if pnl is not None else None,
            "unrealized_pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
            "holding_hours": round(self.holding_hours(), 1),
        }


# ── 메인 엔진 (싱글턴) ───────────────────────────────────────

class PaperEngine:
    """페이퍼 트레이딩 엔진 (모듈 레벨 싱글턴으로 사용)"""

    def __init__(self):
        self.config = PaperConfig()
        self.cash: float = self.config.initial_capital
        self.is_running: bool = False
        self.open_positions: List[PaperPosition] = []
        self.closed_today: int = 0
        self._daily_start_value: float = self.config.initial_capital
        self._daily_reset_date: Optional[str] = None
        self._started_at: Optional[datetime] = None
        self._elapsed_seconds: float = 0.0

    # ── 장 시간 체크 ─────────────────────────────────────────

    def _is_market_open(self) -> bool:
        now = datetime.now(KST)
        if now.weekday() >= 5:          # 토/일 휴장
            return False
        t = now.time()
        return time(9, 0) <= t <= time(15, 20)

    # ── 포지션 관리 (backtest/engine.py 로직 이식) ──────────

    def _calculate_position_size(self, price: float) -> int:
        invest = min(
            self.config.initial_capital * self.config.position_size_pct,
            self.cash,
        )
        return int(invest / price)

    def _get_commission(self, price: float, qty: int) -> float:
        return price * qty * self.config.commission_rate

    def _can_open(self) -> bool:
        return len(self.open_positions) < self.config.max_positions

    def _already_holding(self, code: str) -> bool:
        return any(p.code == code for p in self.open_positions)

    def _passes_entry_filter(self, surge_item: dict) -> bool:
        """진입 조건 필터: 과열/동력부족/유동성 부족/고점 근접/오후 장 제외"""
        code = surge_item.get("code", "")

        # 1. 오후 13:30 이후 신규 진입 금지 (세력 분산 시간대)
        now_kst = datetime.now(KST)
        if now_kst.time() >= time(13, 30):
            logger.debug(f"[Filter] {code} 13:30 이후 진입 금지")
            return False

        change_rate = surge_item.get("change_rate", 0)
        volume = surge_item.get("volume", 0)
        price = surge_item.get("price", 0)
        high = surge_item.get("high", 0)

        # 2. 등락률 범위 필터
        if not (self.config.entry_min_change_rate <= change_rate <= self.config.entry_max_change_rate):
            logger.debug(f"[Filter] {code} 등락률 {change_rate:.1f}% 제외 "
                         f"(허용: {self.config.entry_min_change_rate}~{self.config.entry_max_change_rate}%)")
            return False

        # 3. 거래량 필터
        if volume < self.config.entry_min_volume:
            logger.debug(f"[Filter] {code} 거래량 {volume:,}주 부족 제외")
            return False

        # 4. 당일 고점 근접 매수 방지 (고점 대비 3% 이내 = 고점에서 사는 꼴)
        if high > 0 and price > 0 and (price / high) > 0.97:
            logger.debug(f"[Filter] {code} 고점 근접 제외 (현재 {price:,} / 고가 {high:,} = {price/high*100:.1f}%)")
            return False

        return True

    def _check_exit(self, pos: PaperPosition, current_price: float,
                    current_volume: float = 0.0) -> Tuple[bool, str, float]:
        """청산 조건 체크 → (should_exit, reason, volume_pct)
        volume_pct: 잔여 수량 기준 청산 비율 (1.0 = 전량)
        """
        pos.update_highest(current_price)
        ratio = (current_price - pos.entry_price) / pos.entry_price

        # 급등 전 진입 vs 일반 진입 — 전용 설정 분기
        tp_targets = self.config.pre_surge_take_profit_targets if pos.is_presurge else self.config.take_profit_targets
        sl_targets = self.config.pre_surge_stop_loss_targets if pos.is_presurge else self.config.stop_loss_targets
        trailing = self.config.pre_surge_trailing_stop_ratio if pos.is_presurge else self.config.trailing_stop_ratio
        max_hours = self.config.pre_surge_max_holding_hours if pos.is_presurge else self.config.max_holding_hours

        # 1. 분할 익절 (이미 실행된 단계는 건너뜀)
        for i, tgt in enumerate(tp_targets):
            if i in pos.executed_tp_targets:
                continue
            if ratio >= tgt["ratio"]:
                pos.executed_tp_targets.add(i)
                return True, tgt["name"], tgt["volume_pct"]

        # 1-b. 저항 거래량 미달 익절 (이미지 ⑤ 로직)
        #   - 수익 구간 (+1% 이상)에서만 발동 (손실 중에는 적용 안 함)
        #   - 저항가 ±3% 이내 도달 + 현재 거래량이 저항 거래량의 70% 미만
        #   - → 돌파 실패 가능성 높음 → 부분 익절 (1/2)
        if (ratio >= 0.01
                and pos.resistance_price > 0
                and pos.resistance_volume > 0
                and current_volume > 0):
            near_res = abs(current_price - pos.resistance_price) / pos.resistance_price < 0.03
            vol_weak = current_volume < pos.resistance_volume * 0.70
            if near_res and vol_weak:
                logger.info(
                    f"[Paper] {pos.code} 저항가 근처({pos.resistance_price:,.0f}) + "
                    f"거래량 미달({current_volume:.0f} < {pos.resistance_volume * 0.70:.0f}) → 저항 익절"
                )
                return True, "저항거래량미달_익절", 0.5

        # 2. 손절 분기
        if pos.breakeven_active:
            # Phase B: 1차 익절 후 → break-even 손절 전량
            stop_ratio = (pos.dynamic_stop_price - pos.entry_price) / pos.entry_price
            if ratio <= stop_ratio:
                return True, "손절(본전)", 1.0
        else:
            # Phase A: 1차 익절 전 → 분할 손절
            for i, sl in enumerate(sl_targets):
                if i in pos.executed_sl_targets:
                    continue
                if ratio <= sl["ratio"]:
                    pos.executed_sl_targets.add(i)
                    return True, sl["name"], sl["volume_pct"]

        # 3. 트레일링 스톱 (최고가 경신 후 하락 시)
        trail_threshold = pos.highest_price * (1 + trailing)
        if current_price <= trail_threshold and pos.highest_price > pos.entry_price:
            return True, "trailing_stop", 1.0

        # 4. 최대 보유 시간
        if pos.holding_hours() >= max_hours:
            return True, f"time_limit_{max_hours}h", 1.0

        return False, "", 0.0

    # ── 현재가 조회 ──────────────────────────────────────────

    async def _get_current_price(self, code: str, market: str) -> Optional[float]:
        price, _ = await self._get_current_price_and_volume(code, market)
        return price

    async def _get_current_price_and_volume(self, code: str, market: str) -> tuple[Optional[float], float]:
        """현재가 + 최근 분봉 거래량 반환 (price, volume)"""
        try:
            if market == "KR":
                from ..kis.rest_client import get_kis_client
                candles = await get_kis_client().get_minute_chart(code)
                if candles:
                    return float(candles[-1]["close"]), float(candles[-1].get("volume", 0))
            else:
                import yfinance as yf
                ticker = yf.Ticker(f"{code}")
                hist = ticker.history(period="1d", interval="1m")
                if not hist.empty:
                    return float(hist["Close"].iloc[-1]), float(hist["Volume"].iloc[-1])
        except Exception as e:
            logger.warning(f"[Paper] 현재가 조회 실패 {code}: {e}")
        return None, 0.0

    # ── DB 저장/복원 ─────────────────────────────────────────

    async def load_from_db(self, db: AsyncSession) -> None:
        """서버 시작 시 DB에서 상태 복원"""
        from ..db.models import PaperAccount, PaperTrade
        try:
            acc = await db.get(PaperAccount, 1)
            if acc:
                self.config.initial_capital = acc.initial_capital
                self.config.market = acc.market
                self.config.strategy = acc.strategy
                self.config.min_score = acc.min_score
                self.config.max_positions = acc.max_positions
                self.config.position_size_pct = acc.position_size_pct
                self.cash = acc.cash
                self.is_running = acc.is_running

            # 오픈 포지션 복원
            result = await db.execute(
                select(PaperTrade).where(PaperTrade.status == "OPEN")
            )
            rows = result.scalars().all()
            self.open_positions = [
                PaperPosition(
                    db_id=r.id,
                    code=r.code,
                    name=r.name,
                    market=r.market,
                    entry_time=r.entry_time,
                    entry_price=r.entry_price,
                    quantity=r.quantity,
                    highest_price=r.highest_price,
                    entry_score=r.entry_score,
                    dynamic_stop_price=r.entry_price * (1 + self.config.stop_loss_ratio),
                )
                for r in rows
            ]
            logger.info(f"[Paper] DB 복원: cash={self.cash:,.0f}, positions={len(self.open_positions)}, running={self.is_running}")
        except Exception as e:
            logger.error(f"[Paper] DB 복원 실패: {e}")

    async def _save_account(self, db: AsyncSession) -> None:
        from ..db.models import PaperAccount
        from datetime import timezone
        acc = await db.get(PaperAccount, 1)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if acc is None:
            acc = PaperAccount(id=1)
            db.add(acc)
        acc.initial_capital = self.config.initial_capital
        acc.cash = self.cash
        acc.is_running = self.is_running
        acc.market = self.config.market
        acc.strategy = self.config.strategy
        acc.min_score = self.config.min_score
        acc.max_positions = self.config.max_positions
        acc.position_size_pct = self.config.position_size_pct
        acc.updated_at = now
        await db.commit()

    async def _save_open_position(self, pos: PaperPosition, db: AsyncSession) -> None:
        import json
        from ..db.models import PaperTrade
        row = PaperTrade(
            code=pos.code,
            name=pos.name,
            market=pos.market,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            quantity=pos.quantity,
            highest_price=pos.highest_price,
            entry_score=pos.entry_score,
            status="OPEN",
            is_presurge=pos.is_presurge,
            has_cup_handle=pos.has_cup_handle,
            cup_handle_status=pos.cup_handle_status or None,
            has_candle_vol_signal=pos.has_candle_vol_signal,
            resistance_price=pos.resistance_price,
            resistance_volume=pos.resistance_volume,
            entry_reasons_json=json.dumps(pos.entry_reasons, ensure_ascii=False) if pos.entry_reasons else None,
        )
        db.add(row)
        await db.flush()        # id 할당
        pos.db_id = row.id
        await db.commit()

    async def _close_position_in_db(self, pos: PaperPosition, exit_price: float,
                                    exit_reason: str, db: AsyncSession) -> None:
        from ..db.models import PaperTrade
        from datetime import timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        pl = (exit_price - pos.entry_price) * pos.quantity
        pl_pct = (exit_price - pos.entry_price) / pos.entry_price * 100
        if pos.db_id:
            row = await db.get(PaperTrade, pos.db_id)
            if row:
                row.status = "CLOSED"
                row.exit_time = now
                row.exit_price = exit_price
                row.exit_reason = exit_reason
                row.profit_loss = round(pl, 2)
                row.profit_loss_pct = round(pl_pct, 2)
                row.highest_price = pos.highest_price
        await db.commit()

    async def _record_portfolio(self, db: AsyncSession, current_prices: dict) -> None:
        from ..db.models import PaperPortfolioHistory
        from datetime import timezone
        pos_value = sum(
            current_prices.get(p.code, p.entry_price) * p.quantity
            for p in self.open_positions
        )
        row = PaperPortfolioHistory(
            recorded_at=datetime.now(timezone.utc).replace(tzinfo=None),
            total_value=round(self.cash + pos_value, 2),
            cash=round(self.cash, 2),
            position_value=round(pos_value, 2),
        )
        db.add(row)
        await db.commit()

    # ── 메인 루프 (5분마다 호출) ─────────────────────────────

    async def tick(self, db: AsyncSession) -> None:
        """신호 스캔 → 진입/청산 → DB 저장"""
        if not self._is_market_open():
            logger.info("[Paper] 장 시간 외 — tick 스킵")
            return

        current_prices: dict = {}

        # 1. 오픈 포지션 청산 체크
        for pos in self.open_positions[:]:
            price, cur_vol = await self._get_current_price_and_volume(pos.code, pos.market)
            if price is None:
                continue
            current_prices[pos.code] = price
            should_exit, reason, volume_pct = self._check_exit(pos, price, cur_vol)
            if should_exit:
                await self._do_close(pos, price, reason, volume_pct, db)

        # 2. 신규 진입 스캔
        if self._can_open():
            if self.config.pre_surge_mode:
                await self._scan_and_buy_presurge(db, current_prices)
            else:
                await self._scan_and_buy(db, current_prices)

        # 3. 포트폴리오 기록
        await self._record_portfolio(db, current_prices)
        await self._save_account(db)

    async def _do_close(self, pos: PaperPosition, price: float, reason: str,
                        volume_pct: float, db: AsyncSession) -> None:
        """청산 실행 (volume_pct < 1.0이면 부분 청산, 잔여 수량 기준)"""
        close_qty = pos.quantity if volume_pct >= 1.0 else max(1, int(pos.quantity * volume_pct))
        close_qty = min(close_qty, pos.quantity)

        commission = self._get_commission(price, close_qty)
        self.cash += price * close_qty - commission

        pl_pct = (price - pos.entry_price) / pos.entry_price * 100
        is_full = (close_qty >= pos.quantity)

        if is_full:
            self.open_positions.remove(pos)
            self.closed_today += 1
            logger.info(f"[Paper] CLOSE {pos.code} x{close_qty} @ {price:,.0f}원 ({pl_pct:+.2f}%) — {reason}")
            await self._close_position_in_db(pos, price, reason, db)
        else:
            pos.quantity -= close_qty
            # TP 부분청산일 때만 break-even 이동 (SL 부분청산은 이동 안 함)
            tp_names = {tgt["name"] for tgt in self.config.take_profit_targets}
            if reason in tp_names and not pos.breakeven_active:
                pos.dynamic_stop_price = max(pos.dynamic_stop_price, pos.entry_price)
                pos.breakeven_active = True
                logger.info(f"[Paper] PARTIAL(TP) {pos.code} x{close_qty} → 잔여 x{pos.quantity} @ {price:,.0f}원 ({pl_pct:+.2f}%) — {reason} | 손절가 → 본전")
            else:
                logger.info(f"[Paper] PARTIAL(SL) {pos.code} x{close_qty} → 잔여 x{pos.quantity} @ {price:,.0f}원 ({pl_pct:+.2f}%) — {reason}")
            await self._record_partial_close(pos, price, reason, close_qty, pl_pct, db)

    async def _record_partial_close(self, pos: PaperPosition, price: float, reason: str,
                                    qty: int, pl_pct: float, db: AsyncSession) -> None:
        """부분 익절 기록: CLOSED 행 신규 생성 + OPEN 행 수량 업데이트"""
        from ..db.models import PaperTrade
        from datetime import timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        pl = (price - pos.entry_price) * qty
        # 부분 체결 내역 저장 (별도 CLOSED 레코드)
        row = PaperTrade(
            code=pos.code,
            name=pos.name,
            market=pos.market,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            quantity=qty,
            highest_price=pos.highest_price,
            entry_score=pos.entry_score,
            status="CLOSED",
            exit_time=now,
            exit_price=price,
            exit_reason=reason,
            profit_loss=round(pl, 2),
            profit_loss_pct=round(pl_pct, 2),
        )
        db.add(row)
        # OPEN 행 수량·최고가 업데이트 (서버 재시작 시 정확하게 복원)
        if pos.db_id:
            open_row = await db.get(PaperTrade, pos.db_id)
            if open_row:
                open_row.quantity = pos.quantity
                open_row.highest_price = pos.highest_price
        await db.commit()

    async def _check_minute_breakout(self, code: str) -> tuple:
        """분봉 진입 타이밍 신호 확인 (단타 진입 + 스윙 홀딩).

        Returns:
            (진입 가능 여부: bool, 분봉 신호 dict)
        """
        from ..kis.rest_client import get_kis_client
        from .signals import MinuteBreakoutSignal
        try:
            candles = await get_kis_client().get_minute_chart(code)
            if not candles:
                logger.debug(f"[Paper] {code} 분봉 데이터 없음 — 일봉 신호로만 진입")
                return True, {}
            result = MinuteBreakoutSignal().check_signal(candles)
            ok = result["signal"] == "BUY"
            if ok:
                logger.info(
                    f"[Paper] {code} 분봉 진입 확인 score={result['score']} "
                    f"intraday={result.get('intraday_change', 0):+.1f}% "
                    f"| {result['reasons']}"
                )
            else:
                logger.debug(
                    f"[Paper] {code} 분봉 신호 미확인 score={result['score']} — 진입 보류 "
                    f"| {result['reasons']}"
                )
            return ok, result
        except Exception as e:
            logger.warning(f"[Paper] {code} 분봉 확인 실패: {e} — 일봉 신호로 진입")
            return True, {}

    async def _scan_and_buy(self, db: AsyncSession, current_prices: dict) -> None:
        from .signal_service import generate_entry_signals_bulk
        from ..kis.rest_client import get_kis_client

        try:
            surge = await get_kis_client().get_volume_rank(limit=50)
            name_map = {s["code"]: s.get("name", "") for s in surge}
            codes = [
                s["code"] for s in surge
                if not self._already_holding(s["code"]) and self._passes_entry_filter(s)
            ]
            if not codes:
                return

            signals = await generate_entry_signals_bulk(
                codes[:30], self.config.market, self.config.strategy, self.config.min_score
            )

            for sig in signals:
                if not self._can_open():
                    break
                if self._already_holding(sig["code"]):
                    continue
                price = sig.get("current_price") or current_prices.get(sig["code"])
                if not price:
                    continue

                # ── 분봉 진입 타이밍 확인 (단타 진입 + 스윙 홀딩) ──────────
                minute_ok, minute_sig = await self._check_minute_breakout(sig["code"])
                if not minute_ok:
                    continue

                sig["_name"] = name_map.get(sig["code"], sig["code"])
                if minute_sig:
                    sig["_minute_signal"] = minute_sig
                await self._do_open(sig, price, db)

        except Exception as e:
            logger.error(f"[Paper] 신호 스캔 오류: {e}")

    async def _scan_and_buy_presurge(self, db: AsyncSession, current_prices: dict) -> None:
        """급등 전 시그널 기반 진입 스캔 (pre_surge_mode=True 전용)

        거래량 상위 100종목 중 dryup_recovery / seoryuk / tight_consolidation 감지 시 진입.
        chase_blocked (당일 +5%↑) 종목은 건너뜀 — 이미 급등 완료로 판단.
        """
        from .signal_service import generate_entry_signal, collect_ohlcv_data
        from ..kis.rest_client import get_kis_client
        import asyncio

        try:
            surge = await get_kis_client().get_volume_rank(limit=100)
        except Exception as e:
            logger.error(f"[Paper][PreSurge] 거래량 상위 조회 실패: {e}")
            return

        name_map = {s["code"]: s.get("name", "") for s in surge}
        # 거래량 최소치만 적용 (등락률 필터는 해제 — 아직 안 움직인 종목을 잡기 위해)
        candidates = [
            s["code"] for s in surge
            if not self._already_holding(s["code"])
            and s.get("volume", 0) >= self.config.entry_min_volume
        ]
        if not candidates:
            return

        semaphore = asyncio.Semaphore(4)

        async def _check_presurge(code: str):
            async with semaphore:
                try:
                    sig = await generate_entry_signal(code, self.config.market, self.config.strategy)
                    # 추격차단: 당일 이미 급등한 종목 건너뜀
                    if sig.get("chase_blocked") or sig.get("breakdown", {}).get("chase_blocked"):
                        return None
                    pattern = sig.get("breakdown", {}).get("pattern", {})
                    ps = pattern.get("pre_surge") or {}
                    dr = ps.get("dryup_recovery", {})
                    se = ps.get("seoryuk", {})
                    tc = ps.get("tight_consol", {})
                    if dr.get("detected") or se.get("detected") or tc.get("detected"):
                        sig["_pre_surge"] = ps
                        sig["_name"] = name_map.get(code, code)
                        return sig
                    return None
                except Exception as e:
                    logger.debug(f"[Paper][PreSurge] {code} 분석 실패: {e}")
                    return None

        tasks = [_check_presurge(c) for c in candidates[:50]]
        results = await asyncio.gather(*tasks)
        hits = [r for r in results if r is not None]

        # 점수 높은 순 진입
        hits.sort(key=lambda x: x.get("score", 0), reverse=True)
        for sig in hits:
            if not self._can_open():
                break
            if self._already_holding(sig["code"]):
                continue
            price = sig.get("current_price") or current_prices.get(sig["code"])
            if not price:
                continue
            ps = sig["_pre_surge"]
            tags = []
            if ps.get("dryup_recovery", {}).get("detected"):
                tags.append(f"건조회복({ps['dryup_recovery']['dryup_days']}일)")
            if ps.get("seoryuk", {}).get("detected"):
                tags.append(f"세력매집(x{ps['seoryuk']['spike_ratio']:.1f})")
            if ps.get("tight_consol", {}).get("detected"):
                tags.append(f"압축횡보({ps['tight_consol']['range_pct']:.1f}%)")
            logger.info(f"[Paper][PreSurge] 진입 {sig['code']} {sig['_name']} @ {price:,.0f} | {' · '.join(tags)}")
            await self._do_open(sig, price, db, is_presurge=True)

    async def _do_open(self, signal: dict, price: float, db: AsyncSession, is_presurge: bool = False) -> None:
        qty = self._calculate_position_size(price)
        if qty <= 0:
            return
        cost = price * qty + self._get_commission(price, qty)
        if cost > self.cash:
            return

        self.cash -= cost
        from datetime import timezone
        sl_ratio = self.config.pre_surge_stop_loss_targets[1]["ratio"] if is_presurge else self.config.stop_loss_ratio

        # 진입 시그널에서 저항 거래량/가격 추출 (캔들 해부 분석 결과)
        candle_vol = (
            signal.get("breakdown", {}).get("pattern", {}).get("candle_volume")
            or signal.get("candle_volume")
            or {}
        )
        res_price  = float(candle_vol.get("resistance_price", 0) or 0)
        res_volume = float(candle_vol.get("max_resistance_volume", 0) or 0)

        # 컵앤핸들 / 캔들 버팀 신호 추적
        cup_handle_data = (
            signal.get("cup_handle")
            or signal.get("breakdown", {}).get("pattern", {}).get("cup_handle")
            or {}
        )
        ch_status = cup_handle_data.get("breakout_status", "") if cup_handle_data else ""
        has_ch = bool(cup_handle_data.get("score", 0) >= 40) if cup_handle_data else False
        has_cv = bool(candle_vol.get("entry_signal", False))

        pos = PaperPosition(
            db_id=None,
            code=signal["code"],
            name=signal.get("_name") or signal.get("stock_info", {}).get("name") or signal["code"],
            market=self.config.market,
            entry_time=datetime.now(timezone.utc).replace(tzinfo=None),
            entry_price=price,
            quantity=qty,
            highest_price=price,
            entry_score=signal.get("score", 0.0),
            dynamic_stop_price=price * (1 + sl_ratio),
            is_presurge=is_presurge,
            resistance_price=res_price,
            resistance_volume=res_volume,
            has_cup_handle=has_ch,
            cup_handle_status=ch_status,
            has_candle_vol_signal=has_cv,
            entry_reasons=signal.get("reasons", []),
        )
        self.open_positions.append(pos)
        res_info = f" | 저항가={res_price:,.0f} 저항거래량={res_volume:.0f}" if res_price > 0 else ""
        logger.info(f"[Paper] BUY {pos.code} x{qty} @ {price:,.0f}원 (score={pos.entry_score:.0f}){res_info}")
        await self._save_open_position(pos, db)

    # ── 외부 제어 ────────────────────────────────────────────

    async def start(self, config: dict, db: AsyncSession) -> None:
        self.config.initial_capital = config.get("initial_capital", self.config.initial_capital)
        self.config.market = config.get("market", self.config.market)
        self.config.strategy = config.get("strategy", self.config.strategy)
        self.config.min_score = config.get("min_score", self.config.min_score)
        self.config.max_positions = config.get("max_positions", self.config.max_positions)
        self.config.position_size_pct = config.get("position_size_pct", self.config.position_size_pct)
        self.config.pre_surge_mode = config.get("pre_surge_mode", self.config.pre_surge_mode)
        # 첫 시작이면 현금 초기화
        if not self.is_running and not self.open_positions:
            self.cash = self.config.initial_capital
        self.is_running = True
        from datetime import timezone
        self._started_at = datetime.now(timezone.utc)
        await self._save_account(db)
        logger.info(f"[Paper] 시뮬레이션 시작: capital={self.config.initial_capital:,.0f}, market={self.config.market}")

    async def stop(self, db: AsyncSession) -> None:
        self.is_running = False
        if self._started_at:
            from datetime import timezone
            self._elapsed_seconds += (datetime.now(timezone.utc) - self._started_at).total_seconds()
            self._started_at = None
        await self._save_account(db)
        logger.info("[Paper] 시뮬레이션 중지")

    async def reset(self, db: AsyncSession) -> None:
        from ..db.models import PaperTrade, PaperPortfolioHistory
        self.is_running = False
        self._started_at = None
        self._elapsed_seconds = 0.0
        self.open_positions = []
        self.cash = self.config.initial_capital
        self.closed_today = 0
        await db.execute(delete(PaperTrade))
        await db.execute(delete(PaperPortfolioHistory))
        await db.commit()
        await self._save_account(db)
        logger.info("[Paper] 시뮬레이션 초기화")

    # ── 조회 ─────────────────────────────────────────────────

    def get_status(self) -> dict:
        pos_value = sum(p.entry_price * p.quantity for p in self.open_positions)
        total_value = self.cash + pos_value
        roi = (total_value - self.config.initial_capital) / self.config.initial_capital * 100
        return {
            "is_running": self.is_running,
            "market": self.config.market,
            "strategy": self.config.strategy,
            "min_score": self.config.min_score,
            "max_positions": self.config.max_positions,
            "pre_surge_mode": self.config.pre_surge_mode,
            "initial_capital": self.config.initial_capital,
            "cash": round(self.cash, 0),
            "position_value": round(pos_value, 0),
            "total_value": round(total_value, 0),
            "roi": round(roi, 2),
            "open_count": len(self.open_positions),
            "closed_today": self.closed_today,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "elapsed_seconds": int(self._elapsed_seconds),
        }

    def get_positions(self) -> list:
        return [p.to_dict() for p in self.open_positions]

    async def open_position_manually(self, code: str, name: str, entry_price: float,
                                     quantity: int, db: AsyncSession) -> dict:
        """수동 포지션 추가.

        Args:
            quantity: 0이면 config 기준으로 자동 계산
        Raises:
            ValueError: 포지션 한도 초과 / 현금 부족 / 수량 0
        """
        from datetime import timezone

        if not self._can_open():
            raise ValueError(f"최대 포지션 수({self.config.max_positions})에 도달했습니다")

        qty = quantity if quantity > 0 else self._calculate_position_size(entry_price)
        if qty <= 0:
            raise ValueError("수량이 0입니다. 진입가나 현금 잔액을 확인하세요")

        cost = entry_price * qty + self._get_commission(entry_price, qty)
        if cost > self.cash:
            raise ValueError(f"현금 부족 (필요: {cost:,.0f}원, 보유: {self.cash:,.0f}원)")

        self.cash -= cost
        pos = PaperPosition(
            db_id=None,
            code=code,
            name=name or code,
            market=self.config.market,
            entry_time=datetime.now(timezone.utc).replace(tzinfo=None),
            entry_price=entry_price,
            quantity=qty,
            highest_price=entry_price,
            entry_score=0.0,
            dynamic_stop_price=entry_price * (1 + self.config.stop_loss_ratio),
        )
        self.open_positions.append(pos)
        logger.info(f"[Paper] MANUAL BUY {pos.code} x{qty} @ {entry_price:,.0f}원")
        await self._save_open_position(pos, db)
        await self._save_account(db)
        return pos.to_dict()

    async def close_all_positions(self, db: AsyncSession) -> list:
        """전체 포지션 일괄 청산 — 각 종목 현재가(조회 실패 시 진입가)로 즉시 전량 청산"""
        results = []
        for pos in self.open_positions[:]:
            price = await self._get_current_price(pos.code, pos.market)
            if price is None:
                price = pos.entry_price
            await self._do_close(pos, price, "일괄청산", 1.0, db)
            results.append({"code": pos.code, "price": price, "reason": "일괄청산"})
        await self._save_account(db)
        return results

    async def close_position_manually(self, code: str, db: AsyncSession) -> Optional[dict]:
        """수동 강제 청산 — 현재가(조회 실패 시 진입가)로 즉시 전량 청산"""
        pos = next((p for p in self.open_positions if p.code == code), None)
        if pos is None:
            return None
        price = await self._get_current_price(pos.code, pos.market)
        if price is None:
            price = pos.entry_price  # 현재가 조회 실패 시 진입가로 처리
        await self._do_close(pos, price, "수동청산", 1.0, db)
        await self._save_account(db)
        return {"code": code, "price": price, "reason": "수동청산"}

    async def get_trades(self, db: AsyncSession, limit: int = 50) -> list:
        from ..db.models import PaperTrade
        result = await db.execute(
            select(PaperTrade)
            .where(PaperTrade.status == "CLOSED")
            .order_by(PaperTrade.exit_time.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "market": r.market,
                "entry_time": (r.entry_time.isoformat() + 'Z') if r.entry_time else None,
                "entry_price": r.entry_price,
                "highest_price": r.highest_price,
                "exit_time": (r.exit_time.isoformat() + 'Z') if r.exit_time else None,
                "exit_price": r.exit_price,
                "exit_reason": r.exit_reason,
                "quantity": r.quantity,
                "profit_loss": r.profit_loss,
                "profit_loss_pct": r.profit_loss_pct,
                "entry_score": r.entry_score,
                "status": r.status,
            }
            for r in rows
        ]

    async def get_journal(
        self,
        db: AsyncSession,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        code: Optional[str] = None,
        profit_type: str = "all",  # all | profit | loss
        limit: int = 200,
        offset: int = 0,
    ) -> dict:
        """투자일지 조회 — 날짜·종목·수익여부 필터 지원"""
        from ..db.models import PaperTrade

        filters = [PaperTrade.status == "CLOSED"]

        if date_from:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            filters.append(PaperTrade.exit_time >= dt_from)
        if date_to:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            filters.append(PaperTrade.exit_time <= dt_to)
        if code:
            kw = f"%{code}%"
            filters.append(or_(PaperTrade.code.ilike(kw), PaperTrade.name.ilike(kw)))
        if profit_type == "profit":
            filters.append(PaperTrade.profit_loss > 0)
        elif profit_type == "loss":
            filters.append(PaperTrade.profit_loss <= 0)

        where_clause = and_(*filters)

        # 요약 집계
        sum_q = await db.execute(
            select(
                func.count(PaperTrade.id).label("total"),
                func.coalesce(func.sum(PaperTrade.profit_loss), 0).label("total_pnl"),
            ).where(where_clause)
        )
        summary = sum_q.one()

        profit_q = await db.execute(
            select(
                func.count(PaperTrade.id).label("cnt"),
                func.coalesce(func.sum(PaperTrade.profit_loss), 0).label("amount"),
            ).where(and_(where_clause, PaperTrade.profit_loss > 0))
        )
        profit_row = profit_q.one()
        profit_cnt = profit_row.cnt or 0
        profit_amount = float(profit_row.amount or 0)

        loss_q = await db.execute(
            select(
                func.count(PaperTrade.id).label("cnt"),
                func.coalesce(func.sum(PaperTrade.profit_loss), 0).label("amount"),
            ).where(and_(where_clause, PaperTrade.profit_loss <= 0))
        )
        loss_row = loss_q.one()
        loss_cnt = loss_row.cnt or 0
        loss_amount = float(loss_row.amount or 0)

        # 페이지네이션 거래 목록
        rows_q = await db.execute(
            select(PaperTrade)
            .where(where_clause)
            .order_by(PaperTrade.exit_time.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = rows_q.scalars().all()

        trades = [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "market": r.market,
                "entry_time": (r.entry_time.isoformat() + 'Z') if r.entry_time else None,
                "entry_price": r.entry_price,
                "exit_time": (r.exit_time.isoformat() + 'Z') if r.exit_time else None,
                "exit_price": r.exit_price,
                "exit_reason": r.exit_reason,
                "quantity": r.quantity,
                "profit_loss": r.profit_loss,
                "profit_loss_pct": r.profit_loss_pct,
            }
            for r in rows
        ]

        return {
            "trades": trades,
            "total": summary.total or 0,
            "total_pnl": float(summary.total_pnl or 0),
            "profit_count": profit_cnt,
            "profit_amount": profit_amount,
            "loss_count": loss_cnt,
            "loss_amount": loss_amount,
        }

    async def get_history(self, db: AsyncSession, limit: int = 200) -> list:
        from ..db.models import PaperPortfolioHistory
        result = await db.execute(
            select(PaperPortfolioHistory)
            .order_by(PaperPortfolioHistory.recorded_at.asc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "recorded_at": (r.recorded_at.isoformat() + 'Z') if r.recorded_at else None,
                "total_value": r.total_value,
                "cash": r.cash,
                "position_value": r.position_value,
            }
            for r in rows
        ]


# ── 싱글턴 인스턴스 ──────────────────────────────────────────
paper_engine = PaperEngine()
