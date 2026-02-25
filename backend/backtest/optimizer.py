"""
Grid Search parameter optimization for trading strategies.
매매 전략의 파라미터를 Grid Search로 최적화
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from itertools import product
from dataclasses import dataclass, asdict
import time

from .engine import BacktestConfig, run_simple_backtest
from .analytics import PerformanceAnalytics

logger = logging.getLogger(__name__)


@dataclass
class OptimizationParams:
    """최적화할 파라미터 범위"""
    stop_loss_ratios: List[float] = None
    take_profit_ratios: List[float] = None
    max_holding_days_options: List[int] = None
    min_entry_scores: List[float] = None
    position_size_pcts: List[float] = None

    def __post_init__(self):
        # 기본값 설정
        if self.stop_loss_ratios is None:
            self.stop_loss_ratios = [-0.01, -0.015, -0.02, -0.025, -0.03]

        if self.take_profit_ratios is None:
            self.take_profit_ratios = [0.03, 0.04, 0.05]

        if self.max_holding_days_options is None:
            self.max_holding_days_options = [3, 5, 7]

        if self.min_entry_scores is None:
            self.min_entry_scores = [55, 60, 65]

        if self.position_size_pcts is None:
            self.position_size_pcts = [0.2, 0.3, 0.4]

    def get_total_combinations(self) -> int:
        """전체 조합 수 계산"""
        return (
            len(self.stop_loss_ratios) *
            len(self.take_profit_ratios) *
            len(self.max_holding_days_options) *
            len(self.min_entry_scores) *
            len(self.position_size_pcts)
        )


@dataclass
class OptimizationResult:
    """최적화 결과"""
    params: Dict
    performance: Dict
    rank: int = 0

    def get_score(self, metric: str = "roi") -> float:
        """특정 지표 점수 반환"""
        return self.performance.get("summary", {}).get(metric, 0)


class GridSearchOptimizer:
    """Grid Search 파라미터 최적화기"""

    def __init__(
        self,
        param_ranges: Optional[OptimizationParams] = None,
        optimization_metric: str = "sharpe_ratio",
        parallel: bool = False
    ):
        """
        Args:
            param_ranges: 최적화할 파라미터 범위
            optimization_metric: 최적화 기준 지표
                - roi: 수익률
                - sharpe_ratio: 샤프 비율
                - win_rate: 승률
                - profit_factor: 손익비
                - calmar_ratio: 칼마 비율
            parallel: 병렬 처리 여부
        """
        self.param_ranges = param_ranges or OptimizationParams()
        self.optimization_metric = optimization_metric
        self.parallel = parallel

        self.results: List[OptimizationResult] = []
        self.best_result: Optional[OptimizationResult] = None

    def _generate_param_combinations(self) -> List[Dict]:
        """파라미터 조합 생성"""
        combinations = []

        for (
            stop_loss,
            take_profit,
            max_days,
            min_score,
            position_size
        ) in product(
            self.param_ranges.stop_loss_ratios,
            self.param_ranges.take_profit_ratios,
            self.param_ranges.max_holding_days_options,
            self.param_ranges.min_entry_scores,
            self.param_ranges.position_size_pcts
        ):
            # 익절 목표 생성 (단계별)
            take_profit_targets = [
                {"ratio": take_profit * 0.6, "volume_pct": 0.4, "name": f"1차 익절 +{take_profit*0.6*100:.1f}%"},
                {"ratio": take_profit, "volume_pct": 0.3, "name": f"2차 익절 +{take_profit*100:.1f}%"},
                {"ratio": take_profit * 1.5, "volume_pct": 0.3, "name": f"3차 익절 +{take_profit*1.5*100:.1f}%"},
            ]

            combinations.append({
                "stop_loss_ratio": stop_loss,
                "take_profit_targets": take_profit_targets,
                "max_holding_days": max_days,
                "min_entry_score": min_score,
                "position_size_pct": position_size,
            })

        return combinations

    async def _run_single_backtest(
        self,
        symbols: List[str],
        market: str,
        start_date: datetime,
        end_date: datetime,
        params: Dict
    ) -> OptimizationResult:
        """단일 파라미터 조합으로 백테스팅 실행"""
        # BacktestConfig 생성
        config = BacktestConfig(
            initial_capital=10000.0,
            entry_strategy="combined",
            min_entry_score=params["min_entry_score"],
            stop_loss_ratio=params["stop_loss_ratio"],
            take_profit_targets=params["take_profit_targets"],
            max_holding_days=params["max_holding_days"],
            position_size_pct=params["position_size_pct"]
        )

        try:
            # 백테스팅 실행
            result = await run_simple_backtest(
                symbols=symbols,
                market=market,
                start_date=start_date,
                end_date=end_date,
                config=config
            )

            # 향상된 분석
            enhanced_result = PerformanceAnalytics.generate_enhanced_report(result)

            return OptimizationResult(
                params=params,
                performance=enhanced_result
            )

        except Exception as e:
            logger.error(f"Backtest failed for params {params}: {e}")
            # 실패 시 빈 결과 반환
            return OptimizationResult(
                params=params,
                performance={"summary": {"roi": -999, "sharpe_ratio": -999}}
            )

    def _get_metric_value(self, result: OptimizationResult) -> float:
        """최적화 지표 값 추출"""
        if self.optimization_metric in ["roi", "win_rate", "profit_factor", "max_drawdown"]:
            return result.performance.get("summary", {}).get(self.optimization_metric, -999)
        else:  # sharpe_ratio, sortino_ratio, calmar_ratio
            return result.performance.get("advanced_metrics", {}).get(self.optimization_metric, -999)

    async def optimize(
        self,
        symbols: List[str],
        market: str = "US",
        days: int = 90,
        strategy: str = "combined"
    ) -> Dict:
        """
        Grid Search 최적화 실행

        Args:
            symbols: 종목 코드 리스트
            market: "KR" | "US"
            days: 백테스팅 기간
            strategy: 진입 전략

        Returns:
            최적화 결과
        """
        start_time = time.time()

        # 날짜 범위
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 파라미터 조합 생성
        param_combinations = self._generate_param_combinations()
        total_combinations = len(param_combinations)

        logger.info(f"[Optimizer] Starting Grid Search: {total_combinations} combinations")
        logger.info(f"[Optimizer] Period: {start_date.date()} ~ {end_date.date()}")
        logger.info(f"[Optimizer] Optimization metric: {self.optimization_metric}")

        # 각 조합에 대해 백테스팅 실행
        self.results = []

        for i, params in enumerate(param_combinations, 1):
            logger.info(f"[Optimizer] Progress: {i}/{total_combinations} ({i/total_combinations*100:.1f}%)")

            result = await self._run_single_backtest(
                symbols=symbols,
                market=market,
                start_date=start_date,
                end_date=end_date,
                params=params
            )

            self.results.append(result)

            # 진행상황 로그
            metric_value = self._get_metric_value(result)
            logger.info(f"[Optimizer]   {self.optimization_metric}: {metric_value:.2f}")

        # 결과 정렬 (최적화 지표 기준)
        self.results.sort(key=lambda r: self._get_metric_value(r), reverse=True)

        # 순위 매기기
        for i, result in enumerate(self.results, 1):
            result.rank = i

        # 최고 결과
        self.best_result = self.results[0] if self.results else None

        execution_time = time.time() - start_time

        logger.info(f"[Optimizer] Optimization completed in {execution_time:.1f}s")

        if self.best_result:
            best_metric = self._get_metric_value(self.best_result)
            logger.info(f"[Optimizer] Best {self.optimization_metric}: {best_metric:.2f}")

        # 결과 요약
        return self._generate_optimization_report(execution_time)

    def _generate_optimization_report(self, execution_time: float) -> Dict:
        """최적화 결과 리포트 생성"""
        if not self.best_result:
            return {
                "status": "failed",
                "message": "No valid results"
            }

        # 상위 5개 결과
        top_results = []
        for result in self.results[:5]:
            metric_value = self._get_metric_value(result)

            top_results.append({
                "rank": result.rank,
                "params": result.params,
                f"{self.optimization_metric}": metric_value,
                "roi": result.performance.get("summary", {}).get("roi", 0),
                "win_rate": result.performance.get("summary", {}).get("win_rate", 0),
                "sharpe_ratio": result.performance.get("advanced_metrics", {}).get("sharpe_ratio", 0),
                "max_drawdown": result.performance.get("summary", {}).get("max_drawdown", 0),
                "total_trades": result.performance.get("summary", {}).get("total_trades", 0)
            })

        # 파라미터 분포 분석
        param_analysis = self._analyze_parameter_distribution()

        return {
            "status": "completed",
            "optimization_id": f"opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "optimization_metric": self.optimization_metric,
            "execution_time_seconds": round(execution_time, 2),
            "total_combinations_tested": len(self.results),
            "best_params": self.best_result.params,
            "best_performance": {
                self.optimization_metric: self._get_metric_value(self.best_result),
                "roi": self.best_result.performance.get("summary", {}).get("roi", 0),
                "win_rate": self.best_result.performance.get("summary", {}).get("win_rate", 0),
                "sharpe_ratio": self.best_result.performance.get("advanced_metrics", {}).get("sharpe_ratio", 0),
                "max_drawdown": self.best_result.performance.get("summary", {}).get("max_drawdown", 0),
            },
            "top_5_results": top_results,
            "parameter_analysis": param_analysis,
            "full_results": [
                {
                    "rank": r.rank,
                    "params": r.params,
                    self.optimization_metric: self._get_metric_value(r)
                }
                for r in self.results
            ]
        }

    def _analyze_parameter_distribution(self) -> Dict:
        """파라미터 분포 분석 (상위 10개 결과 기준)"""
        top_10 = self.results[:10]

        if not top_10:
            return {}

        # 각 파라미터별 빈도 분석
        stop_loss_counts = {}
        max_days_counts = {}
        min_score_counts = {}
        position_size_counts = {}

        for result in top_10:
            params = result.params

            # 손절 비율
            sl = params["stop_loss_ratio"]
            stop_loss_counts[sl] = stop_loss_counts.get(sl, 0) + 1

            # 최대 보유 일수
            days = params["max_holding_days"]
            max_days_counts[days] = max_days_counts.get(days, 0) + 1

            # 최소 진입 점수
            score = params["min_entry_score"]
            min_score_counts[score] = min_score_counts.get(score, 0) + 1

            # 포지션 크기
            size = params["position_size_pct"]
            position_size_counts[size] = position_size_counts.get(size, 0) + 1

        # 최빈값 찾기
        most_common_stop_loss = max(stop_loss_counts, key=stop_loss_counts.get)
        most_common_max_days = max(max_days_counts, key=max_days_counts.get)
        most_common_min_score = max(min_score_counts, key=min_score_counts.get)
        most_common_position_size = max(position_size_counts, key=position_size_counts.get)

        return {
            "top_10_most_common": {
                "stop_loss_ratio": most_common_stop_loss,
                "max_holding_days": most_common_max_days,
                "min_entry_score": most_common_min_score,
                "position_size_pct": most_common_position_size
            },
            "distribution": {
                "stop_loss_ratios": stop_loss_counts,
                "max_holding_days": max_days_counts,
                "min_entry_scores": min_score_counts,
                "position_size_pcts": position_size_counts
            }
        }


async def quick_optimize(
    symbols: List[str],
    market: str = "US",
    days: int = 60,
    metric: str = "sharpe_ratio"
) -> Dict:
    """
    빠른 최적화 (제한된 파라미터 범위)

    Args:
        symbols: 종목 코드 리스트
        market: "KR" | "US"
        days: 백테스팅 기간
        metric: 최적화 지표

    Returns:
        최적화 결과
    """
    # 제한된 파라미터 범위
    quick_params = OptimizationParams(
        stop_loss_ratios=[-0.015, -0.02, -0.025],
        take_profit_ratios=[0.03, 0.04],
        max_holding_days_options=[5, 7],
        min_entry_scores=[60, 65],
        position_size_pcts=[0.3]
    )

    optimizer = GridSearchOptimizer(
        param_ranges=quick_params,
        optimization_metric=metric
    )

    result = await optimizer.optimize(
        symbols=symbols,
        market=market,
        days=days
    )

    return result
