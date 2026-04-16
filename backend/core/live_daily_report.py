"""
Live Trading Daily Report Generator
장 마감(15:30 KST) 이후 당일 거래를 분석하여 live_daily_reports 테이블에 저장.
"""
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
except ImportError:
    import pytz
    KST = pytz.timezone("Asia/Seoul")


def _to_kst_date(utc_naive: datetime) -> str:
    """UTC naive datetime → KST YYYY-MM-DD 문자열"""
    return (utc_naive + timedelta(hours=9)).strftime("%Y-%m-%d")


async def _ai_summary(trades: list[dict], report_date: str) -> str:
    """Groq LLM으로 당일 거래 요약 텍스트 생성"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not trades:
        return ""
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=api_key)

        trade_lines = []
        for t in trades:
            pnl_str = f"{'+' if t['profit_loss'] >= 0 else ''}{int(t['profit_loss']):,}원 ({'+' if t['profit_loss_pct'] >= 0 else ''}{t['profit_loss_pct']:.2f}%)"
            trade_lines.append(
                f"- {t['name']}({t['code']}) | 진입 {int(t['entry_price']):,}원 → 청산 {int(t['exit_price'] or 0):,}원 | "
                f"수량 {t['quantity']}주 | {pnl_str} | 사유: {t['exit_reason'] or '-'} | "
                f"{'⚡급등전' if t.get('is_presurge') else '일반'}"
            )

        prompt = f"""아래는 {report_date} 실전 트레이딩 결과입니다. 한국어로 간결하게 분석하세요.

## 당일 거래 내역
{chr(10).join(trade_lines)}

다음 4가지 항목을 각각 2~3문장으로 작성하세요:

### 1. 전반적 성과
당일 거래의 종합 평가 (수익/손실 규모, 승률 관점).

### 2. 잘된 점
수익이 난 거래의 패턴이나 타이밍의 적절성.

### 3. 아쉬운 점
손실 거래의 원인 분석 (진입 타이밍, 손절 수준, 고점 진입 여부 등).

### 4. 내일을 위한 교훈
오늘 거래에서 얻은 구체적인 개선 방향 1~2가지.

주의: 한글로만 작성, 한자·일본어 금지."""

        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            stream=False,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning(f"[DailyReport] AI 요약 생성 실패: {e}")
        return ""


async def generate_daily_report(report_date_str: str, db: AsyncSession) -> Optional[dict]:
    """
    특정 날짜(KST YYYY-MM-DD)의 실전 거래를 분석하여 DB에 저장.
    이미 존재하면 기존 데이터를 반환.
    """
    from ..db.models import LiveTrade, LiveDailyReport

    # 기존 리포트 확인
    existing = (await db.execute(
        select(LiveDailyReport).where(LiveDailyReport.report_date == report_date_str)
    )).scalar_one_or_none()
    if existing:
        return _row_to_dict(existing)

    # 당일 청산된 거래 조회
    all_closed = (await db.execute(
        select(LiveTrade).where(LiveTrade.status == "CLOSED", LiveTrade.exit_time.isnot(None))
    )).scalars().all()

    day_trades = [t for t in all_closed if _to_kst_date(t.exit_time) == report_date_str]

    if not day_trades:
        logger.info(f"[DailyReport] {report_date_str}: 청산 거래 없음 — 리포트 생략")
        return None

    # ── 통계 계산 ──────────────────────────────────────────────
    profit_rows = [t for t in day_trades if (t.profit_loss or 0) > 0]
    loss_rows   = [t for t in day_trades if (t.profit_loss or 0) <= 0]
    total_pnl   = sum(t.profit_loss or 0 for t in day_trades)
    win_rate    = len(profit_rows) / len(day_trades) * 100 if day_trades else 0
    avg_pnl_pct = sum(t.profit_loss_pct or 0 for t in day_trades) / len(day_trades)

    def holding_hours(t):
        if t.entry_time and t.exit_time:
            return (t.exit_time - t.entry_time).total_seconds() / 3600
        return 0

    avg_hold = sum(holding_hours(t) for t in day_trades) / len(day_trades)

    best  = max(day_trades, key=lambda t: t.profit_loss_pct or 0)
    worst = min(day_trades, key=lambda t: t.profit_loss_pct or 0)

    presurge_rows = [t for t in day_trades if t.is_presurge]
    presurge_pnl  = sum(t.profit_loss or 0 for t in presurge_rows)

    # 청산 사유 집계
    reasons: dict[str, int] = {}
    for t in day_trades:
        key = t.exit_reason or "unknown"
        # 1차/2차 익절 계열 → "익절"로 통합
        if "익절" in key or "take_profit" in key:
            key = "익절"
        elif "손절" in key or "stop" in key.lower():
            key = "손절"
        elif "trailing" in key:
            key = "trailing_stop"
        reasons[key] = reasons.get(key, 0) + 1

    trades_snapshot = [
        {
            "code":            t.code,
            "name":            t.name,
            "entry_price":     t.entry_price,
            "exit_price":      t.exit_price,
            "quantity":        t.quantity,
            "profit_loss":     t.profit_loss,
            "profit_loss_pct": t.profit_loss_pct,
            "exit_reason":     t.exit_reason,
            "is_presurge":     t.is_presurge,
            "holding_hours":   round(holding_hours(t), 2),
        }
        for t in day_trades
    ]

    # AI 요약
    ai_text = await _ai_summary(trades_snapshot, report_date_str)

    # ── DB 저장 ───────────────────────────────────────────────
    from datetime import timezone
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    row = LiveDailyReport(
        report_date         = report_date_str,
        total_trades        = len(day_trades),
        profit_count        = len(profit_rows),
        loss_count          = len(loss_rows),
        total_pnl           = round(total_pnl, 2),
        win_rate            = round(win_rate, 1),
        avg_pnl_pct         = round(avg_pnl_pct, 2),
        avg_holding_hours   = round(avg_hold, 2),
        best_trade_code     = best.code,
        best_trade_name     = best.name,
        best_trade_pnl_pct  = round(best.profit_loss_pct or 0, 2),
        worst_trade_code    = worst.code,
        worst_trade_name    = worst.name,
        worst_trade_pnl_pct = round(worst.profit_loss_pct or 0, 2),
        presurge_count      = len(presurge_rows),
        presurge_pnl        = round(presurge_pnl, 2),
        exit_reasons_json   = json.dumps(reasons, ensure_ascii=False),
        trades_json         = json.dumps(trades_snapshot, ensure_ascii=False),
        ai_summary          = ai_text,
        created_at          = now_utc,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    logger.info(f"[DailyReport] {report_date_str} 리포트 저장 완료 — {len(day_trades)}건, 총손익 {total_pnl:+,.0f}원")
    return _row_to_dict(row)


def _row_to_dict(row) -> dict:
    return {
        "id":                 row.id,
        "report_date":        row.report_date,
        "total_trades":       row.total_trades,
        "profit_count":       row.profit_count,
        "loss_count":         row.loss_count,
        "total_pnl":          row.total_pnl,
        "win_rate":           row.win_rate,
        "avg_pnl_pct":        row.avg_pnl_pct,
        "avg_holding_hours":  row.avg_holding_hours,
        "best_trade_code":    row.best_trade_code,
        "best_trade_name":    row.best_trade_name,
        "best_trade_pnl_pct": row.best_trade_pnl_pct,
        "worst_trade_code":   row.worst_trade_code,
        "worst_trade_name":   row.worst_trade_name,
        "worst_trade_pnl_pct":row.worst_trade_pnl_pct,
        "presurge_count":     row.presurge_count,
        "presurge_pnl":       row.presurge_pnl,
        "exit_reasons":       json.loads(row.exit_reasons_json) if row.exit_reasons_json else {},
        "trades":             json.loads(row.trades_json) if row.trades_json else [],
        "ai_summary":         row.ai_summary or "",
        "created_at":         (row.created_at.isoformat() + "Z") if row.created_at else None,
    }


async def maybe_generate_today_report(db: AsyncSession) -> None:
    """
    현재 시각이 15:30 KST 이후이고 오늘 리포트가 없으면 자동 생성.
    백그라운드 루프에서 호출.
    """
    now_kst = datetime.now(KST)
    from datetime import time as dtime
    if now_kst.weekday() >= 5:       # 주말 제외
        return
    if now_kst.time() < dtime(15, 30):
        return
    today_str = now_kst.strftime("%Y-%m-%d")
    await generate_daily_report(today_str, db)
