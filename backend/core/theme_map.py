"""
테마-종목 매핑 테이블
키워드 → 테마 → 종목 코드 매핑
"""
from typing import Dict, List

# 테마별 관련 종목 및 트리거 키워드
THEME_MAP: Dict[str, Dict] = {
    "AI반도체": {
        "keywords": ["엔비디아", "NVDA", "HBM", "AI칩", "GPU", "반도체", "파운드리", "TSMC", "AI가속기"],
        "stocks": [
            {"code": "000660", "name": "SK하이닉스"},
            {"code": "005930", "name": "삼성전자"},
            {"code": "042700", "name": "한미반도체"},
            {"code": "058470", "name": "리노공업"},
            {"code": "357780", "name": "솔브레인"},
            {"code": "000150", "name": "두산"},
        ]
    },
    "광통신": {
        "keywords": ["광통신", "광모듈", "광트랜시버", "광케이블", "데이터센터", "AI인프라", "네트워크인프라"],
        "stocks": [
            {"code": "069540", "name": "빛과전자"},
            {"code": "036800", "name": "나이스정보통신"},
            {"code": "010040", "name": "한국전선"},
            {"code": "138080", "name": "오이솔루션"},
            {"code": "189300", "name": "인텍플러스"},
        ]
    },
    "2차전지": {
        "keywords": ["배터리", "2차전지", "LFP", "전고체", "음극재", "양극재", "전해질", "리튬", "ESS"],
        "stocks": [
            {"code": "373220", "name": "LG에너지솔루션"},
            {"code": "006400", "name": "삼성SDI"},
            {"code": "051910", "name": "LG화학"},
            {"code": "096770", "name": "SK이노베이션"},
            {"code": "247540", "name": "에코프로비엠"},
            {"code": "086520", "name": "에코프로"},
        ]
    },
    "바이오": {
        "keywords": ["신약", "임상", "FDA", "바이오", "항체", "항암", "치료제", "CMO", "CDMO", "제약"],
        "stocks": [
            {"code": "068270", "name": "셀트리온"},
            {"code": "207940", "name": "삼성바이오로직스"},
            {"code": "128940", "name": "한미약품"},
            {"code": "326030", "name": "SK바이오팜"},
            {"code": "009830", "name": "한화솔루션"},
        ]
    },
    "방산": {
        "keywords": ["방산", "무기", "탄약", "미사일", "전차", "K2", "K9", "방위산업", "NATO", "우크라이나"],
        "stocks": [
            {"code": "012450", "name": "한화에어로스페이스"},
            {"code": "047050", "name": "포스코인터내셔널"},
            {"code": "064350", "name": "현대로템"},
            {"code": "079550", "name": "LIG넥스원"},
            {"code": "010140", "name": "삼성중공업"},
        ]
    },
    "조선": {
        "keywords": ["조선", "LNG선", "컨테이너선", "발주", "수주", "HD현대", "삼성중공업", "한화오션"],
        "stocks": [
            {"code": "009540", "name": "HD한국조선해양"},
            {"code": "010140", "name": "삼성중공업"},
            {"code": "042660", "name": "한화오션"},
            {"code": "329180", "name": "HD현대중공업"},
            {"code": "267250", "name": "HD현대"},
        ]
    },
    "원전": {
        "keywords": ["원전", "원자력", "SMR", "소형원자로", "핵융합", "우라늄", "두산에너빌리티"],
        "stocks": [
            {"code": "034020", "name": "두산에너빌리티"},
            {"code": "298040", "name": "효성중공업"},
            {"code": "012690", "name": "모나리자"},
            {"code": "071320", "name": "지역난방공사"},
            {"code": "123890", "name": "한국전력기술"},
        ]
    },
    "로봇": {
        "keywords": ["로봇", "휴머노이드", "자동화", "협동로봇", "레인보우로보틱스", "Boston Dynamics", "AI로봇"],
        "stocks": [
            {"code": "277810", "name": "레인보우로보틱스"},
            {"code": "215360", "name": "로보스타"},
            {"code": "090460", "name": "비에이치"},
            {"code": "348210", "name": "넥스틴"},
            {"code": "091580", "name": "상아프론테크"},
        ]
    },
    "양자컴퓨터": {
        "keywords": ["양자컴퓨터", "양자컴", "양자암호", "양자통신", "큐비트", "극저온", "크라이오"],
        "stocks": [
            {"code": "131760", "name": "파인텍"},
            {"code": "950180", "name": "오라이언"},
            {"code": "036930", "name": "주성엔지니어링"},
        ]
    },
    "K뷰티": {
        "keywords": ["화장품", "K뷰티", "뷰티", "코스메틱", "ODM", "OEM", "아모레퍼시픽", "LG생활건강"],
        "stocks": [
            {"code": "090430", "name": "아모레퍼시픽"},
            {"code": "051900", "name": "LG생활건강"},
            {"code": "214150", "name": "클리오"},
            {"code": "078520", "name": "에이블씨엔씨"},
            {"code": "002790", "name": "아모레G"},
        ]
    },
}


def match_themes(text: str) -> List[str]:
    """헤드라인/공시 텍스트에서 매칭되는 테마 이름 목록 반환"""
    matched = []
    text_lower = text.lower()
    for theme_name, info in THEME_MAP.items():
        for kw in info["keywords"]:
            if kw.lower() in text_lower:
                matched.append(theme_name)
                break
    return matched


def get_theme_stocks(theme_names: List[str]) -> List[dict]:
    """테마 이름 목록 → 관련 종목 코드 목록 (중복 제거)"""
    seen = set()
    result = []
    for theme in theme_names:
        info = THEME_MAP.get(theme)
        if not info:
            continue
        for stock in info["stocks"]:
            if stock["code"] not in seen:
                seen.add(stock["code"])
                result.append({**stock, "theme_name": theme})
    return result
