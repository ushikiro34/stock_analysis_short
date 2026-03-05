"""
Paper Trading Engine — 실시간 데이터 기반 가상 자동매매 시뮬레이션
실제 주문 없이 KIS API의 리얼 데이터로 자동매매를 시뮬레이션한다.
"""
import asyncio
import logging
from datetime import datetime, time
from typing import List, Optional, Tuple
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

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
    position_size_pct: float = 0.3          # 종목당 30%
    max_positions: int = 3
    strategy: str = "combined"
    min_score: float = 65.0
    market: str = "KR"
    stop_loss_ratio: float = -0.02          # -2% 손절
    trailing_stop_ratio: float = -0.03      # 최고가 대비 -3%
    take_profit_targets: List[dict] = field(default_factory=lambda: [
        {"ratio": 0.03, "name": "1차 익절 +3%"},
        {"ratio": 0.05, "name": "2차 익절 +5%"},
        {"ratio": 0.10, "name": "3차 익절 +10%"},
    ])
    max_holding_hours: int = 24 * 5         # 최대 5일 보유
    commission_rate: float = 0.001          # 0.1%


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

    def update_highest(self, price: float):
        self.highest_price = max(self.highest_price, price)

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.entry_price) * self.quantity

    def unrealized_pnl_pct(self, current_price: float) -> float:
        return (current_price - self.entry_price) / self.entry_price * 100

    def holding_hours(self) -> float:
        return (datetime.utcnow() - self.entry_time).total_seconds() / 3600

    def to_dict(self, current_price: Optional[float] = None) -> dict:
        pnl = self.unrealized_pnl(current_price) if current_price else None
        pnl_pct = self.unrealized_pnl_pct(current_price) if current_price else None
        return {
            "id": self.db_id,
            "code": self.code,
            "name": self.name,
            "market": self.market,
            "entry_time": self.entry_time.isoformat(),
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

    def _check_exit(self, pos: PaperPosition, current_price: float) -> Tuple[bool, str]:
        """청산 조건 체크 (backtest engine.check_exit_conditions 이식)"""
        pos.update_highest(current_price)
        ratio = (current_price - pos.entry_price) / pos.entry_price

        # 1. 익절
        for tgt in self.config.take_profit_targets:
            if ratio >= tgt["ratio"]:
                return True, tgt["name"]

        # 2. 고정 손절
        if ratio <= self.config.stop_loss_ratio:
            return True, "fixed_stop_loss"

        # 3. 트레일링 스톱 (최고가 경신 후 하락 시)
        trail_threshold = pos.highest_price * (1 + self.config.trailing_stop_ratio)
        if current_price <= trail_threshold and pos.highest_price > pos.entry_price:
            return True, "trailing_stop"

        # 4. 최대 보유 시간
        if pos.holding_hours() >= self.config.max_holding_hours:
            return True, f"time_limit_{self.config.max_holding_hours}h"

        return False, ""

    # ── 현재가 조회 ──────────────────────────────────────────

    async def _get_current_price(self, code: str, market: str) -> Optional[float]:
        try:
            if market == "KR":
                from ..kis.rest_client import get_kis_client
                candles = await get_kis_client().get_minute_chart(code)
                if candles:
                    return float(candles[-1]["close"])
            else:
                import yfinance as yf
                ticker = yf.Ticker(f"{code}")
                hist = ticker.history(period="1d", interval="1m")
                if not hist.empty:
                    return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"[Paper] 현재가 조회 실패 {code}: {e}")
        return None

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
            price = await self._get_current_price(pos.code, pos.market)
            if price is None:
                continue
            current_prices[pos.code] = price
            should_exit, reason = self._check_exit(pos, price)
            if should_exit:
                await self._do_close(pos, price, reason, db)

        # 2. 신규 진입 스캔
        if self._can_open():
            await self._scan_and_buy(db, current_prices)

        # 3. 포트폴리오 기록
        await self._record_portfolio(db, current_prices)
        await self._save_account(db)

    async def _do_close(self, pos: PaperPosition, price: float, reason: str,
                        db: AsyncSession) -> None:
        revenue = price * pos.quantity
        commission = self._get_commission(price, pos.quantity)
        self.cash += revenue - commission
        self.open_positions.remove(pos)
        self.closed_today += 1
        pl_pct = (price - pos.entry_price) / pos.entry_price * 100
        logger.info(f"[Paper] CLOSE {pos.code} @ {price:,.0f}원 ({pl_pct:+.2f}%) — {reason}")
        await self._close_position_in_db(pos, price, reason, db)

    async def _scan_and_buy(self, db: AsyncSession, current_prices: dict) -> None:
        from .signal_service import generate_entry_signals_bulk
        from ..kis.rest_client import get_kis_client

        try:
            surge = await get_kis_client().get_volume_rank(limit=50)
            name_map = {s["code"]: s.get("name", "") for s in surge}
            codes = [s["code"] for s in surge if not self._already_holding(s["code"])]
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
                sig["_name"] = name_map.get(sig["code"], sig["code"])
                await self._do_open(sig, price, db)

        except Exception as e:
            logger.error(f"[Paper] 신호 스캔 오류: {e}")

    async def _do_open(self, signal: dict, price: float, db: AsyncSession) -> None:
        qty = self._calculate_position_size(price)
        if qty <= 0:
            return
        cost = price * qty + self._get_commission(price, qty)
        if cost > self.cash:
            return

        self.cash -= cost
        from datetime import timezone
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
        )
        self.open_positions.append(pos)
        logger.info(f"[Paper] BUY {pos.code} x{qty} @ {price:,.0f}원 (score={pos.entry_score:.0f})")
        await self._save_open_position(pos, db)

    # ── 외부 제어 ────────────────────────────────────────────

    async def start(self, config: dict, db: AsyncSession) -> None:
        self.config.initial_capital = config.get("initial_capital", self.config.initial_capital)
        self.config.market = config.get("market", self.config.market)
        self.config.strategy = config.get("strategy", self.config.strategy)
        self.config.min_score = config.get("min_score", self.config.min_score)
        self.config.max_positions = config.get("max_positions", self.config.max_positions)
        self.config.position_size_pct = config.get("position_size_pct", self.config.position_size_pct)
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
                "entry_time": r.entry_time.isoformat() if r.entry_time else None,
                "entry_price": r.entry_price,
                "exit_time": r.exit_time.isoformat() if r.exit_time else None,
                "exit_price": r.exit_price,
                "exit_reason": r.exit_reason,
                "quantity": r.quantity,
                "profit_loss": r.profit_loss,
                "profit_loss_pct": r.profit_loss_pct,
            }
            for r in rows
        ]

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
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                "total_value": r.total_value,
                "cash": r.cash,
                "position_value": r.position_value,
            }
            for r in rows
        ]


# ── 싱글턴 인스턴스 ──────────────────────────────────────────
paper_engine = PaperEngine()
