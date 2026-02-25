from sqlalchemy import Column, Integer, String, Numeric, BigInteger, TIMESTAMP, ForeignKey, PrimaryKeyConstraint
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
