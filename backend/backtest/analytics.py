"""
Backtesting analytics and performance metrics.
백테스팅 성과 분석 및 지표 계산
"""
import math
from typing import List, Dict
from datetime import datetime

import pandas as pd


class PerformanceAnalytics:
    """성과 분석 클래스"""

    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        """
        샤프 비율 계산 (위험 대비 수익률)

        Args:
            returns: 일별 수익률 리스트
            risk_free_rate: 무위험 수익률 (연율)

        Returns:
            샤프 비율
        """
        if not returns or len(returns) < 2:
            return 0.0

        returns_series = pd.Series(returns)

        # 평균 수익률
        mean_return = returns_series.mean()

        # 표준편차
        std_return = returns_series.std()

        if std_return == 0:
            return 0.0

        # 일별 무위험 수익률
        daily_rf = risk_free_rate / 252

        # 샤프 비율 (연율화)
        sharpe = ((mean_return - daily_rf) / std_return) * math.sqrt(252)

        return sharpe

    @staticmethod
    def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        """
        소르티노 비율 (하방 위험 대비 수익률)

        Args:
            returns: 일별 수익률 리스트
            risk_free_rate: 무위험 수익률

        Returns:
            소르티노 비율
        """
        if not returns or len(returns) < 2:
            return 0.0

        returns_series = pd.Series(returns)

        # 평균 수익률
        mean_return = returns_series.mean()

        # 하방 편차 (음수 수익률만)
        downside_returns = returns_series[returns_series < 0]
        if len(downside_returns) == 0:
            return 0.0

        downside_std = downside_returns.std()

        if downside_std == 0:
            return 0.0

        # 일별 무위험 수익률
        daily_rf = risk_free_rate / 252

        # 소르티노 비율 (연율화)
        sortino = ((mean_return - daily_rf) / downside_std) * math.sqrt(252)

        return sortino

    @staticmethod
    def calculate_calmar_ratio(returns: List[float], max_drawdown: float) -> float:
        """
        칼마 비율 (MDD 대비 수익률)

        Args:
            returns: 일별 수익률 리스트
            max_drawdown: 최대 낙폭 (%)

        Returns:
            칼마 비율
        """
        if not returns or max_drawdown == 0:
            return 0.0

        # 연율 수익률
        total_return = sum(returns)
        annual_return = (total_return / len(returns)) * 252

        # 칼마 비율
        calmar = annual_return / (max_drawdown / 100)

        return calmar

    @staticmethod
    def calculate_win_loss_ratio(winning_trades: int, losing_trades: int) -> float:
        """승패 비율"""
        if losing_trades == 0:
            # JSON 직렬화를 위해 inf 대신 큰 값 사용
            return 999.0 if winning_trades > 0 else 0.0

        return winning_trades / losing_trades

    @staticmethod
    def calculate_expectancy(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        기대값 (1회 거래당 기대 수익)

        Args:
            win_rate: 승률 (0-100)
            avg_win: 평균 수익
            avg_loss: 평균 손실

        Returns:
            기대값
        """
        win_rate_decimal = win_rate / 100
        loss_rate = 1 - win_rate_decimal

        expectancy = (win_rate_decimal * avg_win) + (loss_rate * avg_loss)

        return expectancy

    @staticmethod
    def analyze_trade_duration(trades: List[Dict]) -> Dict:
        """
        거래 보유 기간 분석

        Returns:
            {
                "avg_holding_days": 평균 보유 일수,
                "min_holding_days": 최소 보유 일수,
                "max_holding_days": 최대 보유 일수,
                "median_holding_days": 중앙값
            }
        """
        holding_days = []

        for trade in trades:
            if trade.get("holding_days") is not None:
                holding_days.append(trade["holding_days"])

        if not holding_days:
            return {
                "avg_holding_days": 0,
                "min_holding_days": 0,
                "max_holding_days": 0,
                "median_holding_days": 0
            }

        return {
            "avg_holding_days": round(sum(holding_days) / len(holding_days), 2),
            "min_holding_days": min(holding_days),
            "max_holding_days": max(holding_days),
            "median_holding_days": round(pd.Series(holding_days).median(), 2)
        }

    @staticmethod
    def analyze_exit_reasons(trades: List[Dict]) -> Dict:
        """
        청산 이유 분석

        Returns:
            {
                "take_profit": 익절 횟수,
                "stop_loss": 손절 횟수,
                "trailing_stop": 트레일링 스톱 횟수,
                "time_limit": 시간 제한 횟수,
                ...
            }
        """
        exit_reasons = {}

        for trade in trades:
            reason = trade.get("exit_reason", "unknown")
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

        return exit_reasons

    @staticmethod
    def calculate_consecutive_stats(trades: List[Dict]) -> Dict:
        """
        연속 승/패 통계

        Returns:
            {
                "max_consecutive_wins": 최대 연승,
                "max_consecutive_losses": 최대 연패,
                "current_streak": 현재 연속 기록
            }
        """
        if not trades:
            return {
                "max_consecutive_wins": 0,
                "max_consecutive_losses": 0,
                "current_streak": 0
            }

        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for trade in trades:
            profit = trade.get("profit_loss", 0)

            if profit > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif profit < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        current_streak = current_wins if current_wins > 0 else -current_losses

        return {
            "max_consecutive_wins": max_wins,
            "max_consecutive_losses": max_losses,
            "current_streak": current_streak
        }

    @staticmethod
    def calculate_monthly_returns(portfolio_history: List[Dict]) -> List[Dict]:
        """
        월별 수익률 계산

        Returns:
            [{"month": "2024-01", "return": 5.2, "trades": 10}, ...]
        """
        if not portfolio_history:
            return []

        df = pd.DataFrame(portfolio_history)
        df['date'] = pd.to_datetime(df['date'])
        df['month'] = df['date'].dt.to_period('M')

        monthly_data = []

        for month, group in df.groupby('month'):
            start_value = group.iloc[0]['total_value']
            end_value = group.iloc[-1]['total_value']

            monthly_return = ((end_value - start_value) / start_value) * 100

            monthly_data.append({
                "month": str(month),
                "return": round(monthly_return, 2),
                "start_value": round(start_value, 2),
                "end_value": round(end_value, 2)
            })

        return monthly_data

    @staticmethod
    def generate_enhanced_report(backtest_result: Dict) -> Dict:
        """
        향상된 백테스팅 리포트 생성

        Args:
            backtest_result: 백테스팅 결과

        Returns:
            향상된 리포트
        """
        summary = backtest_result.get("summary", {})
        trades = backtest_result.get("trades", [])
        portfolio_history = backtest_result.get("portfolio_history", [])

        # 일별 수익률 계산
        daily_returns = []
        if len(portfolio_history) > 1:
            for i in range(1, len(portfolio_history)):
                prev_value = portfolio_history[i-1]["total_value"]
                curr_value = portfolio_history[i]["total_value"]
                daily_return = (curr_value - prev_value) / prev_value
                daily_returns.append(daily_return)

        # 고급 지표 계산
        sharpe_ratio = PerformanceAnalytics.calculate_sharpe_ratio(daily_returns)
        sortino_ratio = PerformanceAnalytics.calculate_sortino_ratio(daily_returns)
        calmar_ratio = PerformanceAnalytics.calculate_calmar_ratio(
            daily_returns,
            summary.get("max_drawdown", 0)
        )

        # 기대값
        expectancy = PerformanceAnalytics.calculate_expectancy(
            summary.get("win_rate", 0),
            summary.get("avg_win", 0),
            abs(summary.get("avg_loss", 0))
        )

        # 거래 기간 분석
        duration_stats = PerformanceAnalytics.analyze_trade_duration(trades)

        # 청산 이유 분석
        exit_reasons = PerformanceAnalytics.analyze_exit_reasons(trades)

        # 연속 승/패
        consecutive_stats = PerformanceAnalytics.calculate_consecutive_stats(trades)

        # 월별 수익률
        monthly_returns = PerformanceAnalytics.calculate_monthly_returns(portfolio_history)

        # 승패 비율
        win_loss_ratio = PerformanceAnalytics.calculate_win_loss_ratio(
            summary.get("winning_trades", 0),
            summary.get("losing_trades", 0)
        )

        return {
            **backtest_result,
            "advanced_metrics": {
                "sharpe_ratio": round(sharpe_ratio, 2),
                "sortino_ratio": round(sortino_ratio, 2),
                "calmar_ratio": round(calmar_ratio, 2),
                "expectancy": round(expectancy, 2),
                "win_loss_ratio": round(win_loss_ratio, 2),
            },
            "trade_analysis": {
                "duration": duration_stats,
                "exit_reasons": exit_reasons,
                "consecutive": consecutive_stats,
            },
            "monthly_returns": monthly_returns,
        }


def compare_strategies(results: List[Dict]) -> Dict:
    """
    여러 전략 비교

    Args:
        results: 백테스팅 결과 리스트

    Returns:
        비교 리포트
    """
    comparison = {
        "strategies": [],
        "best_roi": None,
        "best_sharpe": None,
        "best_win_rate": None,
        "lowest_mdd": None
    }

    best_roi_value = -999.0
    best_sharpe_value = -999.0
    best_win_rate_value = 0
    lowest_mdd_value = 999.0

    for result in results:
        strategy_name = result.get("config", {}).get("entry_strategy", "unknown")
        summary = result.get("summary", {})
        advanced = result.get("advanced_metrics", {})

        strategy_summary = {
            "strategy": strategy_name,
            "roi": summary.get("roi", 0),
            "sharpe_ratio": advanced.get("sharpe_ratio", 0),
            "win_rate": summary.get("win_rate", 0),
            "max_drawdown": summary.get("max_drawdown", 0),
            "total_trades": summary.get("total_trades", 0),
            "profit_factor": summary.get("profit_factor", 0)
        }

        comparison["strategies"].append(strategy_summary)

        # 최고 지표 추적
        if strategy_summary["roi"] > best_roi_value:
            best_roi_value = strategy_summary["roi"]
            comparison["best_roi"] = strategy_name

        if strategy_summary["sharpe_ratio"] > best_sharpe_value:
            best_sharpe_value = strategy_summary["sharpe_ratio"]
            comparison["best_sharpe"] = strategy_name

        if strategy_summary["win_rate"] > best_win_rate_value:
            best_win_rate_value = strategy_summary["win_rate"]
            comparison["best_win_rate"] = strategy_name

        if 0 < strategy_summary["max_drawdown"] < lowest_mdd_value:
            lowest_mdd_value = strategy_summary["max_drawdown"]
            comparison["lowest_mdd"] = strategy_name

    return comparison
