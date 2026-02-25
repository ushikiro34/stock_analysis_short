"""Optimization-related Pydantic schemas"""
from pydantic import BaseModel
from typing import List, Optional


class OptimizeRequest(BaseModel):
    """최적화 요청"""
    symbols: List[str]
    market: str = "US"
    days: int = 60
    optimization_metric: str = "sharpe_ratio"  # roi, sharpe_ratio, win_rate, profit_factor, calmar_ratio

    # 파라미터 범위 (optional)
    stop_loss_ratios: Optional[List[float]] = None
    take_profit_ratios: Optional[List[float]] = None
    max_holding_days_options: Optional[List[int]] = None
    min_entry_scores: Optional[List[float]] = None
    position_size_pcts: Optional[List[float]] = None


class QuickOptimizeRequest(BaseModel):
    """빠른 최적화 요청 (제한된 범위)"""
    symbols: List[str]
    market: str = "US"
    days: int = 60
    optimization_metric: str = "sharpe_ratio"


class OptimizeResponse(BaseModel):
    """최적화 응답"""
    status: str
    optimization_id: Optional[str] = None
    optimization_metric: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    total_combinations_tested: Optional[int] = None
    best_params: Optional[dict] = None
    best_performance: Optional[dict] = None
    top_5_results: Optional[List[dict]] = None
    parameter_analysis: Optional[dict] = None
    full_results: Optional[List[dict]] = None
    message: Optional[str] = None
