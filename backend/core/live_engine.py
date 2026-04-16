"""
Live Trading Engine — KIS 실전 자동매매
실제 주문을 KIS API로 제출하고 체결을 확인한다.

⚠️  실제 자금이 사용됩니다. LIVE_TRADING_ENABLED=true 환경변수가 있어야 동작합니다.
"""
import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
except ImportError:
    import pytz
    KST = pytz.timezone("Asia/Seoul")


# ── 설정 ──────────────────────────────────────────────────────

@dataclass
class LiveConfig:
    max_positions: int = 2
    position_size_pct: float = 0.15       # 종목당 15%
    min_score: float = 65.0
    strategy: str = "combined"
    market: str = "KR"
    stop_loss_ratio: float = -0.04
    trailing_stop_ratio: float = -0.05
    take_profit_targets: List[dict] = field(default_factory=lambda: [
        {"ratio": 0.03, "volume_pct": 0.33, "name": "1차 익절 +3%"},
        {"ratio": 0.07, "volume_pct": 0.50, "name": "2차 익절 +7%"},
        {"ratio": 0.12, "volume_pct": 1.00, "name": "3차 익절 +12%"},
    ])
    stop_loss_targets: List[dict] = field(default_factory=lambda: [
        {"ratio": -0.02, "volume_pct": 0.50, "name": "1차 손절 -2%"},
        {"ratio": -0.04, "volume_pct": 1.00, "name": "2차 손절 -4%"},
    ])
    pre_surge_take_profit_targets: List[dict] = field(default_factory=lambda: [
        {"ratio": 0.08,  "volume_pct": 0.33, "name": "급등전 1차 익절 +8%"},
        {"ratio": 0.18,  "volume_pct": 0.50, "name": "급등전 2차 익절 +18%"},
        {"ratio": 0.30,  "volume_pct": 1.00, "name": "급등전 3차 익절 +30%"},
    ])
    pre_surge_stop_loss_targets: List[dict] = field(default_factory=lambda: [
        {"ratio": -0.03, "volume_pct": 0.50, "name": "급등전 1차 손절 -3%"},
        {"ratio": -0.05, "volume_pct": 1.00, "name": "급등전 2차 손절 -5%"},
    ])
    pre_surge_trailing_stop_ratio: float = -0.08
    pre_surge_max_holding_hours: int = 24 * 7
    entry_min_change_rate: float = 3.0
    entry_max_change_rate: float = 15.0
    entry_min_volume: int = 100_000
    max_holding_hours: int = 24 * 5
    commission_rate: float = 0.00015      # 0.015% (실전 수수료)
    sell_tax_rate: float = 0.0020         # 0.20% 증권거래세
    daily_loss_limit: float = -0.03       # 일일 손실 -3% 초과 시 매수 중단
    pre_surge_mode: bool = False
    order_timeout_sec: int = 30           # 주문 체결 대기 최대 시간(초)


# ── 인메모리 포지션 ────────────────────────────────────────────

@dataclass
class LivePosition:
    db_id: Optional[int]
    code: str
    name: str
    market: str
    entry_time: datetime
    entry_price: float
    quantity: int
    highest_price: float
    entry_score: float = 0.0
    entry_order_no: str = ""
    executed_tp_targets: set = field(default_factory=set)
    executed_sl_targets: set = field(default_factory=set)
    dynamic_stop_price: float = 0.0
    breakeven_active: bool = False
    is_presurge: bool = False

    def update_highest(self, price: float):
        self.highest_price = max(self.highest_price, price)

    def holding_hours(self) -> float:
        from datetime import timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return (now - self.entry_time).total_seconds() / 3600

    def to_dict(self, current_price: float = 0) -> dict:
        pnl_pct = (current_price - self.entry_price) / self.entry_price * 100 if current_price else None
        return {
            "db_id":        self.db_id,
            "code":         self.code,
            "name":         self.name,
            "entry_price":  self.entry_price,
            "quantity":     self.quantity,
            "highest_price": self.highest_price,
            "entry_score":  self.entry_score,
            "is_presurge":  self.is_presurge,
            "holding_hours": round(self.holding_hours(), 1),
            "current_price": current_price,
            "unrealized_pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
        }


# ── 메인 엔진 ─────────────────────────────────────────────────

class LiveEngine:
    """KIS 실전 자동매매 엔진 (싱글턴)"""

    def __init__(self):
        self.config = LiveConfig()
        self.is_running: bool = False
        self.open_positions: List[LivePosition] = []
        self._started_at: Optional[datetime] = None
        self._daily_start_value: float = 0.0
        self._daily_reset_date: Optional[str] = None
        self._enabled = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"

    # ── 안전 체크 ──────────────────────────────────────────────

    def _assert_enabled(self):
        if not self._enabled:
            raise RuntimeError("실전 매매가 비활성화 상태입니다. LIVE_TRADING_ENABLED=true 설정 필요")

    def _is_market_open(self) -> bool:
        now = datetime.now(KST)
        if now.weekday() >= 5:
            return False
        t = now.time()
        return time(9, 0) <= t <= time(15, 20)

    def _can_open(self) -> bool:
        return len(self.open_positions) < self.config.max_positions

    def _already_holding(self, code: str) -> bool:
        return any(p.code == code for p in self.open_positions)

    def _passes_entry_filter(self, surge_item: dict) -> bool:
        code = surge_item.get("code", "")
        now_kst = datetime.now(KST)
        if now_kst.time() >= time(13, 30):
            return False
        change_rate = surge_item.get("change_rate", 0)
        volume = surge_item.get("volume", 0)
        price = surge_item.get("price", 0)
        high = surge_item.get("high", 0)
        if not (self.config.entry_min_change_rate <= change_rate <= self.config.entry_max_change_rate):
            return False
        if volume < self.config.entry_min_volume:
            return False
        if high > 0 and price > 0 and (price / high) > 0.97:
            logger.debug(f"[Live][Filter] {code} 고점 근접 제외")
            return False
        return True

    def _check_exit(self, pos: LivePosition, current_price: float) -> Tuple[bool, str, float]:
        pos.update_highest(current_price)
        ratio = (current_price - pos.entry_price) / pos.entry_price

        tp_targets = self.config.pre_surge_take_profit_targets if pos.is_presurge else self.config.take_profit_targets
        sl_targets = self.config.pre_surge_stop_loss_targets if pos.is_presurge else self.config.stop_loss_targets
        trailing   = self.config.pre_surge_trailing_stop_ratio if pos.is_presurge else self.config.trailing_stop_ratio
        max_hours  = self.config.pre_surge_max_holding_hours if pos.is_presurge else self.config.max_holding_hours

        for i, tgt in enumerate(tp_targets):
            if i in pos.executed_tp_targets:
                continue
            if ratio >= tgt["ratio"]:
                pos.executed_tp_targets.add(i)
                return True, tgt["name"], tgt["volume_pct"]

        if pos.breakeven_active:
            stop_ratio = (pos.dynamic_stop_price - pos.entry_price) / pos.entry_price
            if ratio <= stop_ratio:
                return True, "손절(본전)", 1.0
        else:
            for i, sl in enumerate(sl_targets):
                if i in pos.executed_sl_targets:
                    continue
                if ratio <= sl["ratio"]:
                    pos.executed_sl_targets.add(i)
                    return True, sl["name"], sl["volume_pct"]

        trail_threshold = pos.highest_price * (1 + trailing)
        if current_price <= trail_threshold and pos.highest_price > pos.entry_price:
            return True, "trailing_stop", 1.0

        if pos.holding_hours() >= max_hours:
            return True, f"time_limit_{max_hours}h", 1.0

        return False, "", 0.0

    # ── 현재가 조회 ────────────────────────────────────────────

    async def _get_current_price(self, code: str) -> Optional[float]:
        try:
            from ..kis.rest_client import get_kis_client
            candles = await get_kis_client().get_minute_chart(code)
            if candles:
                return float(candles[-1]["close"])
        except Exception as e:
            logger.warning(f"[Live] 현재가 조회 실패 {code}: {e}")
        return None

    # ── 주문 실행 (매수) ───────────────────────────────────────

    async def _place_buy_and_wait(self, code: str, qty: int) -> Optional[dict]:
        """시장가 매수 → 체결 확인 (최대 order_timeout_sec 대기)
        Returns: {"filled_qty": int, "avg_price": float} or None
        """
        from ..kis.rest_client import get_kis_order_client
        client = get_kis_order_client()
        try:
            order = await client.place_buy_order(code, qty, price=0)
            order_no = order["order_no"]
        except Exception as e:
            logger.error(f"[Live] 매수 주문 실패 {code}: {e}")
            return None

        # 체결 대기
        for _ in range(self.config.order_timeout_sec // 3):
            await asyncio.sleep(3)
            try:
                status = await client.get_order_status(order_no)
                if status["filled"] and status["filled_qty"] > 0:
                    return {
                        "order_no":   order_no,
                        "filled_qty": status["filled_qty"],
                        "avg_price":  status["avg_price"],
                    }
            except Exception as e:
                logger.warning(f"[Live] 체결확인 실패 {code}: {e}")

        logger.warning(f"[Live] 매수 체결 타임아웃 {code} — 주문취소 시도")
        try:
            await client.cancel_order(order_no, code, qty)
        except Exception:
            pass
        return None

    # ── 주문 실행 (매도) ───────────────────────────────────────

    async def _place_sell_and_wait(self, code: str, qty: int) -> Optional[dict]:
        from ..kis.rest_client import get_kis_order_client
        client = get_kis_order_client()
        try:
            order = await client.place_sell_order(code, qty, price=0)
            order_no = order["order_no"]
        except Exception as e:
            logger.error(f"[Live] 매도 주문 실패 {code}: {e}")
            return None

        for _ in range(self.config.order_timeout_sec // 3):
            await asyncio.sleep(3)
            try:
                status = await client.get_order_status(order_no)
                if status["filled"] and status["filled_qty"] > 0:
                    return {
                        "order_no":   order_no,
                        "filled_qty": status["filled_qty"],
                        "avg_price":  status["avg_price"],
                    }
            except Exception as e:
                logger.warning(f"[Live] 매도 체결확인 실패 {code}: {e}")

        logger.error(f"[Live] 매도 체결 타임아웃 {code} — 수동 확인 필요!")
        return None

    # ── DB 저장 ────────────────────────────────────────────────

    async def _save_open(self, pos: LivePosition, db: AsyncSession):
        from ..db.models import LiveTrade
        from datetime import timezone
        row = LiveTrade(
            code=pos.code, name=pos.name, market=pos.market,
            entry_time=pos.entry_time, entry_price=pos.entry_price,
            quantity=pos.quantity, highest_price=pos.highest_price,
            entry_score=pos.entry_score, entry_order_no=pos.entry_order_no,
            status="OPEN", is_presurge=pos.is_presurge,
        )
        db.add(row)
        await db.flush()
        pos.db_id = row.id
        await db.commit()

    async def _save_close(self, pos: LivePosition, exit_price: float,
                          exit_order_no: str, reason: str, db: AsyncSession):
        from ..db.models import LiveTrade
        from datetime import timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        pl = (exit_price - pos.entry_price) * pos.quantity
        pl_pct = (exit_price - pos.entry_price) / pos.entry_price * 100
        if pos.db_id:
            row = await db.get(LiveTrade, pos.db_id)
            if row:
                row.status = "CLOSED"
                row.exit_time = now
                row.exit_price = exit_price
                row.exit_order_no = exit_order_no
                row.exit_reason = reason
                row.profit_loss = round(pl, 2)
                row.profit_loss_pct = round(pl_pct, 2)
                row.highest_price = pos.highest_price
        await db.commit()

    async def _record_portfolio(self, db: AsyncSession):
        from ..db.models import LivePortfolioHistory
        from datetime import timezone
        try:
            from ..kis.rest_client import get_kis_order_client
            bal = await get_kis_order_client().get_balance()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            pos_val = bal["total_eval"] - bal["cash"]
            db.add(LivePortfolioHistory(
                recorded_at=now,
                total_value=bal["total_eval"],
                cash=bal["cash"],
                position_value=max(pos_val, 0),
            ))
            await db.commit()
        except Exception as e:
            logger.warning(f"[Live] 포트폴리오 기록 실패: {e}")

    # ── 진입 ──────────────────────────────────────────────────

    async def _do_open(self, code: str, name: str, signal: dict,
                       db: AsyncSession, is_presurge: bool = False):
        # 예수금 기준 수량 계산
        try:
            from ..kis.rest_client import get_kis_order_client
            bal = await get_kis_order_client().get_balance()
            cash = bal["cash"]
        except Exception as e:
            logger.error(f"[Live] 예수금 조회 실패: {e}")
            return

        price = signal.get("current_price", 0)
        if not price:
            return
        invest = min(cash * self.config.position_size_pct, cash)
        qty = int(invest / price)
        if qty <= 0:
            logger.warning(f"[Live] {code} 수량 0 — 예수금 부족")
            return

        logger.info(f"[Live] 매수 시도 {code} {name} x{qty} @ {price:,.0f} (예수금 {cash:,.0f})")
        result = await self._place_buy_and_wait(code, qty)
        if not result:
            return

        from datetime import timezone
        pos = LivePosition(
            db_id=None, code=code, name=name, market=self.config.market,
            entry_time=datetime.now(timezone.utc).replace(tzinfo=None),
            entry_price=result["avg_price"],
            quantity=result["filled_qty"],
            highest_price=result["avg_price"],
            entry_score=signal.get("score", 0.0),
            entry_order_no=result["order_no"],
            dynamic_stop_price=result["avg_price"] * (1 + self.config.stop_loss_ratio),
            is_presurge=is_presurge,
        )
        self.open_positions.append(pos)
        await self._save_open(pos, db)
        logger.info(f"[Live] ✅ 매수 체결 {code} x{result['filled_qty']} @ {result['avg_price']:,.0f}")

    # ── 청산 ──────────────────────────────────────────────────

    async def _do_close(self, pos: LivePosition, reason: str,
                        volume_pct: float, db: AsyncSession):
        close_qty = pos.quantity if volume_pct >= 1.0 else max(1, int(pos.quantity * volume_pct))
        close_qty = min(close_qty, pos.quantity)

        logger.info(f"[Live] 매도 시도 {pos.code} x{close_qty} — {reason}")
        result = await self._place_sell_and_wait(pos.code, close_qty)
        if not result:
            logger.error(f"[Live] ❌ 매도 체결 실패 {pos.code} — 수동 확인 필요")
            return

        exit_price = result["avg_price"]
        is_full = (close_qty >= pos.quantity)
        pl_pct = (exit_price - pos.entry_price) / pos.entry_price * 100

        if is_full:
            self.open_positions.remove(pos)
            logger.info(f"[Live] ✅ 매도 체결 {pos.code} x{close_qty} @ {exit_price:,.0f} ({pl_pct:+.2f}%) — {reason}")
        else:
            pos.quantity -= close_qty
            tp_names = {tgt["name"] for tgt in self.config.take_profit_targets}
            if reason in tp_names and not pos.breakeven_active:
                pos.dynamic_stop_price = max(pos.dynamic_stop_price, pos.entry_price)
                pos.breakeven_active = True
            logger.info(f"[Live] ✅ 부분매도 {pos.code} x{close_qty} → 잔여 x{pos.quantity} @ {exit_price:,.0f} ({pl_pct:+.2f}%) — {reason}")

        await self._save_close(pos, exit_price, result["order_no"], reason, db)

    # ── 신호 스캔 ──────────────────────────────────────────────

    async def _scan_and_buy(self, db: AsyncSession):
        from .signal_service import generate_entry_signals_bulk
        from ..kis.rest_client import get_kis_client

        surge = await get_kis_client().get_volume_rank(limit=50)
        name_map = {s["code"]: s.get("name", "") for s in surge}
        codes = [s["code"] for s in surge
                 if not self._already_holding(s["code"]) and self._passes_entry_filter(s)]
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
            minute_ok, _ = await self._check_minute_breakout(sig["code"])
            if not minute_ok:
                continue
            name = name_map.get(sig["code"], sig["code"])
            await self._do_open(sig["code"], name, sig, db)

    async def _check_minute_breakout(self, code: str) -> Tuple[bool, dict]:
        from ..kis.rest_client import get_kis_client
        from .signals import MinuteBreakoutSignal
        try:
            candles = await get_kis_client().get_minute_chart(code)
            if not candles:
                return True, {}
            result = MinuteBreakoutSignal().check_signal(candles)
            return result["signal"] == "BUY", result
        except Exception:
            return True, {}

    async def _scan_and_buy_presurge(self, db: AsyncSession):
        from .signal_service import generate_entry_signal
        from ..kis.rest_client import get_kis_client
        import asyncio

        surge = await get_kis_client().get_volume_rank(limit=100, min_change_rate=-999)
        name_map = {s["code"]: s["name"] for s in surge}
        candidates = [s["code"] for s in surge
                      if not self._already_holding(s["code"])
                      and s.get("volume", 0) >= self.config.entry_min_volume]
        if not candidates:
            return

        semaphore = asyncio.Semaphore(4)

        async def _check(code: str):
            async with semaphore:
                try:
                    sig = await generate_entry_signal(code, self.config.market, self.config.strategy)
                    if sig.get("chase_blocked"):
                        return None
                    ps = sig.get("breakdown", {}).get("pattern", {}).get("pre_surge") or {}
                    if any(ps.get(k, {}).get("detected") for k in ("dryup_recovery", "seoryuk", "tight_consol")):
                        sig["_presurge"] = True
                        return sig
                    return None
                except Exception:
                    return None

        results = [r for r in await asyncio.gather(*[_check(c) for c in candidates[:50]]) if r]
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        for sig in results:
            if not self._can_open():
                break
            if self._already_holding(sig["code"]):
                continue
            code = sig["code"]
            await self._do_open(code, name_map.get(code, code), sig, db, is_presurge=True)

    # ── 일일 손실 한도 체크 ────────────────────────────────────

    async def _daily_loss_exceeded(self) -> bool:
        try:
            from ..kis.rest_client import get_kis_order_client
            bal = await get_kis_order_client().get_balance()
            today = datetime.now(KST).strftime("%Y-%m-%d")
            if self._daily_reset_date != today:
                self._daily_reset_date = today
                self._daily_start_value = bal["total_eval"]
                return False
            if self._daily_start_value <= 0:
                return False
            daily_pnl_pct = (bal["total_eval"] - self._daily_start_value) / self._daily_start_value
            if daily_pnl_pct <= self.config.daily_loss_limit:
                logger.warning(f"[Live] 일일 손실 한도 도달 ({daily_pnl_pct:.2%}) — 매수 중단")
                return True
        except Exception:
            pass
        return False

    # ── 메인 틱 ───────────────────────────────────────────────

    async def tick(self, db: AsyncSession) -> None:
        self._assert_enabled()
        if not self.is_running or not self._is_market_open():
            return

        # 1. 보유 포지션 청산 체크
        for pos in self.open_positions[:]:
            price = await self._get_current_price(pos.code)
            if price is None:
                continue
            should_exit, reason, volume_pct = self._check_exit(pos, price)
            if should_exit:
                await self._do_close(pos, reason, volume_pct, db)

        # 2. 신규 진입
        if self._can_open():
            if await self._daily_loss_exceeded():
                pass  # 일일 손실 한도 초과 — 매수 중단
            elif self.config.pre_surge_mode:
                await self._scan_and_buy_presurge(db)
            else:
                await self._scan_and_buy(db)

        # 3. 포트폴리오 기록 (30분 간격 — 별도 카운터 없이 tick 주기에 맡김)
        await self._record_portfolio(db)

    # ── 외부 제어 ─────────────────────────────────────────────

    async def start(self, config: dict, db: AsyncSession) -> None:
        self._assert_enabled()
        self.config.max_positions     = config.get("max_positions", self.config.max_positions)
        self.config.position_size_pct = config.get("position_size_pct", self.config.position_size_pct)
        self.config.min_score         = config.get("min_score", self.config.min_score)
        self.config.pre_surge_mode    = config.get("pre_surge_mode", self.config.pre_surge_mode)
        self.is_running = True
        from datetime import timezone
        self._started_at = datetime.now(timezone.utc)
        logger.info(f"[Live] ⚡ 실전 매매 시작 — max_pos={self.config.max_positions}, pre_surge={self.config.pre_surge_mode}")

    async def stop(self, db: AsyncSession) -> None:
        self.is_running = False
        logger.info("[Live] 실전 매매 중지")

    async def close_all_positions(self, db: AsyncSession) -> list:
        """전량 긴급 청산"""
        results = []
        for pos in self.open_positions[:]:
            await self._do_close(pos, "긴급청산", 1.0, db)
            results.append({"code": pos.code, "reason": "긴급청산"})
        return results

    def get_status(self) -> dict:
        return {
            "is_running":     self.is_running,
            "enabled":        self._enabled,
            "open_positions": len(self.open_positions),
            "max_positions":  self.config.max_positions,
            "pre_surge_mode": self.config.pre_surge_mode,
            "daily_loss_limit": self.config.daily_loss_limit,
        }

    def get_positions(self) -> list:
        return [p.to_dict() for p in self.open_positions]

    async def get_trades(self, db: AsyncSession, limit: int = 50) -> dict:
        from ..db.models import LiveTrade
        from sqlalchemy import func, case
        result = await db.execute(
            select(LiveTrade)
            .where(LiveTrade.status == "CLOSED")
            .order_by(LiveTrade.exit_time.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        trades = [{
            "id":             r.id,
            "code":           r.code,
            "name":           r.name,
            "entry_time":     (r.entry_time.isoformat() + 'Z') if r.entry_time else None,
            "entry_price":    r.entry_price,
            "highest_price":  r.highest_price,
            "exit_time":      (r.exit_time.isoformat() + 'Z') if r.exit_time else None,
            "exit_price":     r.exit_price,
            "exit_reason":    r.exit_reason,
            "quantity":       r.quantity,
            "profit_loss":    r.profit_loss,
            "profit_loss_pct": r.profit_loss_pct,
            "is_presurge":    r.is_presurge,
        } for r in rows]

        total_pnl   = sum(r.profit_loss or 0 for r in rows)
        profit_rows = [r for r in rows if (r.profit_loss or 0) > 0]
        loss_rows   = [r for r in rows if (r.profit_loss or 0) <= 0]
        return {
            "trades":       trades,
            "total":        len(rows),
            "total_pnl":    round(total_pnl, 2),
            "profit_count": len(profit_rows),
            "profit_amount": round(sum(r.profit_loss or 0 for r in profit_rows), 2),
            "loss_count":   len(loss_rows),
            "loss_amount":  round(sum(r.profit_loss or 0 for r in loss_rows), 2),
        }

    async def get_history(self, db: AsyncSession, limit: int = 200) -> list:
        from ..db.models import LivePortfolioHistory
        result = await db.execute(
            select(LivePortfolioHistory)
            .order_by(LivePortfolioHistory.recorded_at.asc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [{
            "recorded_at":    (r.recorded_at.isoformat() + 'Z') if r.recorded_at else None,
            "total_value":    r.total_value,
            "cash":           r.cash,
            "position_value": r.position_value,
        } for r in rows]


# ── 싱글턴 ───────────────────────────────────────────────────
live_engine = LiveEngine()
