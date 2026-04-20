"""
거래 패턴 통계 학습기 (Stage 1)
DB에 저장된 청산 거래를 분석하여 패턴 인사이트 및 파라미터 제안을 생성.

의존성: pandas, numpy (이미 설치됨), Groq (선택)
최소 샘플: 분석 항목당 3건 이상
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

MIN_BUCKET_SAMPLES = 3   # 버킷 통계를 신뢰하기 위한 최소 거래 수


def _normalize_exit_reason(reason: str) -> str:
    r = (reason or "").lower()
    if "익절" in r or "take_profit" in r or "tp" in r:
        return "익절"
    if "손절" in r or "stop_loss" in r or "sl" in r:
        return "손절"
    if "trailing" in r:
        return "trailing_stop"
    if "종가" in r or "close" in r or "eod" in r:
        return "종가청산"
    return reason or "기타"


def _holding_hours(entry_time, exit_time) -> float:
    if entry_time and exit_time:
        return (exit_time - entry_time).total_seconds() / 3600
    return 0.0


def _entry_hour_kst(entry_time) -> Optional[int]:
    """UTC naive → KST 시간 (정수)"""
    if entry_time is None:
        return None
    from datetime import timedelta
    kst = entry_time + timedelta(hours=9)
    return kst.hour


def _to_df(trades: list) -> pd.DataFrame:
    """ORM 객체 리스트 → DataFrame"""
    rows = []
    for t in trades:
        rows.append({
            "id":              t.id,
            "code":            t.code,
            "name":            t.name,
            "entry_score":     float(t.entry_score or 0),
            "profit_loss":     float(t.profit_loss or 0),
            "profit_loss_pct": float(t.profit_loss_pct or 0),
            "exit_reason":     _normalize_exit_reason(t.exit_reason or ""),
            "is_presurge":     bool(getattr(t, "is_presurge", False)),
            "entry_time":      t.entry_time,
            "exit_time":       t.exit_time,
            "holding_hours":   _holding_hours(t.entry_time, t.exit_time),
            "entry_hour_kst":  _entry_hour_kst(t.entry_time),
            "win":             float(t.profit_loss_pct or 0) > 0,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ── 분석 함수들 ───────────────────────────────────────────────


def _bucket_stats(df: pd.DataFrame, col: str, bins, labels) -> list[dict]:
    """컬럼 값을 버킷으로 나눠 승률/평균수익률 계산"""
    if df.empty:
        return []
    df2 = df.copy()
    df2["_bucket"] = pd.cut(df2[col], bins=bins, labels=labels, right=False)
    result = []
    for label in labels:
        grp = df2[df2["_bucket"] == label]
        n = len(grp)
        if n == 0:
            continue
        result.append({
            "label":    str(label),
            "count":    n,
            "win_rate": round(grp["win"].mean() * 100, 1) if n > 0 else 0,
            "avg_pnl":  round(grp["profit_loss_pct"].mean(), 2),
            "total_pnl": round(grp["profit_loss"].sum(), 0),
            "reliable": n >= MIN_BUCKET_SAMPLES,
        })
    return result


def _score_analysis(df: pd.DataFrame) -> dict:
    """진입 점수 구간별 성과"""
    bins   = [0, 60, 65, 70, 75, 80, 200]
    labels = ["~60", "60-65", "65-70", "70-75", "75-80", "80+"]
    buckets = _bucket_stats(df, "entry_score", bins, labels)
    return {
        "buckets": buckets,
        "insight": _score_insight(buckets, df),
    }


def _score_insight(buckets: list[dict], df: pd.DataFrame) -> str:
    """점수 구간 분석 기반 인사이트 텍스트"""
    reliable = [b for b in buckets if b["reliable"]]
    if not reliable:
        return f"데이터 부족 ({len(df)}건) — {MIN_BUCKET_SAMPLES * 2}건 이상 쌓이면 신뢰도 높은 분석이 가능합니다."
    best = max(reliable, key=lambda b: b["avg_pnl"])
    worst = min(reliable, key=lambda b: b["avg_pnl"])
    return (
        f"최고 성과 구간: {best['label']}점 (승률 {best['win_rate']}%, 평균 {best['avg_pnl']:+.2f}%) | "
        f"최저 구간: {worst['label']}점 ({worst['avg_pnl']:+.2f}%)"
    )


def _presurge_analysis(df: pd.DataFrame) -> dict:
    """급등전 종목 vs 일반 종목 비교"""
    if df.empty:
        return {}
    presurge = df[df["is_presurge"] == True]
    normal   = df[df["is_presurge"] == False]

    def _stats(grp):
        n = len(grp)
        if n == 0:
            return {"count": 0, "win_rate": 0, "avg_pnl": 0, "total_pnl": 0}
        return {
            "count":    n,
            "win_rate": round(grp["win"].mean() * 100, 1),
            "avg_pnl":  round(grp["profit_loss_pct"].mean(), 2),
            "total_pnl": round(grp["profit_loss"].sum(), 0),
        }

    ps = _stats(presurge)
    nm = _stats(normal)
    insight = ""
    if ps["count"] >= MIN_BUCKET_SAMPLES and nm["count"] >= MIN_BUCKET_SAMPLES:
        if ps["avg_pnl"] > nm["avg_pnl"]:
            diff = ps["avg_pnl"] - nm["avg_pnl"]
            insight = f"급등전 종목이 일반 대비 평균 {diff:+.2f}%p 우수 → pre_surge_mode 활성화 권장"
        else:
            diff = nm["avg_pnl"] - ps["avg_pnl"]
            insight = f"일반 종목이 급등전 대비 평균 {diff:+.2f}%p 우수 → 현재 설정 유지 권장"
    elif ps["count"] == 0:
        insight = "급등전 거래 없음 — pre_surge_mode 효과 검증 불가"
    else:
        insight = f"데이터 부족 — 급등전 {ps['count']}건, 일반 {nm['count']}건"
    return {"presurge": ps, "normal": nm, "insight": insight}


def _exit_reason_analysis(df: pd.DataFrame) -> list[dict]:
    """청산 사유별 분포 및 평균 수익률"""
    if df.empty:
        return []
    result = []
    for reason, grp in df.groupby("exit_reason"):
        result.append({
            "reason":   reason,
            "count":    len(grp),
            "win_rate": round(grp["win"].mean() * 100, 1),
            "avg_pnl":  round(grp["profit_loss_pct"].mean(), 2),
            "total_pnl": round(grp["profit_loss"].sum(), 0),
        })
    return sorted(result, key=lambda x: -x["count"])


def _time_analysis(df: pd.DataFrame) -> list[dict]:
    """진입 시간대별(KST 시) 승률"""
    if df.empty or df["entry_hour_kst"].isna().all():
        return []
    result = []
    df2 = df.dropna(subset=["entry_hour_kst"])
    for hour in sorted(df2["entry_hour_kst"].unique()):
        grp = df2[df2["entry_hour_kst"] == hour]
        result.append({
            "hour":     int(hour),
            "label":    f"{int(hour):02d}시",
            "count":    len(grp),
            "win_rate": round(grp["win"].mean() * 100, 1),
            "avg_pnl":  round(grp["profit_loss_pct"].mean(), 2),
        })
    return result


def _holding_analysis(df: pd.DataFrame) -> list[dict]:
    """보유 시간 구간별 성과"""
    bins   = [0, 0.5, 1, 2, 4, 999]
    labels = ["30분 미만", "30분-1시간", "1-2시간", "2-4시간", "4시간+"]
    return _bucket_stats(df, "holding_hours", bins, labels)


# ── 파라미터 제안 ─────────────────────────────────────────────


def _build_recommendations(df: pd.DataFrame, score_buckets: list[dict], presurge: dict) -> list[dict]:
    """통계 결과 기반 파라미터 변경 제안"""
    recs = []

    # 1. min_score 제안 (승률 50% 이상 구간 중 가장 낮은 점수 경계)
    score_bins = {"~60": 55, "60-65": 62, "65-70": 67, "70-75": 72, "75-80": 77, "80+": 82}
    reliable = [b for b in score_buckets if b["reliable"]]
    poor_buckets = [b for b in reliable if b["win_rate"] < 45]
    good_buckets = [b for b in reliable if b["win_rate"] >= 50]

    if poor_buckets and good_buckets:
        # 가장 나쁜 버킷의 score_bins 값 이상으로 min_score 제안
        poor_max = max(score_bins.get(b["label"], 0) for b in poor_buckets)
        suggested = poor_max + 3
        recs.append({
            "param":       "min_score",
            "current":     None,
            "suggested":   float(suggested),
            "reason":      f"{poor_max:.0f}점 이하 구간 승률 {min(b['win_rate'] for b in poor_buckets):.0f}% → {suggested:.0f} 이상 진입 권장",
            "confidence":  "medium" if len(reliable) >= 3 else "low",
        })

    # 2. pre_surge_mode 제안
    ps = presurge.get("presurge", {})
    nm = presurge.get("normal", {})
    if ps.get("count", 0) >= MIN_BUCKET_SAMPLES and nm.get("count", 0) >= MIN_BUCKET_SAMPLES:
        if ps["avg_pnl"] > nm["avg_pnl"] + 0.3:
            recs.append({
                "param":     "pre_surge_mode",
                "current":   None,
                "suggested": True,
                "reason":    f"급등전 평균 {ps['avg_pnl']:+.2f}% vs 일반 {nm['avg_pnl']:+.2f}%",
                "confidence": "medium",
            })

    # 3. 데이터 부족 안내
    if len(df) < 10:
        recs.append({
            "param":     "데이터 축적 중",
            "current":   None,
            "suggested": None,
            "reason":    f"현재 {len(df)}건 → 신뢰도 높은 제안을 위해 최소 20건 이상 권장",
            "confidence": "info",
        })

    return recs


# ── AI 내러티브 ──────────────────────────────────────────────


async def _ai_narrative(summary: dict) -> str:
    """Groq으로 통계 결과 → 한국어 자연어 분석 텍스트"""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or summary.get("total_trades", 0) < 3:
        return ""
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=api_key)

        score_info = json.dumps(summary.get("score_analysis", {}).get("buckets", []),
                                ensure_ascii=False)
        exit_info  = json.dumps(summary.get("exit_analysis", [])[:5], ensure_ascii=False)
        ps_info    = json.dumps(summary.get("presurge_analysis", {}), ensure_ascii=False)

        prompt = f"""다음은 자동매매 시스템의 거래 통계 분석 결과입니다.

총 {summary['total_trades']}건 (승률 {summary['win_rate']}%, 평균 수익률 {summary['avg_pnl_pct']}%)

[진입 점수별 성과]
{score_info}

[청산 사유별 분포]
{exit_info}

[급등전 vs 일반 비교]
{ps_info}

위 데이터를 바탕으로 다음을 한국어로 분석해주세요:
1. 현재 전략의 강점과 약점 (2문장)
2. 가장 개선이 필요한 부분 (2문장)
3. 구체적인 파라미터 조정 방향 (1-2문장)

간결하고 실용적으로 작성하세요."""

        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            stream=False,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning(f"[Learner] AI 내러티브 실패: {e}")
        return ""


# ── 메인 분석 함수 ────────────────────────────────────────────


async def analyze_trades(db: AsyncSession, source: str = "all") -> dict:
    """
    DB에서 청산 거래를 읽어 통계 분석 수행.

    source: "live" | "paper" | "all"
    """
    from ..db.models import LiveTrade, PaperTrade

    trades_all = []

    if source in ("live", "all"):
        live = (await db.execute(
            select(LiveTrade).where(LiveTrade.status == "CLOSED")
        )).scalars().all()
        trades_all.extend(live)

    if source in ("paper", "all"):
        paper = (await db.execute(
            select(PaperTrade).where(PaperTrade.status == "CLOSED")
        )).scalars().all()
        # PaperTrade에는 is_presurge 없음 → False로 처리
        for t in paper:
            if not hasattr(t, "is_presurge"):
                t.is_presurge = False
        trades_all.extend(paper)

    if not trades_all:
        return {
            "total_trades": 0,
            "source": source,
            "message": "청산된 거래 없음",
        }

    df = _to_df(trades_all)
    n = len(df)

    # ── 기본 통계 ──────────────────────────────────────────────
    total_pnl    = round(df["profit_loss"].sum(), 0)
    win_rate     = round(df["win"].mean() * 100, 1)
    avg_pnl_pct  = round(df["profit_loss_pct"].mean(), 2)
    avg_hold     = round(df["holding_hours"].mean(), 2)
    best_trade   = df.loc[df["profit_loss_pct"].idxmax()].to_dict()
    worst_trade  = df.loc[df["profit_loss_pct"].idxmin()].to_dict()

    # ── 세부 분석 ──────────────────────────────────────────────
    score_analysis   = _score_analysis(df)
    exit_analysis    = _exit_reason_analysis(df)
    time_analysis    = _time_analysis(df)
    holding_analysis = _holding_analysis(df)
    presurge_analysis = _presurge_analysis(df)

    # ── 파라미터 제안 ──────────────────────────────────────────
    recommendations = _build_recommendations(
        df,
        score_analysis.get("buckets", []),
        presurge_analysis,
    )

    summary = {
        "source":          source,
        "total_trades":    n,
        "win_count":       int(df["win"].sum()),
        "loss_count":      int((~df["win"]).sum()),
        "win_rate":        win_rate,
        "total_pnl":       float(total_pnl),
        "avg_pnl_pct":     avg_pnl_pct,
        "avg_holding_hours": avg_hold,
        "best_trade": {
            "code": best_trade.get("code", ""),
            "name": best_trade.get("name", ""),
            "pnl_pct": round(float(best_trade.get("profit_loss_pct", 0)), 2),
        },
        "worst_trade": {
            "code": worst_trade.get("code", ""),
            "name": worst_trade.get("name", ""),
            "pnl_pct": round(float(worst_trade.get("profit_loss_pct", 0)), 2),
        },
        "score_analysis":    score_analysis,
        "exit_analysis":     exit_analysis,
        "time_analysis":     time_analysis,
        "holding_analysis":  holding_analysis,
        "presurge_analysis": presurge_analysis,
        "recommendations":   recommendations,
        "analyzed_at":       datetime.now(timezone.utc).isoformat(),
        "data_quality":      "sufficient" if n >= 20 else "limited" if n >= 5 else "insufficient",
    }

    # AI 내러티브 (데이터 충분할 때만)
    if n >= 5:
        summary["ai_narrative"] = await _ai_narrative(summary)
    else:
        summary["ai_narrative"] = ""

    logger.info(f"[Learner] 분석 완료: {n}건, 승률 {win_rate}%, 평균 {avg_pnl_pct:+.2f}%")
    return summary
