"""
1달러 미만 주식 필터링 기능 테스트
"""
import asyncio
import sys
from pathlib import Path

# Windows 콘솔 인코딩 설정
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 백엔드 모듈 임포트를 위한 경로 설정
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.us.yfinance_client import get_penny_stocks_with_volume_pattern


async def main():
    print("=" * 60)
    print("1달러 미만 미국 주식 필터링 테스트")
    print("=" * 60)
    print("\n필터 조건:")
    print("  1. 주가 < $1")
    print("  2. 당일 거래량 >= 전일 거래량 x 2 (급증)")
    print("  3. D-2, D-1 거래량 < D-3 거래량")
    print("\n데이터 수집 중...\n")

    try:
        results = await get_penny_stocks_with_volume_pattern(limit=30)

        if not results:
            print("⚠️  조건에 맞는 주식을 찾지 못했습니다.")
            print("   (시장이 휴장이거나 조건이 매우 엄격할 수 있습니다)")
            return

        print(f"✅ 총 {len(results)}개 종목 발견\n")
        print("-" * 100)
        print(f"{'종목코드':<10} {'회사명':<30} {'가격($)':<10} {'변동률(%)':<12} {'당일거래량':<15} {'급증배율':<10}")
        print("-" * 100)

        for stock in results:
            code = stock["code"]
            name = stock["name"][:28]  # 이름 길이 제한
            price = stock["price"]
            change_rate = stock["change_rate"]
            volume = stock["volume"]
            surge_ratio = stock["volume_pattern"]["surge_ratio"]

            print(f"{code:<10} {name:<30} ${price:<9.2f} {change_rate:>+10.2f}% {volume:>14,} {surge_ratio:>9.2f}x")

        print("-" * 100)
        print("\n거래량 패턴 상세 (상위 5개):\n")

        for i, stock in enumerate(results[:5], 1):
            vol = stock["volume_pattern"]
            print(f"{i}. {stock['code']} - {stock['name']}")
            print(f"   D-3: {vol['d3']:,} → D-2: {vol['d2']:,} → D-1: {vol['d1']:,} → D-0 (당일): {vol['d0']:,}")
            print(f"   급증 비율: {vol['surge_ratio']:.2f}배\n")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
