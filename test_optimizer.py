"""
Grid Search 파라미터 최적화 테스트
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

from backend.backtest.optimizer import (
    GridSearchOptimizer,
    OptimizationParams,
    quick_optimize
)


def print_section(title):
    """섹션 헤더 출력"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_best_params(params):
    """최적 파라미터 출력"""
    print("\n🏆 최적 파라미터:")
    print(f"  손절 비율: {params['stop_loss_ratio']*100:.1f}%")
    print(f"  최대 보유: {params['max_holding_days']}일")
    print(f"  진입 점수: {params['min_entry_score']}")
    print(f"  포지션 크기: {params['position_size_pct']*100:.0f}%")

    if 'take_profit_targets' in params:
        print(f"\n  익절 목표:")
        for i, target in enumerate(params['take_profit_targets'], 1):
            print(f"    {i}. {target['name']} - {target['volume_pct']*100:.0f}% 매도")


def print_performance(perf, metric_name):
    """성과 출력"""
    print(f"\n📊 성과 지표:")
    print(f"  {metric_name}: {perf.get(metric_name, 0):.2f}")
    print(f"  ROI: {perf.get('roi', 0):+.2f}%")
    print(f"  승률: {perf.get('win_rate', 0):.2f}%")
    print(f"  샤프 비율: {perf.get('sharpe_ratio', 0):.2f}")
    print(f"  MDD: {perf.get('max_drawdown', 0):.2f}%")


def print_top_results(results, metric_name):
    """상위 결과 출력"""
    print_section("상위 5개 결과")

    print(f"\n{'순위':<4} {metric_name:<15} {'ROI':<10} {'승률':<10} {'샤프비율':<10} {'MDD':<10}")
    print("-" * 70)

    for result in results:
        rank = result['rank']
        metric_val = result.get(metric_name, 0)
        roi = result.get('roi', 0)
        win_rate = result.get('win_rate', 0)
        sharpe = result.get('sharpe_ratio', 0)
        mdd = result.get('max_drawdown', 0)

        print(f"{rank:<4} {metric_val:<15.2f} {roi:<10.2f} {win_rate:<10.2f} {sharpe:<10.2f} {mdd:<10.2f}")


def print_parameter_analysis(analysis):
    """파라미터 분석 출력"""
    print_section("파라미터 분석 (상위 10개 기준)")

    most_common = analysis.get('top_10_most_common', {})

    print("\n📈 가장 많이 선택된 파라미터:")
    print(f"  손절 비율: {most_common.get('stop_loss_ratio', 0)*100:.1f}%")
    print(f"  최대 보유: {most_common.get('max_holding_days', 0)}일")
    print(f"  진입 점수: {most_common.get('min_entry_score', 0)}")
    print(f"  포지션 크기: {most_common.get('position_size_pct', 0)*100:.0f}%")


async def test_quick_optimization():
    """빠른 최적화 테스트"""
    print_section("빠른 파라미터 최적화 테스트")

    # 테스트 종목 (소수의 종목으로 빠르게)
    symbols = ["AAPL", "MSFT"]

    print(f"\n📊 종목: {', '.join(symbols)}")
    print(f"🎯 최적화 지표: 샤프 비율")
    print(f"📅 백테스팅 기간: 60일")

    print("\n⏳ 최적화 실행 중... (예상 시간: 1-3분)")

    try:
        result = await quick_optimize(
            symbols=symbols,
            market="US",
            days=60,
            metric="sharpe_ratio"
        )

        # 결과 출력
        print(f"\n✅ 최적화 완료!")
        print(f"  실행 시간: {result['execution_time_seconds']:.1f}초")
        print(f"  테스트 조합: {result['total_combinations_tested']}개")

        # 최적 파라미터
        print_best_params(result['best_params'])

        # 성과
        print_performance(result['best_performance'], 'sharpe_ratio')

        # 상위 결과
        if 'top_5_results' in result:
            print_top_results(result['top_5_results'], 'sharpe_ratio')

        # 파라미터 분석
        if 'parameter_analysis' in result:
            print_parameter_analysis(result['parameter_analysis'])

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


async def test_full_grid_search():
    """전체 Grid Search 테스트"""
    print_section("전체 Grid Search 최적화 테스트")

    # 테스트 종목
    symbols = ["AAPL"]

    # 제한된 파라미터 범위 (테스트용)
    param_ranges = OptimizationParams(
        stop_loss_ratios=[-0.015, -0.02],
        take_profit_ratios=[0.03, 0.04],
        max_holding_days_options=[5, 7],
        min_entry_scores=[60, 65],
        position_size_pcts=[0.3]
    )

    total_combinations = param_ranges.get_total_combinations()

    print(f"\n📊 종목: {', '.join(symbols)}")
    print(f"🎯 최적화 지표: ROI")
    print(f"📅 백테스팅 기간: 60일")
    print(f"🔢 전체 조합 수: {total_combinations}개")

    print("\n⏳ 최적화 실행 중... (예상 시간: 2-5분)")

    try:
        optimizer = GridSearchOptimizer(
            param_ranges=param_ranges,
            optimization_metric="roi"
        )

        result = await optimizer.optimize(
            symbols=symbols,
            market="US",
            days=60
        )

        # 결과 출력
        print(f"\n✅ 최적화 완료!")
        print(f"  실행 시간: {result['execution_time_seconds']:.1f}초")
        print(f"  테스트 조합: {result['total_combinations_tested']}개")

        # 최적 파라미터
        print_best_params(result['best_params'])

        # 성과
        print_performance(result['best_performance'], 'roi')

        # 상위 결과
        if 'top_5_results' in result:
            print_top_results(result['top_5_results'], 'roi')

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """메인 테스트"""
    print("\n" + "🔧 " * 20)
    print("Grid Search 파라미터 최적화 테스트")
    print("🔧 " * 20)

    # 1. 빠른 최적화 테스트
    await test_quick_optimization()

    # 2. 전체 Grid Search (선택적)
    print("\n\n" + "─" * 80)
    print("\n💡 전체 Grid Search는 시간이 오래 걸립니다.")
    print("   빠른 최적화 결과로 충분하다면 스킵하세요.")

    # 자동으로 스킵 (필요시 주석 해제)
    # await test_full_grid_search()

    print_section("테스트 완료")
    print("\nAPI 엔드포인트 사용 예시:")
    print("  POST http://localhost:8000/optimize/quick")
    print("  Body: {")
    print('    "symbols": ["AAPL", "MSFT"],')
    print('    "market": "US",')
    print('    "days": 60,')
    print('    "optimization_metric": "sharpe_ratio"')
    print("  }")


if __name__ == "__main__":
    asyncio.run(main())
