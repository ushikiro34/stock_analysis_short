from sqlalchemy import Column, Integer, String, Numeric, BigInteger, Float, Boolean, TIMESTAMP, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from .session import Base

class Stock(Base):
    __tablename__ = "stocks"
    code = Column(String(10), primary_key=True)
    name = Column(String(100))
    market = Column(String(10))

class TickData(Base):
    __tablename__ = "tick_data"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(10), ForeignKey("stocks.code"))
    price = Column(Numeric)
    volume = Column(BigInteger)
    tick_time = Column(TIMESTAMP)

class OHLCV1m(Base):
    __tablename__ = "ohlcv_1m"
    code = Column(String(10), ForeignKey("stocks.code"), primary_key=True)
    minute = Column(TIMESTAMP, primary_key=True)
    open = Column(Numeric)
    high = Column(Numeric)
    low = Column(Numeric)
    close = Column(Numeric)
    volume = Column(BigInteger)

class Fundamental(Base):
    __tablename__ = "fundamentals"
    code = Column(String(10), ForeignKey("stocks.code"), primary_key=True)
    per = Column(Numeric)
    pbr = Column(Numeric)
    roe = Column(Numeric)
    eps = Column(Numeric)
    bps = Column(Numeric)
    updated_at = Column(TIMESTAMP)

class ScoreSnapshot(Base):
    __tablename__ = "score_snapshot"
    code = Column(String(10), ForeignKey("stocks.code"), primary_key=True)
    calculated_at = Column(TIMESTAMP, primary_key=True)
    value_score = Column(Numeric)
    trend_score = Column(Numeric)
    stability_score = Column(Numeric)
    risk_penalty = Column(Numeric)
    total_score = Column(Numeric)


# ── Paper Trading ─────────────────────────────────────────────

class PaperAccount(Base):
    """페이퍼 트레이딩 계좌 설정 (단일 행, id=1 고정)"""
    __tablename__ = "paper_account"
    id                = Column(Integer, primary_key=True, default=1)
    initial_capital   = Column(Float, default=10_000_000.0)
    cash              = Column(Float, default=10_000_000.0)
    is_running        = Column(Boolean, default=False)
    market            = Column(String(4), default="KR")
    strategy          = Column(String(32), default="combined")
    min_score         = Column(Float, default=65.0)
    max_positions     = Column(Integer, default=3)
    position_size_pct = Column(Float, default=0.3)
    updated_at        = Column(TIMESTAMP)


class PaperTrade(Base):
    """페이퍼 트레이딩 거래 기록"""
    __tablename__ = "paper_trades"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    code            = Column(String(10))
    name            = Column(String(64))
    market          = Column(String(4), default="KR")
    entry_time      = Column(TIMESTAMP)
    entry_price     = Column(Float)
    quantity        = Column(Integer)
    highest_price   = Column(Float)
    entry_score     = Column(Float, default=0.0)
    status          = Column(String(8), default="OPEN")   # OPEN / CLOSED
    exit_time       = Column(TIMESTAMP, nullable=True)
    exit_price      = Column(Float, nullable=True)
    exit_reason     = Column(String(64), nullable=True)
    profit_loss     = Column(Float, default=0.0)
    profit_loss_pct = Column(Float, default=0.0)


class PaperPortfolioHistory(Base):
    """페이퍼 트레이딩 포트폴리오 가치 이력"""
    __tablename__ = "paper_portfolio_history"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    recorded_at    = Column(TIMESTAMP)
    total_value    = Column(Float)
    cash           = Column(Float)
    position_value = Column(Float)
