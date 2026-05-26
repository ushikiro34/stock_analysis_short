"""
장마감 후 시장 분석 브리핑
매일 15:40 KST 이후 자동 생성.

3개 레이어:
  1. 오늘 급등/급락/거래량 주목 종목
  2. 장 마감 전후 DART 공시
  3. 뉴스 + LLM → 내일 주목 종목 및 전략
"""
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
except ImportError:
    import pytz
    KST = pytz.timezone("Asia/Seoul")


async def _get_today_movers() -> dict:
    """KIS API로 오늘 급등/급락/거래량 상위 종목 수집"""
    from ..kis.rest_client import get_kis_client
    client = get_kis_client()

    try:
        # 전체 등락률 무관, 상위 200 수집
        all_stocks = await client.get_volume_rank(
            max_price=500_000, limit=200, min_change_rate=-999
        )
    except Exception as e:
        logger.warning(f"[Closing] 거래량 조회 실패: {e}")
        all_stocks = []

    # 급등 (등락률 상위 10)
    surge = sorted(
        [s for s in all_stocks if s.get("change_rate", 0) > 0],
        key=lambda x: x["change_rate"], reverse=True
    )[:10]

    # 급락 (등락률 하위 5)
    fall = sorted(
        [s for s in all_stocks if s.get("change_rate", 0) < 0],
        key=lambda x: x["change_rate"]
    )[:5]

    # 거래량 폭발 (volume 상위 10)
    vol_top = sorted(all_stocks, key=lambda x: x.get("volume", 0), reverse=True)[:10]

    # 상한가 (등락률 29% 이상)
    upper_limit = [s for s in all_stocks if s.get("change_rate", 0) >= 29.0]

    return {
        "surge": surge,
        "fall": fall,
        "volume_top": vol_top,
        "upper_limit": upper_limit,
    }


async def _llm_closing_analysis(
    movers: dict,
    dart_items: list[dict],
    news_items: list[dict],
    report_date: str,
) -> tuple[list[dict], str]:
    """
    Groq LLM으로 내일 주목 종목 추출 및 시장 분석 텍스트 생성.
    Returns: (watch_candidates, summary_text)
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return [], ""

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=api_key)

        surge_lines = [
            f"- {s['name']}({s['code']}) +{s['change_rate']}% (거래량 {s.get('volume',0):,})"
            for s in movers.get("surge", [])[:8]
        ]
        fall_lines = [
            f"- {s['name']}({s['code']}) {s['change_rate']}%"
            for s in movers.get("fall", [])[:5]
        ]
        upper_lines = [
            f"- {s['name']}({s['code']}) 상한가 {s['change_rate']}%"
            for s in movers.get("upper_limit", [])
        ]
        dart_lines = [
            f"- {d['corp_name']}({d['stock_code']}): {d['report_nm']} [{d['dart_type']}]"
            for d in dart_items[:15]
        ]
        news_lines = [
            f"[{n['source']}] {n['title']}"
            for n in news_items[:30]
        ]

        prompt = f"""오늘({report_date}) 한국 주식시장 장마감 데이터입니다.

## 오늘 급등 종목
{chr(10).join(surge_lines) if surge_lines else "없음"}

## 오늘 급락 종목
{chr(10).join(fall_lines) if fall_lines else "없음"}

## 상한가 종목
{chr(10).join(upper_lines) if upper_lines else "없음"}

## 오늘 주요 공시
{chr(10).join(dart_lines) if dart_lines else "없음"}

## 최신 뉴스 헤드라인
{chr(10).join(news_lines)}

다음 두 가지를 수행하세요:

### 1. 내일 주목 종목 추출
아래 JSON 형식으로 내일 장에서 주목할 종목을 최대 8개 추출하세요.
오늘 급등 후 눌림목 예상 종목, 공시로 내일 반응 예상 종목, 뉴스 테마 연관 종목 포함.

```json
{{"candidates": [{{"code": "6자리코드또는null", "name": "종목명", "reason": "주목 이유 1문장", "type": "모멘텀|공시|테마|눌림목"}}]}}
```

### 2. 내일 장 전망 요약
오늘 시장 흐름과 내일 주목해야 할 포인트를 3~4문장으로 요약하세요.

주의: 한국어만 사용."""

        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            stream=False,
        )
        content = resp.choices[0].message.content or ""

        # JSON 파싱
        candidates = []
        try:
            import re
            json_match = re.search(
                r'\{["\s]*candidates["\s]*:.*?\}(?=\s*```|\s*###|\s*$)',
                content, re.DOTALL
            )
            if json_match:
                parsed = json.loads(json_match.group())
                for item in parsed.get("candidates", []):
                    code = (item.get("code") or "").strip()
                    name = (item.get("name") or "").strip()
                    if name:
                        candidates.append({
                            "code": code if (code and code.isdigit() and len(code) == 6) else "",
                            "name": name,
                            "reason": (item.get("reason") or "").strip(),
                            "type": (item.get("type") or "기타").strip(),
                            "source": "llm_closing",
                        })
        except Exception as e:
            logger.warning(f"[Closing] LLM JSON 파싱 실패: {e}")

        # 요약 텍스트
        summary = ""
        try:
            after_json = content.split("###")
            if len(after_json) >= 2:
                summary = after_json[-1].strip()
                summary = summary.replace("2. 내일 장 전망 요약", "").strip()
            else:
                parts = content.split("```")
                if len(parts) >= 3:
                    summary = parts[-1].strip()
        except Exception:
            pass

        return candidates, summary

    except Exception as e:
        logger.warning(f"[Closing] LLM 호출 실패: {e}")
        return [], ""


async def generate_closing_briefing(briefing_date_str: str, db: AsyncSession) -> Optional[dict]:
    """
    특정 날짜(YYYY-MM-DD KST) 장마감 분석 생성.
    이미 존재하면 기존 데이터 반환.
    """
    from ..db.models import ClosingBriefing

    existing = (await db.execute(
        select(ClosingBriefing).where(ClosingBriefing.briefing_date == briefing_date_str)
    )).scalar_one_or_none()
    if existing:
        return _row_to_dict(existing)

    logger.info(f"[Closing] {briefing_date_str} 생성 시작")

    # 1. 오늘 주목 종목
    movers = await _get_today_movers()

    # 2. DART 공시 (오늘 전체)
    dart_items: list[dict] = []
    try:
        from ..collector.dart_client import fetch_today_disclosures
        dart_items = await fetch_today_disclosures(briefing_date_str.replace("-", ""))
    except Exception as e:
        logger.warning(f"[Closing] DART 조회 실패: {e}")

    # 3. 뉴스 RSS
    news_items: list[dict] = []
    try:
        from ..core.news_crawler import fetch_all_news
        news_items = await fetch_all_news()
    except Exception as e:
        logger.warning(f"[Closing] 뉴스 조회 실패: {e}")

    # 4. LLM 분석
    watch_candidates, ai_summary = await _llm_closing_analysis(
        movers, dart_items, news_items, briefing_date_str
    )

    # DB 저장
    from datetime import timezone
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    row = ClosingBriefing(
        briefing_date=briefing_date_str,
        surge_stocks_json=json.dumps(movers.get("surge", []), ensure_ascii=False),
        fall_stocks_json=json.dumps(movers.get("fall", []), ensure_ascii=False),
        upper_limit_json=json.dumps(movers.get("upper_limit", []), ensure_ascii=False),
        volume_top_json=json.dumps(movers.get("volume_top", []), ensure_ascii=False),
        dart_items_json=json.dumps(dart_items, ensure_ascii=False),
        news_items_json=json.dumps(news_items[:30], ensure_ascii=False),
        watch_candidates_json=json.dumps(watch_candidates, ensure_ascii=False),
        total_candidates=len(watch_candidates),
        ai_summary=ai_summary,
        generated_at=now_utc,
        created_at=now_utc,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    logger.info(
        f"[Closing] {briefing_date_str} 생성 완료 — "
        f"급등 {len(movers.get('surge',[]))}개, 공시 {len(dart_items)}건, 후보 {len(watch_candidates)}개"
    )
    return _row_to_dict(row)


async def regenerate_closing_briefing(briefing_date_str: str, db: AsyncSession) -> Optional[dict]:
    """기존 데이터 삭제 후 재생성"""
    from ..db.models import ClosingBriefing
    existing = (await db.execute(
        select(ClosingBriefing).where(ClosingBriefing.briefing_date == briefing_date_str)
    )).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()
    return await generate_closing_briefing(briefing_date_str, db)


async def maybe_generate_today_closing(db: AsyncSession) -> None:
    """
    15:40 KST 이후이고 오늘 브리핑이 없으면 자동 생성.
    백그라운드 루프에서 호출.
    """
    from datetime import time as dtime
    now_kst = datetime.now(KST)
    if now_kst.weekday() >= 5:
        return
    if now_kst.time() < dtime(15, 40):
        return
    today_str = now_kst.strftime("%Y-%m-%d")
    await generate_closing_briefing(today_str, db)


def _row_to_dict(row) -> dict:
    def _load(field):
        try:
            return json.loads(field) if field else []
        except Exception:
            return []

    return {
        "id":                row.id,
        "briefing_date":     row.briefing_date,
        "surge_stocks":      _load(row.surge_stocks_json),
        "fall_stocks":       _load(row.fall_stocks_json),
        "upper_limit":       _load(row.upper_limit_json),
        "volume_top":        _load(row.volume_top_json),
        "dart_items":        _load(row.dart_items_json),
        "news_items":        _load(row.news_items_json),
        "watch_candidates":  _load(row.watch_candidates_json),
        "total_candidates":  row.total_candidates,
        "ai_summary":        row.ai_summary or "",
        "generated_at":      (row.generated_at.isoformat() + "Z") if row.generated_at else None,
        "created_at":        (row.created_at.isoformat() + "Z") if row.created_at else None,
    }
