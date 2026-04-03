"""
Paper Trading API Router
가상 자동매매 시뮬레이션 제어 및 조회
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...core.paper_engine import paper_engine
from ...db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/paper", tags=["📄 Paper Trading"])


class StartConfig(BaseModel):
    initial_capital: float = 10_000_000.0
    market: str = "KR"
    strategy: str = "combined"
    min_score: float = 65.0
    max_positions: int = 2
    position_size_pct: float = 0.15
    pre_surge_mode: bool = False


class AddPositionRequest(BaseModel):
    code: str
    name: str = ""
    entry_price: float
    quantity: int = 0   # 0 = config 기준 자동 계산


@router.post("/start")
async def start_paper_trading(config: StartConfig, db: AsyncSession = Depends(get_db)):
    """페이퍼 트레이딩 시작"""
    if paper_engine.is_running:
        raise HTTPException(status_code=400, detail="이미 실행 중입니다")
    await paper_engine.start(config.model_dump(), db)
    return {"status": "started", **paper_engine.get_status()}


@router.post("/stop")
async def stop_paper_trading(db: AsyncSession = Depends(get_db)):
    """페이퍼 트레이딩 중지"""
    await paper_engine.stop(db)
    return {"status": "stopped", **paper_engine.get_status()}


@router.post("/reset")
async def reset_paper_trading(db: AsyncSession = Depends(get_db)):
    """전체 초기화 (포지션·거래내역·이력 삭제, 자본 리셋)"""
    await paper_engine.reset(db)
    return {"status": "reset", **paper_engine.get_status()}


@router.get("/status")
async def get_status():
    """계좌 현황 조회"""
    return paper_engine.get_status()


@router.post("/positions")
async def add_position(req: AddPositionRequest, db: AsyncSession = Depends(get_db)):
    """수동 포지션 추가 (quantity=0이면 자동 계산)"""
    try:
        result = await paper_engine.open_position_manually(
            req.code, req.name, req.entry_price, req.quantity, db
        )
        return {"status": "opened", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {type(e).__name__}: {e}")


@router.get("/positions")
async def get_positions():
    """현재 보유 포지션 조회"""
    return paper_engine.get_positions()


@router.post("/positions/close-all")
async def close_all_positions(db: AsyncSession = Depends(get_db)):
    """전체 포지션 일괄 청산"""
    results = await paper_engine.close_all_positions(db)
    return {"status": "closed_all", "closed": len(results), "positions": results}


@router.post("/positions/{code}/close")
async def close_position(code: str, db: AsyncSession = Depends(get_db)):
    """특정 포지션 수동 강제 청산"""
    result = await paper_engine.close_position_manually(code, db)
    if result is None:
        raise HTTPException(status_code=404, detail=f"포지션 없음: {code}")
    return {"status": "closed", **result}


@router.get("/trades")
async def get_trades(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """체결 거래 내역 조회 (최신 N건)"""
    return await paper_engine.get_trades(db, limit)


@router.get("/history")
async def get_history(limit: int = 200, db: AsyncSession = Depends(get_db)):
    """포트폴리오 가치 변화 이력"""
    return await paper_engine.get_history(db, limit)


@router.get("/journal/{trade_id}/analyze")
async def analyze_journal_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    """AI 기반 거래 분석 — Claude API SSE 스트리밍"""
    import os, json
    from fastapi.responses import StreamingResponse
    from ...db.models import PaperTrade

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY가 설정되지 않았습니다")

    trade = await db.get(PaperTrade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="거래 내역을 찾을 수 없습니다")

    # pykrx OHLCV (거래일 기준 ±30거래일)
    ohlcv_text = ""
    try:
        import pandas as pd
        from pykrx import stock as pykrx_stock
        entry_dt = trade.entry_time
        start = (entry_dt - pd.Timedelta(days=45)).strftime("%Y%m%d")
        end = (entry_dt + pd.Timedelta(days=5)).strftime("%Y%m%d")
        df = pykrx_stock.get_market_ohlcv(start, end, trade.code)
        if not df.empty:
            df = df.tail(25)
            rows = []
            for date, row in df.iterrows():
                rows.append(
                    f"{str(date)[:10]} | 시가:{int(row.iloc[0]):,} 고가:{int(row.iloc[1]):,}"
                    f" 저가:{int(row.iloc[2]):,} 종가:{int(row.iloc[3]):,} 거래량:{int(row.iloc[4]):,}"
                )
            ohlcv_text = "\n".join(rows)
    except Exception as e:
        ohlcv_text = f"(OHLCV 조회 실패: {e})"

    # ── Naver Finance 뉴스 크롤링 ──────────────────────────────
    async def _fetch_naver_news(code: str, target_dt) -> list[dict]:
        import httpx
        from bs4 import BeautifulSoup
        from datetime import timedelta
        news = []
        try:
            url = f"https://finance.naver.com/item/news_news.naver?code={code}&page=1"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            cutoff = (target_dt - pd.Timedelta(days=3)).strftime("%Y.%m.%d")
            target_str = target_dt.strftime("%Y.%m.%d")
            for row in soup.select("table tr"):
                a = row.select_one("td.title a")
                date_td = row.select_one("td.date")
                if not a or not date_td:
                    continue
                title = a.get_text(strip=True)
                href = a.get("href", "")
                link = ("https://finance.naver.com" + href) if href.startswith("/") else href
                date_text = date_td.get_text(strip=True)[:10]
                if cutoff <= date_text <= target_str:
                    news.append({"title": title, "link": link, "date": date_text})
                    if len(news) >= 3:
                        break
        except Exception:
            pass
        return news

    entry_price_str = f"{int(trade.entry_price):,}원"
    exit_price_str = f"{int(trade.exit_price):,}원" if trade.exit_price else "-"
    profit_str = f"{'+' if trade.profit_loss >= 0 else ''}{int(trade.profit_loss):,}원 ({'+' if trade.profit_loss_pct >= 0 else ''}{trade.profit_loss_pct:.2f}%)"
    entry_time_str = trade.entry_time.strftime("%Y-%m-%d %H:%M") if trade.entry_time else "-"
    exit_time_str = trade.exit_time.strftime("%Y-%m-%d %H:%M") if trade.exit_time else "-"

    news_items = await _fetch_naver_news(trade.code, trade.entry_time) if trade.entry_time else []
    if news_items:
        news_section_text = "아래는 실제 크롤링한 뉴스입니다. 각 뉴스를 반드시 언급하고 링크를 그대로 포함하세요:\n"
        for n in news_items:
            news_section_text += f"- [{n['date']}] {n['title']} → {n['link']}\n"
        news_section_text += "위 뉴스들을 바탕으로 종목 이슈를 간략히 정리하세요."
    else:
        news_section_text = (
            f"매수일({entry_time_str}) 전후 3일 이내 네이버 금융에서 "
            f"뉴스가 검색되지 않았습니다. 해당 종목의 일반적인 이슈를 간략히 서술하세요."
        )

    system_msg = (
        "You are a Korean stock market analyst. "
        "ABSOLUTE RULE — OUTPUT LANGUAGE: Write ONLY in Korean (한국어/Hangul). "
        "NEVER output Chinese characters (CJK: 一二三 etc.), Japanese hiragana (あいう), or Japanese katakana (アイウ). "
        "NEVER output English words — use Korean equivalents instead. "
        "Allowed characters: Korean Hangul, Arabic numerals (0-9), punctuation, and ticker/abbreviation codes only (e.g. ETF, PER, PBR). "
        "Any Chinese or Japanese character in your output is strictly forbidden and counts as a critical error. "
        "Replace every Chinese/Japanese term with its Korean Hangul pronunciation or Korean equivalent word."
    )

    prompt = f"""IMPORTANT: Respond in Korean (한국어) ONLY. Do NOT use Chinese characters or Japanese characters anywhere.

아래 모의투자 거래 데이터와 OHLCV를 분석하여 7개 섹션으로 나누어 상세 보고서를 작성하세요.
각 섹션은 반드시 "### 숫자. 제목" 형식의 헤더로 시작해야 합니다. 모든 내용은 반드시 한국어(한글)로만 작성하세요. 한자나 일본어는 절대 사용하지 마세요.

## 거래 정보
- 종목명: {trade.name} / 종목코드: {trade.code} / 시장: {trade.market}
- 매수일시: {entry_time_str} / 매수가: {entry_price_str}
- 매도일시: {exit_time_str} / 매도가: {exit_price_str}
- 보유수량: {trade.quantity}주
- 실현손익: {profit_str}
- 청산사유: {trade.exit_reason or '미입력'}

## OHLCV 데이터 (최근 25거래일, 단위: 원)
{ohlcv_text}

---

### 1. 종목 및 섹터 정보
{trade.name}({trade.code})이 속한 산업 섹터와 대표 사업 내용을 설명하세요. 해당 섹터의 국내 경쟁사, 주요 고객사, 수익 구조, 시장 내 포지션을 구체적으로 서술하세요. 섹터 전반의 최근 흐름과 해당 종목의 차별점도 포함하세요.

### 2. 종목 관련 뉴스 및 이슈
{news_section_text}

### 3. 차트 패턴 분석
제공된 OHLCV를 기반으로 캔들 패턴, 추세 방향, 거래량 변화, 지지/저항 구간을 분석하세요. 매수 시점 전후의 패턴 특징(예: 골든크로스, 돌파, 눌림목 등)과 이동평균선 관계도 서술하세요.

### 4. 당일 종가 분석
매수일 및 매도일의 종가를 중심으로 시가·고가·저가 대비 종가 위치, 당일 거래량, 가격 변동폭을 분석하세요. 장중 흐름과 종가 마감 특성(강세 마감/약세 마감/보합)을 판단하고 그 의미를 해석하세요.

### 5. 주가 종합 분석
매수가({entry_price_str})에서 매도가({exit_price_str})까지의 전체 흐름을 종합 분석하세요. 기술적 분석(추세·패턴·거래량)과 수급 관점(기관·외국인·개인 추정)을 결합하여 주가 변동의 핵심 원인과 과정을 상세히 서술하세요.

### 6. 익일 주가 흐름 예상
매도일({exit_time_str}) 이후 다음 거래일의 예상 주가 방향을 시나리오별로 제시하세요. 상승 시나리오, 하락 시나리오, 보합 시나리오로 나누어 각각의 조건과 목표가/지지가를 구체적인 수치로 제시하세요.

### 7. 거래 분석 및 교훈
이번 거래({profit_str})의 매수 타이밍과 매도 타이밍의 적절성을 평가하세요. 잘된 점과 아쉬운 점을 구분하여 서술하고, 동일 상황에서 더 나은 대응 전략이 있었다면 무엇인지, 향후 비슷한 종목을 거래할 때 적용할 수 있는 구체적인 교훈을 제시하세요."""

    import re as _re

    # 허용할 영문 대문자 약어 (금융 용어)
    _ALLOWED_EN = _re.compile(
        r"\b(OHLCV|OHLC|ETF|PER|PBR|ROE|ROA|EPS|BPS|KOSPI|KOSDAQ|EV|EBITDA|IPO|GDP|CPI|PPI|FOMC|FED|ECB|BOK|KRW|USD|EUR|YOY|QOQ|MOM|BB|RSI|MACD|MA|EMA|SMA|ATR|OBV|M&A)\b"
    )

    def _clean_foreign(text: str) -> str:
        """한문·일본어·러시아어·베트남어 등 외국어 문자 및 한국어에 섞인 영문 소문자 단어 제거"""
        # 1) CJK 한자 / 일본어
        text = _re.sub(
            r"[\u3040-\u309F\u30A0-\u30FF\uFF65-\uFF9F"
            r"\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF]+",
            "", text,
        )
        # 2) 키릴 문자 (러시아어·우크라이나어 등)
        text = _re.sub(r"[\u0400-\u04FF\u0500-\u052F]+", "", text)
        # 3) 라틴 이형 문자 (베트남어 ă/ê/ơ 등, 유럽어 악센트 등)
        text = _re.sub(r"[À-ÖØ-öø-ž\u0100-\u024F\u1E00-\u1EFF]+", "", text)
        # 3) _단어_ 형태 마크다운 이탤릭 (영문)
        text = _re.sub(r"_[A-Za-z][A-Za-z0-9_]*_", "", text)
        # 4) 허용 약어를 임시 치환 후, 소문자 영문 단어 제거, 복원
        placeholders: list[tuple[str, str]] = []
        def _protect(m: _re.Match) -> str:
            ph = f"\x00{len(placeholders)}\x00"
            placeholders.append((ph, m.group()))
            return ph
        text = _ALLOWED_EN.sub(_protect, text)
        text = _re.sub(r"\b[a-zA-Z]+\b", "", text)        # 남은 영문 단어·단일문자 제거
        for ph, orig in placeholders:
            text = text.replace(ph, orig)
        # 5) 연속 공백 정리
        text = _re.sub(r"  +", " ", text)
        return text

    async def event_stream():
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=api_key)
            stream = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4096,
                stream=True,
            )
            line_buf = ""
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if not content:
                    continue
                line_buf += content
                # 줄바꿈 단위로 완성된 라인만 필터링해서 전송
                lines = line_buf.split("\n")
                line_buf = lines.pop()          # 마지막 미완성 조각은 버퍼에 유지
                for line in lines:
                    filtered = _clean_foreign(line)
                    if filtered.strip():
                        yield f"data: {json.dumps({'text': filtered + chr(10)}, ensure_ascii=False)}\n\n"
            # 스트림 종료 후 남은 버퍼 처리
            if line_buf:
                filtered = _clean_foreign(line_buf)
                if filtered.strip():
                    yield f"data: {json.dumps({'text': filtered}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/journal")
async def get_journal(
    date_from: Optional[str] = Query(None, description="시작 날짜 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="종료 날짜 YYYY-MM-DD"),
    code: Optional[str] = Query(None, description="종목코드/종목명 검색"),
    profit_type: str = Query("all", description="all | profit | loss"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """투자일지 조회 (날짜·종목·수익여부 필터)"""
    return await paper_engine.get_journal(
        db, date_from, date_to, code, profit_type, limit, offset
    )
