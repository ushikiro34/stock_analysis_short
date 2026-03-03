"""
Sectors API Router
섹터별 실시간 분석 엔드포인트
"""
from fastapi import APIRouter, Query
from typing import List, Optional
import logging

from ...sectors.sector_config import SectorType, get_all_sectors, get_sector_info
from ...sectors.sector_analyzer import SectorAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sectors", tags=["📊 Sectors"])

# Sector Analyzer 인스턴스
sector_analyzer = SectorAnalyzer()


@router.get("/list")
async def list_sectors():
    """
    사용 가능한 섹터 목록 조회

    Returns:
        [
            {
                "sector": "technology",
                "name": "🚀 기술주",
                "stocks": [...],
                "stock_count": 10
            },
            ...
        ]
    """
    sectors = get_all_sectors()
    return [get_sector_info(sector) for sector in sectors]


@router.get("/{sector}/analyze")
async def analyze_sector(
    sector: SectorType,
    days: int = Query(default=30, ge=7, le=90, description="분석 기간 (일)")
):
    """
    특정 섹터 실시간 분석

    Args:
        sector: 섹터 타입 (technology, energy, healthcare 등)
        days: 분석 기간 (7~90일)

    Returns:
        {
            "sector": "technology",
            "sector_name": "🚀 기술주",
            "summary": {
                "total_stocks": 10,
                "avg_return": 5.2,
                "bullish_count": 7,
                "bearish_count": 3
            },
            "stocks": [...],
            "sector_strength": "strong",
            "top_performers": [...],
            "rotation_signal": "rotating_in"
        }
    """
    try:
        result = await sector_analyzer.analyze_sector(sector, days)
        return result
    except Exception as e:
        logger.error(f"Sector analysis error for {sector}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "sector": sector.value,
            "summary": {}
        }


@router.get("/compare")
async def compare_sectors(
    sectors: Optional[List[SectorType]] = Query(default=None, description="비교할 섹터 (미지정 시 전체)"),
    days: int = Query(default=30, ge=7, le=90, description="분석 기간 (일)")
):
    """
    여러 섹터 비교 분석

    Args:
        sectors: 비교할 섹터 리스트 (미지정 시 전체 섹터)
        days: 분석 기간

    Returns:
        {
            "compared_at": "2024-01-01T00:00:00",
            "sectors": [
                {
                    "sector": "technology",
                    "sector_name": "🚀 기술주",
                    "avg_return": 5.2,
                    "strength": "strong"
                },
                ...
            ],
            "strongest_sector": {...},
            "weakest_sector": {...},
            "rotating_sectors": {
                "in": ["🚀 기술주"],
                "out": ["⚡ 에너지"]
            }
        }
    """
    try:
        # 섹터 미지정 시 전체 섹터
        if not sectors:
            sectors = get_all_sectors()

        result = await sector_analyzer.compare_sectors(sectors, days)
        return result
    except Exception as e:
        logger.error(f"Sector comparison error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "sectors": []
        }


@router.get("/{sector}/signals")
async def get_sector_signals(
    sector: SectorType,
    min_score: float = Query(default=60, ge=0, le=100, description="최소 신호 점수"),
    strategy: str = Query(default="combined", description="신호 전략")
):
    """
    섹터 내 매매 신호 생성

    Args:
        sector: 섹터 타입
        min_score: 최소 신호 점수
        strategy: 신호 전략 (volume, technical, pattern, combined)

    Returns:
        [
            {
                "symbol": "AAPL",
                "signal": "BUY",
                "score": 75,
                "reasons": [...]
            },
            ...
        ]
    """
    try:
        from ...sectors.sector_config import get_sector_symbols
        from ...core.signal_service import generate_entry_signal

        symbols = get_sector_symbols(sector)
        signals = []

        for symbol in symbols:
            try:
                signal = await generate_entry_signal(symbol, market="US", strategy=strategy)

                if signal["signal"] == "BUY" and signal["score"] >= min_score:
                    signals.append({
                        "symbol": symbol,
                        "signal": signal["signal"],
                        "strength": signal["strength"],
                        "score": signal["score"],
                        "reasons": signal["reasons"],
                        "current_price": signal.get("current_price"),
                        "timestamp": signal.get("timestamp")
                    })
            except Exception as e:
                logger.error(f"Signal generation failed for {symbol}: {e}")
                continue

        # 점수 높은 순 정렬
        signals.sort(key=lambda x: x["score"], reverse=True)

        return {
            "sector": sector.value,
            "sector_name": get_sector_info(sector)["name"],
            "total_signals": len(signals),
            "signals": signals
        }

    except Exception as e:
        logger.error(f"Sector signals error for {sector}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "signals": []
        }
