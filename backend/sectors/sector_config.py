"""
Sector Configuration
섹터별 종목 분류 및 설정
"""
from typing import Dict, List
from enum import Enum


class SectorType(str, Enum):
    """섹터 타입"""
    TECHNOLOGY = "technology"
    ENERGY = "energy"
    HEALTHCARE = "healthcare"
    FINANCIALS = "financials"
    CONSUMER = "consumer"
    INDUSTRIALS = "industrials"
    REAL_ESTATE = "real_estate"
    UTILITIES = "utilities"
    COMMUNICATION = "communication"
    ENTERTAINMENT = "entertainment"


# 섹터별 대표 종목 (미국 시장)
US_SECTOR_STOCKS: Dict[SectorType, List[Dict]] = {
    SectorType.TECHNOLOGY: [
        {"symbol": "AAPL", "name": "Apple Inc.", "weight": 1.5},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "weight": 1.5},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "weight": 1.3},
        {"symbol": "NVDA", "name": "NVIDIA Corp.", "weight": 1.2},
        {"symbol": "AMD", "name": "Advanced Micro Devices", "weight": 1.0},
        {"symbol": "META", "name": "Meta Platforms Inc.", "weight": 1.0},
        {"symbol": "INTC", "name": "Intel Corp.", "weight": 0.8},
        {"symbol": "AVGO", "name": "Broadcom Inc.", "weight": 1.0},
        {"symbol": "CSCO", "name": "Cisco Systems", "weight": 0.8},
        {"symbol": "ORCL", "name": "Oracle Corp.", "weight": 0.8},
    ],
    SectorType.ENERGY: [
        {"symbol": "XOM", "name": "Exxon Mobil Corp.", "weight": 1.5},
        {"symbol": "CVX", "name": "Chevron Corp.", "weight": 1.5},
        {"symbol": "COP", "name": "ConocoPhillips", "weight": 1.0},
        {"symbol": "SLB", "name": "Schlumberger Ltd.", "weight": 0.9},
        {"symbol": "EOG", "name": "EOG Resources Inc.", "weight": 0.8},
        {"symbol": "MPC", "name": "Marathon Petroleum", "weight": 0.8},
        {"symbol": "PSX", "name": "Phillips 66", "weight": 0.7},
        {"symbol": "VLO", "name": "Valero Energy", "weight": 0.7},
    ],
    SectorType.HEALTHCARE: [
        {"symbol": "JNJ", "name": "Johnson & Johnson", "weight": 1.5},
        {"symbol": "UNH", "name": "UnitedHealth Group", "weight": 1.5},
        {"symbol": "PFE", "name": "Pfizer Inc.", "weight": 1.2},
        {"symbol": "ABBV", "name": "AbbVie Inc.", "weight": 1.0},
        {"symbol": "TMO", "name": "Thermo Fisher Scientific", "weight": 1.0},
        {"symbol": "MRK", "name": "Merck & Co.", "weight": 1.0},
        {"symbol": "LLY", "name": "Eli Lilly and Co.", "weight": 1.2},
        {"symbol": "ABT", "name": "Abbott Laboratories", "weight": 0.9},
    ],
    SectorType.FINANCIALS: [
        {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "weight": 1.5},
        {"symbol": "BAC", "name": "Bank of America", "weight": 1.3},
        {"symbol": "WFC", "name": "Wells Fargo & Co.", "weight": 1.2},
        {"symbol": "GS", "name": "Goldman Sachs Group", "weight": 1.0},
        {"symbol": "MS", "name": "Morgan Stanley", "weight": 1.0},
        {"symbol": "C", "name": "Citigroup Inc.", "weight": 1.0},
        {"symbol": "BLK", "name": "BlackRock Inc.", "weight": 0.9},
        {"symbol": "SCHW", "name": "Charles Schwab Corp.", "weight": 0.8},
    ],
    SectorType.CONSUMER: [
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "weight": 1.5},
        {"symbol": "TSLA", "name": "Tesla Inc.", "weight": 1.5},
        {"symbol": "HD", "name": "Home Depot Inc.", "weight": 1.2},
        {"symbol": "MCD", "name": "McDonald's Corp.", "weight": 1.0},
        {"symbol": "NKE", "name": "Nike Inc.", "weight": 1.0},
        {"symbol": "SBUX", "name": "Starbucks Corp.", "weight": 0.9},
        {"symbol": "TGT", "name": "Target Corp.", "weight": 0.8},
        {"symbol": "LOW", "name": "Lowe's Companies", "weight": 0.9},
    ],
    SectorType.INDUSTRIALS: [
        {"symbol": "BA", "name": "Boeing Co.", "weight": 1.2},
        {"symbol": "CAT", "name": "Caterpillar Inc.", "weight": 1.2},
        {"symbol": "GE", "name": "General Electric", "weight": 1.0},
        {"symbol": "UPS", "name": "United Parcel Service", "weight": 1.0},
        {"symbol": "HON", "name": "Honeywell International", "weight": 1.0},
        {"symbol": "LMT", "name": "Lockheed Martin", "weight": 0.9},
        {"symbol": "RTX", "name": "Raytheon Technologies", "weight": 0.9},
        {"symbol": "DE", "name": "Deere & Co.", "weight": 0.8},
    ],
    SectorType.REAL_ESTATE: [
        {"symbol": "AMT", "name": "American Tower Corp.", "weight": 1.5},
        {"symbol": "PLD", "name": "Prologis Inc.", "weight": 1.3},
        {"symbol": "SPG", "name": "Simon Property Group", "weight": 1.2},
        {"symbol": "EQIX", "name": "Equinix Inc.", "weight": 1.0},
        {"symbol": "PSA", "name": "Public Storage", "weight": 0.9},
        {"symbol": "O", "name": "Realty Income Corp.", "weight": 0.9},
    ],
    SectorType.UTILITIES: [
        {"symbol": "NEE", "name": "NextEra Energy", "weight": 1.5},
        {"symbol": "DUK", "name": "Duke Energy", "weight": 1.2},
        {"symbol": "SO", "name": "Southern Co.", "weight": 1.2},
        {"symbol": "D", "name": "Dominion Energy", "weight": 1.0},
        {"symbol": "AEP", "name": "American Electric Power", "weight": 1.0},
        {"symbol": "EXC", "name": "Exelon Corp.", "weight": 0.9},
    ],
    SectorType.COMMUNICATION: [
        {"symbol": "T", "name": "AT&T Inc.", "weight": 1.3},
        {"symbol": "VZ", "name": "Verizon Communications", "weight": 1.3},
        {"symbol": "TMUS", "name": "T-Mobile US Inc.", "weight": 1.2},
        {"symbol": "CHTR", "name": "Charter Communications", "weight": 0.9},
        {"symbol": "CMCSA", "name": "Comcast Corp.", "weight": 1.0},
    ],
    SectorType.ENTERTAINMENT: [
        {"symbol": "DIS", "name": "Walt Disney Co.", "weight": 1.5},
        {"symbol": "NFLX", "name": "Netflix Inc.", "weight": 1.5},
        {"symbol": "WBD", "name": "Warner Bros. Discovery", "weight": 1.0},
        {"symbol": "PARA", "name": "Paramount Global", "weight": 0.8},
        {"symbol": "LYV", "name": "Live Nation Entertainment", "weight": 0.7},
    ],
}


# 섹터별 한글 이름
SECTOR_NAMES_KR: Dict[SectorType, str] = {
    SectorType.TECHNOLOGY: "🚀 기술주",
    SectorType.ENERGY: "⚡ 에너지",
    SectorType.HEALTHCARE: "💊 헬스케어",
    SectorType.FINANCIALS: "💰 금융",
    SectorType.CONSUMER: "🛒 소비재",
    SectorType.INDUSTRIALS: "🏭 산업재",
    SectorType.REAL_ESTATE: "🏠 부동산",
    SectorType.UTILITIES: "🔌 유틸리티",
    SectorType.COMMUNICATION: "📱 통신",
    SectorType.ENTERTAINMENT: "🎬 엔터테인먼트",
}


def get_sector_symbols(sector: SectorType) -> List[str]:
    """섹터의 종목 코드 리스트 반환"""
    return [stock["symbol"] for stock in US_SECTOR_STOCKS.get(sector, [])]


def get_all_sectors() -> List[SectorType]:
    """모든 섹터 리스트 반환"""
    return list(SectorType)


def get_sector_info(sector: SectorType) -> Dict:
    """섹터 정보 반환"""
    return {
        "sector": sector.value,
        "name": SECTOR_NAMES_KR.get(sector, sector.value),
        "stocks": US_SECTOR_STOCKS.get(sector, []),
        "stock_count": len(US_SECTOR_STOCKS.get(sector, []))
    }
