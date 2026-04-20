"""
장전 뉴스 RSS 크롤러
네이버 금융, 한국경제, 매일경제 RSS를 수집합니다.
"""
import asyncio
import logging
from typing import List

import httpx

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    {
        "name": "네이버금융",
        "url": "https://finance.naver.com/news/news_list.nhn?mode=LSS3D&section_id=101&section_id2=258&rss=1",
    },
    {
        "name": "한국경제",
        "url": "https://www.hankyung.com/feed/stock-market",
    },
    {
        "name": "매일경제",
        "url": "https://www.mk.co.kr/rss/40300001/",
    },
    {
        "name": "연합인포맥스",
        "url": "https://news.einfomax.co.kr/rss/allArticle.xml",
    },
]


def _parse_feed(xml_text: str, source_name: str) -> List[dict]:
    """RSS XML 파싱 → [{title, link, published, source}]"""
    try:
        import feedparser
        feed = feedparser.parse(xml_text)
        items = []
        for entry in feed.entries[:30]:  # 최신 30개
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            published = entry.get("published", "") or entry.get("updated", "")
            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "published": published,
                    "source": source_name,
                })
        return items
    except Exception as e:
        logger.warning(f"[News] RSS 파싱 오류 ({source_name}): {e}")
        return []


async def _fetch_feed(feed: dict) -> List[dict]:
    """단일 RSS 피드 비동기 조회"""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(
                feed["url"],
                headers={"User-Agent": "Mozilla/5.0 StockBot/1.0"},
            )
            resp.raise_for_status()

        loop = asyncio.get_event_loop()
        items = await loop.run_in_executor(
            None, _parse_feed, resp.text, feed["name"]
        )
        logger.info(f"[News] {feed['name']}: {len(items)}건")
        return items
    except Exception as e:
        logger.warning(f"[News] {feed['name']} 조회 실패: {e}")
        return []


async def fetch_all_news() -> List[dict]:
    """모든 RSS 피드 병렬 조회 → 중복 제거 후 반환"""
    results = await asyncio.gather(*[_fetch_feed(f) for f in RSS_FEEDS])

    # 중복 제거 (제목 앞 30자 기준)
    seen = set()
    merged = []
    for items in results:
        for item in items:
            key = item["title"][:30]
            if key not in seen:
                seen.add(key)
                merged.append(item)

    logger.info(f"[News] 총 {len(merged)}건 수집")
    return merged
