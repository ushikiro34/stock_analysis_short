"""Signal-related Pydantic schemas"""
from pydantic import BaseModel
from typing import Optional, List


class EntrySignalResponse(BaseModel):
    """진입 신호 응답"""
    code: str
    market: str
    signal: str  # BUY, HOLD
    strength: str  # high, medium, low
    score: float
    reasons: List[str]
    timestamp: str
    current_price: Optional[float] = None
    breakdown: Optional[dict] = None


class ExitSignalRequest(BaseModel):
    """청산 신호 요청"""
    code: str
    entry_price: float
    entry_time: str  # ISO 8601 format
    market: str = "KR"


class ExitSignalResponse(BaseModel):
    """청산 신호 응답"""
    code: str
    market: str
    should_exit: bool
    exit_type: Optional[str] = None  # take_profit, stop_loss, time_based
    volume_pct: float
    reason: str
    current_price: Optional[float] = None
    entry_price: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None
    holding_time: Optional[float] = None  # minutes
    timestamp: Optional[str] = None
    details: Optional[dict] = None
