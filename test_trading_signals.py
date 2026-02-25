"""
진입/청산 신호 로직 테스트
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

from backend.core.signal_service import (
    generate_entry_signal,
    generate_exit_signal,
    scan_signals_from_surge_stocks
)


async def test_entry_signal():
    """진입 신호 테스트"""
    print("=" * 80)
    print("📊 진입 신호 테스트")
    print("=" * 80)

    # 테스트 종목 (한국: 삼성전자, 미국: AAPL)
    test_stocks = [
        {"code": "005930", "market": "KR", "name": "삼성전자"},
        {"code": "AAPL", "market": "US", "name": "Apple Inc."}
    ]

    for stock in test_stocks:
        print(f"\n종목: {stock['name']} ({stock['code']}) - {stock['market']}")
        print("-" * 80)

        try:
            # Combined 전략
            signal = await generate_entry_signal(
                code=stock["code"],
                market=stock["market"],
                strategy="combined"
            )

            print(f"신호: {signal['signal']}")
            print(f"강도: {signal['strength']}")
            print(f"점수: {signal['score']}/100")
            print(f"현재가: {signal.get('current_price', 'N/A')}")

            if signal['reasons']:
                print("\n발생 이유:")
                for i, reason in enumerate(signal['reasons'], 1):
                    print(f"  {i}. {reason}")

            # Breakdown 정보
            if 'breakdown' in signal and signal['breakdown']:
                print("\n세부 점수:")
                bd = signal['breakdown']
                if 'volume' in bd:
                    print(f"  - 거래량: {bd['volume']['score']}/100")
                if 'technical' in bd:
                    print(f"  - 기술적: {bd['technical']['score']}/100")
                if 'pattern' in bd:
                    print(f"  - 패턴: {bd['pattern']['score']}/100")

        except Exception as e:
            print(f"❌ 오류: {e}")
            import traceback
            traceback.print_exc()


async def test_exit_signal():
    """청산 신호 테스트"""
    print("\n" + "=" * 80)
    print("📉 청산 신호 테스트")
    print("=" * 80)

    # 시뮬레이션 시나리오
    scenarios = [
        {
            "name": "익절 시나리오 (+5%)",
            "code": "AAPL",
            "market": "US",
            "entry_price": 100.0,
            "current_price_offset": 1.05,  # +5%
            "minutes_ago": 15
        },
        {
            "name": "손절 시나리오 (-3%)",
            "code": "005930",
            "market": "KR",
            "entry_price": 70000,
            "current_price_offset": 0.97,  # -3%
            "minutes_ago": 10
        },
        {
            "name": "시간 초과 시나리오 (35분)",
            "code": "AAPL",
            "market": "US",
            "entry_price": 150.0,
            "current_price_offset": 1.01,  # +1%
            "minutes_ago": 35
        }
    ]

    for scenario in scenarios:
        print(f"\n시나리오: {scenario['name']}")
        print("-" * 80)

        entry_time = datetime.now() - timedelta(minutes=scenario['minutes_ago'])

        # 실제 현재가 조회는 API를 사용하므로, 여기서는 시뮬레이션
        print(f"종목: {scenario['code']} ({scenario['market']})")
        print(f"진입 가격: {scenario['entry_price']:,.2f}")
        print(f"진입 시각: {entry_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"경과 시간: {scenario['minutes_ago']}분")

        # 주의: 실제 API를 호출하면 현재가를 조회하지만
        # 테스트에서는 오프셋을 사용한 시뮬레이션만 수행
        expected_current = scenario['entry_price'] * scenario['current_price_offset']
        print(f"예상 현재가: {expected_current:,.2f}")

        profit_pct = (scenario['current_price_offset'] - 1) * 100
        print(f"예상 손익률: {profit_pct:+.2f}%")

        print("\n[실제 API 호출은 생략 - 시뮬레이션만 표시]")
        print("실제 사용 시:")
        print(f"  result = await generate_exit_signal(")
        print(f"      code='{scenario['code']}',")
        print(f"      entry_price={scenario['entry_price']},")
        print(f"      entry_time={entry_time},")
        print(f"      market='{scenario['market']}'")
        print(f"  )")


async def test_signal_scan():
    """급등주 스캔 테스트"""
    print("\n" + "=" * 80)
    print("🔍 급등주 진입 신호 스캔 테스트")
    print("=" * 80)

    markets = ["US"]  # KR은 API 키 필요할 수 있음

    for market in markets:
        print(f"\n시장: {market}")
        print("-" * 80)

        try:
            signals = await scan_signals_from_surge_stocks(
                market=market,
                strategy="combined",
                min_score=50  # 점수 50점 이상
            )

            if not signals:
                print("⚠️  조건에 맞는 신호가 없습니다.")
                continue

            print(f"✅ {len(signals)}개 신호 발견\n")

            # 상위 5개만 출력
            for i, signal in enumerate(signals[:5], 1):
                print(f"{i}. {signal['code']} - {signal.get('stock_info', {}).get('name', 'N/A')}")
                print(f"   신호: {signal['signal']} ({signal['strength']})")
                print(f"   점수: {signal['score']}/100")
                print(f"   현재가: ${signal.get('current_price', 0):.2f}")

                if signal['reasons']:
                    print(f"   이유: {', '.join(signal['reasons'][:3])}")
                print()

        except Exception as e:
            print(f"❌ 오류: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """메인 테스트 실행"""
    print("\n" + "🚀 " * 20)
    print("단타매매 신호 로직 테스트")
    print("🚀 " * 20 + "\n")

    # 1. 진입 신호 테스트
    await test_entry_signal()

    # 2. 청산 신호 테스트 (시뮬레이션)
    await test_exit_signal()

    # 3. 급등주 스캔 테스트
    await test_signal_scan()

    print("\n" + "=" * 80)
    print("✅ 테스트 완료")
    print("=" * 80)
    print("\nAPI 엔드포인트 사용 예시:")
    print("  - 진입 신호: GET http://localhost:8000/signals/entry/AAPL?market=US")
    print("  - 신호 스캔: GET http://localhost:8000/signals/scan?market=US&min_score=60")
    print("  - 청산 신호: POST http://localhost:8000/signals/exit")
    print("    Body: {")
    print('      "code": "AAPL",')
    print('      "entry_price": 150.0,')
    print('      "entry_time": "2024-01-01T09:30:00",')
    print('      "market": "US"')
    print("    }")


if __name__ == "__main__":
    asyncio.run(main())
