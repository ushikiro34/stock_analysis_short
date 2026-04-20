"""
장전 브리핑 생성기
매일 08:20~09:00 KST 사이에 자동 실행.

3개 레이어:
  1. DART 공시   → 주요 공시 종목 추출
  2. 뉴스 + LLM  → 급등 가능 종목 AI 추출
  3. 테마 매핑   → 글로벌 이슈 → 관련 테마 종목
"""
import json
import logging
import os
from datetime import datetime
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


async def _llm_extract_candidates(news_items: list[dict], dart_items: list[dict], report_date: str) -> tuple[list[dict], str]:
    """
    Groq LLM으로 뉴스+공시에서 급등 가능 종목 추출 및 요약 텍스트 생성.
    Returns: (candidates_list, summary_text)
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return [], ""

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=api_key)

        headlines = [f"[{it['source']}] {it['title']}" for it in news_items[:50]]
        dart_lines = [f"- {it['corp_name']}({it['stock_code']}): {it['report_nm']} [{it['dart_type']}]"
                      for it in dart_items]

        prompt = f"""오늘({report_date}) 장전 국내 주요 뉴스와 공시입니다.

## 주요 공시
{chr(10).join(dart_lines) if dart_lines else "없음"}

## 뉴스 헤드라인
{chr(10).join(headlines)}

다음 두 가지를 수행하세요:

### 1. 급등 후보 종목 추출
아래 JSON 형식으로 오늘 한국 주식시장에서 급등 가능성이 높은 종목을 추출하세요.
주로 뉴스 테마와 연관된 종목, 공시 발생 종목을 중심으로 최대 10개.

```json
{{"candidates": [{{"code": "6자리코드또는null", "name": "종목명", "reason": "급등 이유 1문장"}}]}}
```

### 2. 장전 브리핑 요약
오늘 주목해야 할 핵심 이슈와 시장 방향성을 3~4문장으로 요약하세요.

주의: 한국어만 사용, 종목코드 불확실하면 null."""

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
            json_match = re.search(r'\{["\s]*candidates["\s]*:.*?\}(?=\s*```|\s*###|\s*$)', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                raw_list = parsed.get("candidates", [])
                for item in raw_list:
                    code = (item.get("code") or "").strip()
                    name = (item.get("name") or "").strip()
                    reason = (item.get("reason") or "").strip()
                    if name:
                        candidates.append({
                            "code": code if (code and code.isdigit() and len(code) == 6) else "",
                            "name": name,
                            "source": "news_llm",
                            "reason": reason,
                        })
        except Exception as e:
            logger.warning(f"[Briefing] LLM JSON 파싱 실패: {e}")

        # 요약 텍스트 (JSON 블록 이후 텍스트)
        summary = ""
        try:
            after_json = content.split("###")
            if len(after_json) >= 2:
                summary = after_json[-1].strip()
                summary = summary.replace("2. 장전 브리핑 요약", "").strip()
            else:
                # ```json 블록 이후 텍스트
                parts = content.split("```")
                if len(parts) >= 3:
                    summary = parts[-1].strip()
        except Exception:
            pass

        return candidates, summary

    except Exception as e:
        logger.warning(f"[Briefing] LLM 호출 실패: {e}")
        return [], ""


async def generate_morning_briefing(briefing_date_str: str, db: AsyncSession) -> Optional[dict]:
    """
    3개 레이어를 조합해 장전 브리핑 생성.
    이미 존재하면 기존 데이터 반환.
    """
    from ..db.models import MorningBriefing
    from ..collector.dart_client import fetch_today_disclosures
    from ..core.news_crawler import fetch_all_news
    from ..core.theme_map import match_themes, get_theme_stocks

    # 기존 브리핑 확인
    existing = (await db.execute(
        select(MorningBriefing).where(MorningBriefing.briefing_date == briefing_date_str)
    )).scalar_one_or_none()
    if existing:
        return _row_to_dict(existing)

    logger.info(f"[Briefing] {briefing_date_str} 생성 시작")

    date_str_nodash = briefing_date_str.replace("-", "")

    # ── Layer 1 + 2 병렬 조회 ─────────────────────────────────
    dart_items, news_items = await __import__("asyncio").gather(
        fetch_today_disclosures(date_str_nodash),
        fetch_all_news(),
    )

    # ── Layer 1: DART 공시 → 후보 ─────────────────────────────
    dart_candidates = []
    for item in dart_items:
        dart_candidates.append({
            "code":      item["stock_code"],
            "name":      item["corp_name"],
            "source":    "dart",
            "reason":    item["report_nm"],
            "dart_type": item["dart_type"],
            "dart_url":  item["dart_url"],
        })

    # ── Layer 2: LLM 뉴스 분석 ────────────────────────────────
    llm_candidates, ai_summary = await _llm_extract_candidates(
        news_items, dart_items, briefing_date_str
    )

    # ── Layer 3: 테마 매핑 ────────────────────────────────────
    all_texts = " ".join(it["title"] for it in news_items)
    all_texts += " " + " ".join(it["report_nm"] for it in dart_items)
    detected_theme_names = match_themes(all_texts)

    # 테마별 종목 목록
    themes_detected: dict[str, list[str]] = {}
    for theme in detected_theme_names:
        themes_detected[theme] = []
    theme_stocks_raw = get_theme_stocks(detected_theme_names)
    for s in theme_stocks_raw:
        t = s.get("theme_name", "")
        if t in themes_detected:
            themes_detected[t].append(s["code"])

    theme_candidates = [
        {
            "code":       s["code"],
            "name":       s["name"],
            "source":     "theme",
            "reason":     f"{s.get('theme_name', '')} 테마 관련주",
            "theme_name": s.get("theme_name", ""),
        }
        for s in theme_stocks_raw
    ]

    # ── 머지 & 중복 제거 (우선순위: dart > theme > news_llm) ──
    merged: dict[str, dict] = {}
    priority = {"dart": 0, "theme": 1, "news_llm": 2}
    for c in dart_candidates + theme_candidates + llm_candidates:
        code = (c.get("code") or "").strip()
        key = code if code else c.get("name", "")
        if not key:
            continue
        existing_c = merged.get(key)
        if existing_c is None or priority[c["source"]] < priority[existing_c["source"]]:
            merged[key] = c
    all_candidates = list(merged.values())

    # ── DB 저장 ──────────────────────────────────────────────
    from datetime import timezone
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    row = MorningBriefing(
        briefing_date        = briefing_date_str,
        dart_items_json      = json.dumps(dart_items, ensure_ascii=False),
        dart_count           = len(dart_items),
        news_items_json      = json.dumps(
            [{"title": n["title"], "link": n["link"], "source": n["source"]} for n in news_items],
            ensure_ascii=False
        ),
        llm_candidates_json  = json.dumps(llm_candidates, ensure_ascii=False),
        themes_detected_json = json.dumps(themes_detected, ensure_ascii=False),
        theme_stocks_json    = json.dumps(theme_candidates, ensure_ascii=False),
        all_candidates_json  = json.dumps(all_candidates, ensure_ascii=False),
        total_candidates     = len(all_candidates),
        ai_summary           = ai_summary,
        generated_at         = now_utc,
        created_at           = now_utc,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    logger.info(
        f"[Briefing] {briefing_date_str} 저장 완료 — "
        f"DART {len(dart_items)}건, LLM {len(llm_candidates)}개, "
        f"테마 {len(detected_theme_names)}개, 총 후보 {len(all_candidates)}개"
    )
    return _row_to_dict(row)


def _row_to_dict(row) -> dict:
    def _j(v):
        return json.loads(v) if v else []

    def _jd(v):
        return json.loads(v) if v else {}

    return {
        "id":               row.id,
        "briefing_date":    row.briefing_date,
        "dart_items":       _j(row.dart_items_json),
        "dart_count":       row.dart_count,
        "news_items":       _j(row.news_items_json),
        "llm_candidates":   _j(row.llm_candidates_json),
        "themes_detected":  _jd(row.themes_detected_json),
        "theme_stocks":     _j(row.theme_stocks_json),
        "all_candidates":   _j(row.all_candidates_json),
        "total_candidates": row.total_candidates,
        "ai_summary":       row.ai_summary or "",
        "generated_at":     (row.generated_at.isoformat() + "Z") if row.generated_at else None,
        "created_at":       (row.created_at.isoformat() + "Z") if row.created_at else None,
    }


async def maybe_generate_today_briefing(db: AsyncSession) -> None:
    """
    08:20~09:00 KST 사이에 오늘 브리핑이 없으면 자동 생성.
    백그라운드 루프에서 5분마다 호출.
    """
    from datetime import time as dtime
    now_kst = datetime.now(KST)
    if now_kst.weekday() >= 5:       # 주말 제외
        return
    if not (dtime(8, 20) <= now_kst.time() <= dtime(9, 0)):
        return
    today_str = now_kst.strftime("%Y-%m-%d")
    await generate_morning_briefing(today_str, db)


async def regenerate_morning_briefing(briefing_date_str: str, db: AsyncSession) -> Optional[dict]:
    """수동 재생성 (기존 레코드 삭제 후 재생성)"""
    from ..db.models import MorningBriefing
    existing = (await db.execute(
        select(MorningBriefing).where(MorningBriefing.briefing_date == briefing_date_str)
    )).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()
    return await generate_morning_briefing(briefing_date_str, db)
