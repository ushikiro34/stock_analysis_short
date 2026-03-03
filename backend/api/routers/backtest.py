"""
Backtest API Router
백테스팅 관련 엔드포인트
"""
from fastapi import APIRouter
from typing import List
from datetime import datetime, timedelta
import logging

from ...backtest.engine import BacktestConfig, run_simple_backtest
from ...backtest.analytics import PerformanceAnalytics, compare_strategies
from ..schemas.backtest import BacktestRequest, CompareRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["📈 Backtest"])

# 백테스트 캐시
_backtest_cache: dict = {}


@router.post("/run")
async def run_backtest(request: BacktestRequest):
    """
    백테스팅 실행

    Args:
        request: 백테스팅 요청 (symbols, market, days, initial_capital 등)

    Returns:
        백테스팅 결과 리포트
    """
    try:
        # 날짜 범위 설정
        end_date = datetime.now()
        start_date = end_date - timedelta(days=request.days)

        # 백테스팅 설정
        config = BacktestConfig(
            initial_capital=request.initial_capital,
            entry_strategy=request.entry_strategy,
            min_entry_score=request.min_entry_score,
            stop_loss_ratio=request.stop_loss_ratio,
            max_holding_days=request.max_holding_days
        )

        logger.info(f"Starting backtest: {len(request.symbols)} symbols, {request.days} days")

        # 백테스팅 실행
        result = await run_simple_backtest(
            symbols=request.symbols,
            market=request.market,
            start_date=start_date,
            end_date=end_date,
            config=config
        )

        # 향상된 분석 리포트 생성
        enhanced_result = PerformanceAnalytics.generate_enhanced_report(result)

        return enhanced_result

    except Exception as e:
        logger.error(f"Backtest error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "summary": {
                "initial_capital": request.initial_capital,
                "final_capital": request.initial_capital,
                "net_profit": 0,
                "roi": 0,
                "total_trades": 0
            }
        }


@router.post("/compare")
async def compare_backtest_strategies(
    symbols: List[str],
    market: str = "US",
    days: int = 90,
    strategies: List[str] = ["volume", "technical", "combined"]
):
    """
    여러 전략 백테스팅 비교

    Args:
        symbols: 종목 코드 리스트
        market: KR | US
        days: 백테스팅 기간
        strategies: 비교할 전략 리스트

    Returns:
        전략 비교 결과
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        results = []

        for strategy in strategies:
            config = BacktestConfig(
                entry_strategy=strategy,
                min_entry_score=60.0
            )

            logger.info(f"Running backtest for strategy: {strategy}")

            result = await run_simple_backtest(
                symbols=symbols,
                market=market,
                start_date=start_date,
                end_date=end_date,
                config=config
            )

            enhanced_result = PerformanceAnalytics.generate_enhanced_report(result)
            results.append(enhanced_result)

        # 전략 비교
        comparison = compare_strategies(results)

        return {
            "comparison": comparison,
            "details": results
        }

    except Exception as e:
        logger.error(f"Strategy comparison error: {e}")
        return {
            "error": str(e),
            "comparison": {},
            "details": []
        }
