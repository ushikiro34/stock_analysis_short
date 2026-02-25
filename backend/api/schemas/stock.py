"""Stock-related Pydantic schemas"""
from pydantic import BaseModel
from typing import Optional


class ScoreResponse(BaseModel):
    """종목 점수 응답"""
    code: str
    calculated_at: Optional[str] = None
    value_score: Optional[float] = None
    trend_score: Optional[float] = None
    stability_score: Optional[float] = None
    risk_penalty: Optional[float] = None
    total_score: Optional[float] = None
    fundamental: Optional[dict] = None
    technical: Optional[dict] = None


class DailyOHLCVResponse(BaseModel):
    """일봉/주봉 OHLCV 응답"""
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class SurgeStockResponse(BaseModel):
    """급등주 응답"""
    code: str
    name: str
    price: float
    change_rate: float
    volume: int
    change_price: float


class MinuteOHLCVResponse(BaseModel):
    """분봉 OHLCV 응답"""
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int
