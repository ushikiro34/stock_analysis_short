"""Backtest-related Pydantic schemas"""
from pydantic import BaseModel
from typing import List, Optional


class BacktestRequest(BaseModel):
    """백테스팅 요청"""
    symbols: List[str]
    market: str = "US"
    days: int = 90
    initial_capital: float = 10000.0
    entry_strategy: str = "combined"
    min_entry_score: float = 60.0
    stop_loss_ratio: float = -0.02
    max_holding_days: int = 5


class BacktestResponse(BaseModel):
    """백테스팅 응답"""
    summary: dict
    advanced_metrics: Optional[dict] = None
    trade_analysis: Optional[dict] = None
    trades: Optional[List[dict]] = None
    portfolio_history: Optional[List[dict]] = None
    best_trade: Optional[dict] = None
    worst_trade: Optional[dict] = None
    monthly_returns: Optional[List[dict]] = None
    config: Optional[dict] = None


class CompareRequest(BaseModel):
    """전략 비교 요청"""
    symbols: List[str]
    market: str = "US"
    days: int = 90
    strategies: List[str] = ["volume", "technical", "combined"]
