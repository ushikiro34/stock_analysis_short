"""
백테스팅 시스템 테스트
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Windows 콘솔 인코딩 설정
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 백엔드 모듈 임포트를 위한 경로 설정
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.backtest.engine import BacktestConfig, run_simple_backtest
from backend.backtest.analytics import PerformanceAnalytics


def print_section(title):
    """섹션 헤더 출력"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_summary(summary):
    """요약 정보 출력"""
    print(f"\n💰 초기 자본금: ${summary['initial_capital']:,.2f}")
    print(f"💵 최종 자본금: ${summary['final_capital']:,.2f}")
    print(f"📈 순수익: ${summary['net_profit']:,.2f}")
    print(f"📊 수익률(ROI): {summary['roi']:+.2f}%")
    print(f"\n📋 총 거래 수: {summary['total_trades']}")
    print(f"✅ 수익 거래: {summary['winning_trades']}")
    print(f"❌ 손실 거래: {summary['losing_trades']}")
    print(f"🎯 승률: {summary['win_rate']:.2f}%")
    print(f"💹 손익비: {summary['profit_factor']:.2f}")
    print(f"📉 최대 낙폭(MDD): {summary['max_drawdown']:.2f}%")
    print(f"\n💚 평균 수익: ${summary['avg_win']:,.2f}")
    print(f"💔 평균 손실: ${summary['avg_loss']:,.2f}")


def print_advanced_metrics(metrics):
    """고급 지표 출력"""
    print_section("고급 성과 지표")
    print(f"📊 샤프 비율: {metrics['sharpe_ratio']:.2f}")
    print(f"📊 소르티노 비율: {metrics['sortino_ratio']:.2f}")
    print(f"📊 칼마 비율: {metrics['calmar_ratio']:.2f}")
    print(f"💰 기대값: ${metrics['expectancy']:.2f}")
    print(f"⚖️  승패 비율: {metrics['win_loss_ratio']:.2f}")


def print_trade_analysis(analysis):
    """거래 분석 출력"""
    print_section("거래 분석")

    # 보유 기간
    duration = analysis['duration']
    print(f"\n⏱️  보유 기간:")
    print(f"  평균: {duration['avg_holding_days']:.1f}일")
    print(f"  최소: {duration['min_holding_days']}일")
    print(f"  최대: {duration['max_holding_days']}일")
    print(f"  중앙값: {duration['median_holding_days']:.1f}일")

    # 청산 이유
    exit_reasons = analysis['exit_reasons']
    print(f"\n🚪 청산 이유:")
    for reason, count in exit_reasons.items():
        print(f"  {reason}: {count}회")

    # 연속 승/패
    consecutive = analysis['consecutive']
    print(f"\n🔥 연속 기록:")
    print(f"  최대 연승: {consecutive['max_consecutive_wins']}회")
    print(f"  최대 연패: {consecutive['max_consecutive_losses']}회")
    print(f"  현재 기록: {consecutive['current_streak']:+d}회")


def print_trades(trades, limit=10):
    """거래 내역 출력"""
    print_section(f"거래 내역 (최근 {min(limit, len(trades))}개)")

    if not trades:
        print("거래 내역 없음")
        return

    print(f"\n{'#':<4} {'종목':<10} {'진입가':<10} {'청산가':<10} {'손익률':<10} {'사유':<20}")
    print("-" * 80)

    for i, trade in enumerate(trades[-limit:], 1):
        profit_pct = trade['profit_loss_pct']
        profit_sign = "🟢" if profit_pct > 0 else "🔴"

        print(f"{i:<4} {trade['code']:<10} "
              f"${trade['entry_price']:<9.2f} "
              f"${trade['exit_price']:<9.2f} "
              f"{profit_sign} {profit_pct:>+7.2f}% "
              f"{trade['exit_reason']:<20}")


def print_best_worst(best, worst):
    """최고/최저 거래 출력"""
    if best:
        print("\n🏆 최고 수익 거래:")
        print(f"  종목: {best['code']}")
        print(f"  수익률: +{best['profit_loss_pct']:.2f}%")
        print(f"  수익: ${best['profit_loss']:,.2f}")

    if worst:
        print("\n💀 최악 손실 거래:")
        print(f"  종목: {worst['code']}")
        print(f"  손실률: {worst['profit_loss_pct']:.2f}%")
        print(f"  손실: ${worst['profit_loss']:,.2f}")


async def test_simple_backtest():
    """간단한 백테스팅 테스트"""
    print_section("단일 전략 백테스팅")

    # 테스트 종목 (미국 주식 - 데이터 접근 용이)
    symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]

    # 백테스팅 설정
    config = BacktestConfig(
        initial_capital=10000.0,
        entry_strategy="combined",
        min_entry_score=60.0,
        stop_loss_ratio=-0.02,
        max_holding_days=5
    )

    # 기간 설정 (최근 90일)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    print(f"\n📅 백테스팅 기간: {start_date.date()} ~ {end_date.date()}")
    print(f"📊 종목: {', '.join(symbols)}")
    print(f"💰 초기 자본금: ${config.initial_capital:,.2f}")
    print(f"🎯 전략: {config.entry_strategy}")
    print(f"⚡ 최소 진입 점수: {config.min_entry_score}")
    print(f"🛑 손절 비율: {config.stop_loss_ratio*100:.1f}%")
    print(f"⏱️  최대 보유: {config.max_holding_days}일")

    print("\n⏳ 백테스팅 실행 중...")

    try:
        # 백테스팅 실행
        result = await run_simple_backtest(
            symbols=symbols,
            market="US",
            start_date=start_date,
            end_date=end_date,
            config=config
        )

        # 향상된 분석
        enhanced_result = PerformanceAnalytics.generate_enhanced_report(result)

        # 결과 출력
        print_section("백테스팅 결과 요약")
        print_summary(enhanced_result['summary'])

        # 고급 지표
        if 'advanced_metrics' in enhanced_result:
            print_advanced_metrics(enhanced_result['advanced_metrics'])

        # 거래 분석
        if 'trade_analysis' in enhanced_result:
            print_trade_analysis(enhanced_result['trade_analysis'])

        # 거래 내역
        print_trades(enhanced_result.get('trades', []), limit=10)

        # 최고/최저
        print_best_worst(
            enhanced_result.get('best_trade'),
            enhanced_result.get('worst_trade')
        )

        # 월별 수익률
        if 'monthly_returns' in enhanced_result and enhanced_result['monthly_returns']:
            print_section("월별 수익률")
            for monthly in enhanced_result['monthly_returns']:
                sign = "🟢" if monthly['return'] > 0 else "🔴"
                print(f"{monthly['month']}: {sign} {monthly['return']:+.2f}%")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


async def test_strategy_comparison():
    """전략 비교 테스트"""
    print_section("전략 비교 백테스팅")

    symbols = ["AAPL", "MSFT"]
    strategies = ["volume", "technical", "combined"]

    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)

    print(f"\n📅 백테스팅 기간: {start_date.date()} ~ {end_date.date()}")
    print(f"📊 종목: {', '.join(symbols)}")
    print(f"🎯 비교 전략: {', '.join(strategies)}")

    print("\n⏳ 백테스팅 실행 중...")

    try:
        results = []

        for strategy in strategies:
            print(f"\n  ▶ {strategy} 전략 실행 중...")

            config = BacktestConfig(
                initial_capital=10000.0,
                entry_strategy=strategy,
                min_entry_score=60.0
            )

            result = await run_simple_backtest(
                symbols=symbols,
                market="US",
                start_date=start_date,
                end_date=end_date,
                config=config
            )

            enhanced_result = PerformanceAnalytics.generate_enhanced_report(result)
            results.append(enhanced_result)

        # 전략 비교
        from backend.backtest.analytics import compare_strategies
        comparison = compare_strategies(results)

        print_section("전략 비교 결과")

        print(f"\n{'전략':<15} {'수익률':<12} {'샤프비율':<12} {'승률':<10} {'MDD':<10} {'거래수':<8}")
        print("-" * 80)

        for strategy_data in comparison['strategies']:
            print(f"{strategy_data['strategy']:<15} "
                  f"{strategy_data['roi']:>+10.2f}% "
                  f"{strategy_data['sharpe_ratio']:>10.2f} "
                  f"{strategy_data['win_rate']:>8.1f}% "
                  f"{strategy_data['max_drawdown']:>8.2f}% "
                  f"{strategy_data['total_trades']:>6}")

        print(f"\n🏆 최고 수익률: {comparison['best_roi']}")
        print(f"🏆 최고 샤프비율: {comparison['best_sharpe']}")
        print(f"🏆 최고 승률: {comparison['best_win_rate']}")
        print(f"🏆 최저 MDD: {comparison['lowest_mdd']}")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """메인 테스트"""
    print("\n" + "🎯 " * 20)
    print("백테스팅 시스템 테스트")
    print("🎯 " * 20)

    # 1. 단일 전략 백테스팅
    await test_simple_backtest()

    # 2. 전략 비교 (선택적 - 주석 처리)
    # print("\n\n" + "─" * 80)
    # await test_strategy_comparison()

    print_section("테스트 완료")
    print("\nAPI 엔드포인트 사용 예시:")
    print("  POST http://localhost:8000/backtest/run")
    print("  Body: {")
    print('    "symbols": ["AAPL", "MSFT", "GOOGL"],')
    print('    "market": "US",')
    print('    "days": 90,')
    print('    "initial_capital": 10000,')
    print('    "entry_strategy": "combined"')
    print("  }")


if __name__ == "__main__":
    asyncio.run(main())
