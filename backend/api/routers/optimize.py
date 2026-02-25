"""
Optimization API Router
파라미터 최적화 관련 엔드포인트
"""
from fastapi import APIRouter, HTTPException
from typing import List
import logging

from ..schemas.optimize import OptimizeRequest, QuickOptimizeRequest, OptimizeResponse
from ...backtest.optimizer import GridSearchOptimizer, OptimizationParams, quick_optimize

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/optimize", tags=["🔧 Optimize"])


@router.post("/grid-search", response_model=OptimizeResponse)
async def run_grid_search(request: OptimizeRequest):
    """
    Grid Search 파라미터 최적화

    전체 파라미터 범위에서 최적의 조합을 찾습니다.
    실행 시간이 오래 걸릴 수 있습니다 (조합 수에 따라 수 분~수십 분).
    """
    try:
        # 파라미터 범위 설정
        param_ranges = OptimizationParams(
            stop_loss_ratios=request.stop_loss_ratios,
            take_profit_ratios=request.take_profit_ratios,
            max_holding_days_options=request.max_holding_days_options,
            min_entry_scores=request.min_entry_scores,
            position_size_pcts=request.position_size_pcts
        )

        # 최적화 실행
        optimizer = GridSearchOptimizer(
            param_ranges=param_ranges,
            optimization_metric=request.optimization_metric
        )

        result = await optimizer.optimize(
            symbols=request.symbols,
            market=request.market,
            days=request.days
        )

        return result

    except Exception as e:
        logger.error(f"Grid search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick", response_model=OptimizeResponse)
async def run_quick_optimization(request: QuickOptimizeRequest):
    """
    빠른 최적화 (제한된 파라미터 범위)

    제한된 범위에서 빠르게 최적화를 수행합니다.
    일반적으로 1-5분 소요됩니다.
    """
    try:
        result = await quick_optimize(
            symbols=request.symbols,
            market=request.market,
            days=request.days,
            metric=request.optimization_metric
        )

        return result

    except Exception as e:
        logger.error(f"Quick optimization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_available_metrics():
    """
    사용 가능한 최적화 지표 목록

    각 지표의 설명과 권장 사용 시나리오를 반환합니다.
    """
    return {
        "metrics": [
            {
                "name": "roi",
                "display_name": "수익률 (ROI)",
                "description": "총 수익률을 최대화",
                "unit": "%",
                "recommended_for": "공격적 전략"
            },
            {
                "name": "sharpe_ratio",
                "display_name": "샤프 비율",
                "description": "위험 대비 수익률 최적화 (가장 균형잡힌 지표)",
                "unit": "ratio",
                "recommended_for": "균형잡힌 전략"
            },
            {
                "name": "sortino_ratio",
                "display_name": "소르티노 비율",
                "description": "하방 위험 대비 수익률 최적화",
                "unit": "ratio",
                "recommended_for": "방어적 전략"
            },
            {
                "name": "calmar_ratio",
                "display_name": "칼마 비율",
                "description": "MDD 대비 수익률 최적화",
                "unit": "ratio",
                "recommended_for": "낙폭 최소화"
            },
            {
                "name": "win_rate",
                "display_name": "승률",
                "description": "거래 성공 비율 최대화",
                "unit": "%",
                "recommended_for": "안정적 수익 추구"
            },
            {
                "name": "profit_factor",
                "display_name": "손익비",
                "description": "수익/손실 비율 최적화",
                "unit": "ratio",
                "recommended_for": "수익 극대화"
            }
        ]
    }


@router.get("/param-ranges")
async def get_default_param_ranges():
    """
    기본 파라미터 범위

    Grid Search에서 사용하는 기본 파라미터 범위를 반환합니다.
    """
    default_params = OptimizationParams()

    return {
        "stop_loss_ratios": default_params.stop_loss_ratios,
        "take_profit_ratios": default_params.take_profit_ratios,
        "max_holding_days_options": default_params.max_holding_days_options,
        "min_entry_scores": default_params.min_entry_scores,
        "position_size_pcts": default_params.position_size_pcts,
        "total_combinations": default_params.get_total_combinations()
    }
