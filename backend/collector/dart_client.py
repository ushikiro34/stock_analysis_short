"""
OpenDART API 클라이언트
전자공시 시스템(DART)에서 당일 공시 정보를 조회합니다.
API 키: DART_API_KEY 환경변수
"""
import logging
import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

DART_BASE = "https://opendart.fss.or.kr/api"

# 관심 공시 유형 키워드 (report_nm 필드 매칭)
_DART_TYPE_PATTERNS = [
    ("CB발행",      ["전환사채권발행결정", "전환사채"]),
    ("BW발행",      ["신주인수권부사채권발행결정", "신주인수권부사채"]),
    ("자사주취득",  ["자기주식취득결정", "자기주식처분결정"]),
    ("유상증자",    ["유상증자결정"]),
    ("대규모계약",  ["단일판매", "공급계약체결", "수주공시"]),
    ("합병·인수",   ["합병결정", "영업양수결정", "주식의포괄적교환"]),
    ("실적발표",    ["잠정실적", "영업실적", "결산실적"]),
    ("투자결정",    ["타법인주식및출자증권취득결정", "유형자산취득결정"]),
]


def _classify_dart_type(report_nm: str) -> Optional[str]:
    """report_nm → 공시 유형 분류"""
    for dtype, keywords in _DART_TYPE_PATTERNS:
        for kw in keywords:
            if kw in report_nm:
                return dtype
    return None


# 코드 → stock_code 캐시 (당일 1회)
_corp_code_cache: dict = {}
_corp_cache_date: str = ""


async def _get_corp_stock_map() -> dict:
    """전체 법인코드 zip 다운로드 → {corp_code: stock_code} 맵 (당일 캐시)"""
    global _corp_code_cache, _corp_cache_date

    today = datetime.now().strftime("%Y%m%d")
    if _corp_cache_date == today and _corp_code_cache:
        return _corp_code_cache

    api_key = os.getenv("DART_API_KEY", "")
    if not api_key:
        return {}

    def _fetch():
        import zipfile
        import io
        import xml.etree.ElementTree as ET
        try:
            resp = httpx.get(
                f"{DART_BASE}/corpCode.xml",
                params={"crtfc_key": api_key},
                timeout=30,
            )
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                xml_data = z.read(z.namelist()[0])
            root = ET.fromstring(xml_data)
            mapping = {}
            for item in root.findall("list"):
                corp_code = (item.findtext("corp_code") or "").strip()
                stock_code = (item.findtext("stock_code") or "").strip()
                if corp_code and stock_code:
                    mapping[corp_code] = stock_code
            return mapping
        except Exception as e:
            logger.warning(f"[DART] 법인코드 맵 로드 실패: {e}")
            return {}

    loop = asyncio.get_event_loop()
    _corp_code_cache = await loop.run_in_executor(None, _fetch)
    _corp_cache_date = today
    logger.info(f"[DART] 법인코드 맵 로드: {len(_corp_code_cache)}개")
    return _corp_code_cache


async def fetch_today_disclosures(date_str: Optional[str] = None) -> List[dict]:
    """
    당일(또는 지정일) 공시 목록 조회.
    전날 마감 공시(~23:59)도 포함하기 위해 bgn_de = 전일로 설정.

    Returns:
        List of {
            corp_name, stock_code, report_nm, rcept_dt, rcept_no,
            dart_type, dart_url
        }
    """
    api_key = os.getenv("DART_API_KEY", "")
    if not api_key:
        logger.warning("[DART] DART_API_KEY 미설정 — 공시 조회 생략")
        return []

    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    # 전일 포함 (전날 17시 이후 공시도 수집)
    prev_date = (datetime.strptime(date_str, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")

    # 법인코드 → stock_code 맵
    corp_map = await _get_corp_stock_map()

    def _fetch():
        results = []
        try:
            resp = httpx.get(
                f"{DART_BASE}/list.json",
                params={
                    "crtfc_key": api_key,
                    "bgn_de": prev_date,
                    "end_de": date_str,
                    "page_count": 100,
                    "sort": "date",
                    "sort_mth": "desc",
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("list", [])
            logger.info(f"[DART] 공시 {len(items)}건 조회 ({prev_date}~{date_str})")

            for item in items:
                report_nm = item.get("report_nm", "")
                dart_type = _classify_dart_type(report_nm)
                if not dart_type:
                    continue  # 관심 공시 아님

                corp_code = item.get("corp_code", "")
                stock_code = corp_map.get(corp_code, "")
                # stock_code 없으면 건너뜀 (비상장 법인)
                if not stock_code:
                    continue

                rcept_no = item.get("rcept_no", "")
                results.append({
                    "corp_name":   item.get("corp_name", ""),
                    "stock_code":  stock_code,
                    "report_nm":   report_nm,
                    "rcept_dt":    item.get("rcept_dt", ""),
                    "rcept_no":    rcept_no,
                    "dart_type":   dart_type,
                    "dart_url":    f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
                })

        except Exception as e:
            logger.error(f"[DART] 공시 조회 오류: {e}")

        return results

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch)
