# -*- coding: utf-8 -*-
"""
4/21 ~ 4/24 주간 실전 로직 점검 리포트
장마감 후 실행: python -m backend.analysis.week_report_0421_0424

분석 항목:
  1. 거래 요약 (진입/청산 수, 승률, 평균 PnL)
  2. 새 로직 기여도 (캔들 버팀 / 컵앤핸들 / 저항 거래량 익절)
  3. 청산 사유 분포
  4. 진입 스코어 vs 수익률 상관
  5. 요일별 성과
  6. 종목별 상세
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

# Windows 터미널 UTF-8 강제 설정
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# -- DB 연결 --------------------------------------------------
import psycopg2
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

load_dotenv()

WEEK_START = "2026-04-21"
WEEK_END   = "2026-04-24 23:59:59"


def get_conn():
    url = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
    u = urlparse(url)
    return psycopg2.connect(
        host=u.hostname, port=u.port or 5432,
        dbname=u.path.lstrip("/"),
        user=unquote(u.username), password=unquote(u.password),
        sslmode="require",
    )


def fetch_trades(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT
            id, code, name, entry_time, entry_price, exit_time, exit_price,
            exit_reason, profit_loss, profit_loss_pct, entry_score, status,
            is_presurge, has_cup_handle, cup_handle_status,
            has_candle_vol_signal, resistance_price, resistance_volume,
            entry_reasons_json
        FROM paper_trades
        WHERE entry_time >= %s AND entry_time <= %s
        ORDER BY entry_time
    """, (WEEK_START, WEEK_END))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def sep(char="-", n=60):
    print(char * n)


def pct_bar(pct: float, width: int = 20) -> str:
    filled = round(abs(pct) / 100 * width)
    bar = "#" * min(filled, width)
    return f"{'^' if pct >= 0 else 'v'} {bar:<{width}} {pct:+.2f}%"


def run_report():
    conn = get_conn()
    trades = fetch_trades(conn)
    conn.close()

    closed = [t for t in trades if t["status"] == "CLOSED"]
    open_  = [t for t in trades if t["status"] == "OPEN"]

    print()
    sep("=")
    print("  📊 4/21 ~ 4/24 페이퍼 트레이딩 주간 리포트")
    print(f"  생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sep("=")

    # -- 1. 거래 요약 -------------------------------------------
    print("\n[1] 거래 요약")
    sep()
    total     = len(closed)
    wins      = [t for t in closed if t["profit_loss_pct"] > 0]
    losses    = [t for t in closed if t["profit_loss_pct"] <= 0]
    win_rate  = len(wins) / total * 100 if total else 0
    avg_pnl   = sum(t["profit_loss_pct"] for t in closed) / total if total else 0
    avg_win   = sum(t["profit_loss_pct"] for t in wins)  / len(wins)  if wins   else 0
    avg_loss  = sum(t["profit_loss_pct"] for t in losses) / len(losses) if losses else 0
    rr_ratio  = abs(avg_win / avg_loss) if avg_loss else float("inf")

    print(f"  총 청산 거래  : {total}건  (수익 {len(wins)}건 / 손실 {len(losses)}건)")
    print(f"  현재 보유 중  : {len(open_)}건")
    print(f"  승률          : {win_rate:.1f}%")
    print(f"  평균 PnL      : {avg_pnl:+.2f}%")
    print(f"  평균 수익 (승): {avg_win:+.2f}%")
    print(f"  평균 손실 (패): {avg_loss:+.2f}%")
    print(f"  손익비 (R:R)  : {rr_ratio:.2f}")

    # -- 2. 새 로직 기여도 --------------------------------------
    print("\n[2] 새 로직 기여도 분석")
    sep()

    # 캔들 버팀 신호
    cv_trades = [t for t in closed if t["has_candle_vol_signal"]]
    cv_wins   = [t for t in cv_trades if t["profit_loss_pct"] > 0]
    cv_wr     = len(cv_wins) / len(cv_trades) * 100 if cv_trades else 0
    cv_avg    = sum(t["profit_loss_pct"] for t in cv_trades) / len(cv_trades) if cv_trades else 0
    print(f"  🕯️  캔들 버팀 진입   : {len(cv_trades)}건 | 승률 {cv_wr:.0f}% | 평균 {cv_avg:+.2f}%")

    # 컵앤핸들 감지 진입
    ch_trades = [t for t in closed if t["has_cup_handle"]]
    ch_wins   = [t for t in ch_trades if t["profit_loss_pct"] > 0]
    ch_wr     = len(ch_wins) / len(ch_trades) * 100 if ch_trades else 0
    ch_avg    = sum(t["profit_loss_pct"] for t in ch_trades) / len(ch_trades) if ch_trades else 0
    print(f"  ☕  컵앤핸들 진입    : {len(ch_trades)}건 | 승률 {ch_wr:.0f}% | 평균 {ch_avg:+.2f}%")

    # 컵앤핸들 상태별
    ch_statuses = defaultdict(list)
    for t in ch_trades:
        ch_statuses[t["cup_handle_status"] or "unknown"].append(t["profit_loss_pct"])
    for status, pnls in ch_statuses.items():
        avg = sum(pnls) / len(pnls)
        print(f"     +-- {status:10s}: {len(pnls)}건 | 평균 {avg:+.2f}%")

    # 급등 전 시그널 진입
    ps_trades = [t for t in closed if t["is_presurge"]]
    ps_wins   = [t for t in ps_trades if t["profit_loss_pct"] > 0]
    ps_wr     = len(ps_wins) / len(ps_trades) * 100 if ps_trades else 0
    ps_avg    = sum(t["profit_loss_pct"] for t in ps_trades) / len(ps_trades) if ps_trades else 0
    print(f"  🚀  급등 전 시그널   : {len(ps_trades)}건 | 승률 {ps_wr:.0f}% | 평균 {ps_avg:+.2f}%")

    # 저항 거래량 익절 발동
    res_exit = [t for t in closed if t["exit_reason"] == "저항거래량미달_익절"]
    print(f"\n  ⚡  저항거래량미달_익절 발동: {len(res_exit)}건")
    for t in res_exit:
        print(f"     {t['code']} {t['name']} @ {t['exit_price']} | {t['profit_loss_pct']:+.2f}%")

    # -- 3. 청산 사유 분포 --------------------------------------
    print("\n[3] 청산 사유 분포")
    sep()
    reason_stats = defaultdict(lambda: {"count": 0, "pnl_sum": 0.0, "wins": 0})
    for t in closed:
        r = t["exit_reason"] or "unknown"
        reason_stats[r]["count"] += 1
        reason_stats[r]["pnl_sum"] += t["profit_loss_pct"]
        if t["profit_loss_pct"] > 0:
            reason_stats[r]["wins"] += 1
    for reason, s in sorted(reason_stats.items(), key=lambda x: -x[1]["count"]):
        avg = s["pnl_sum"] / s["count"]
        wr  = s["wins"] / s["count"] * 100
        print(f"  {reason:<30s}: {s['count']:3d}건 | 승률 {wr:5.1f}% | 평균 {avg:+.2f}%")

    # -- 4. 진입 스코어 구간별 성과 -----------------------------
    print("\n[4] 진입 스코어 구간별 성과")
    sep()
    buckets = {
        "~50":  [t for t in closed if t["entry_score"] < 50],
        "50~60":[t for t in closed if 50 <= t["entry_score"] < 60],
        "60~70":[t for t in closed if 60 <= t["entry_score"] < 70],
        "70~80":[t for t in closed if 70 <= t["entry_score"] < 80],
        "80+":  [t for t in closed if t["entry_score"] >= 80],
    }
    for label, bucket in buckets.items():
        if not bucket:
            continue
        wr  = sum(1 for t in bucket if t["profit_loss_pct"] > 0) / len(bucket) * 100
        avg = sum(t["profit_loss_pct"] for t in bucket) / len(bucket)
        print(f"  {label:<8}: {len(bucket):3d}건 | 승률 {wr:5.1f}% | 평균 {avg:+.2f}%")

    # -- 5. 요일별 성과 -----------------------------------------
    print("\n[5] 요일별 성과 (진입 기준)")
    sep()
    DAYS = ["월", "화", "수", "목", "금", "토", "일"]
    day_stats = defaultdict(lambda: {"count": 0, "pnl_sum": 0.0, "wins": 0})
    for t in closed:
        if t["entry_time"]:
            d = t["entry_time"].weekday()
            day_stats[d]["count"] += 1
            day_stats[d]["pnl_sum"] += t["profit_loss_pct"]
            if t["profit_loss_pct"] > 0:
                day_stats[d]["wins"] += 1
    for day_idx in range(7):
        s = day_stats[day_idx]
        if s["count"] == 0:
            continue
        avg = s["pnl_sum"] / s["count"]
        wr  = s["wins"] / s["count"] * 100
        print(f"  {DAYS[day_idx]}요일: {s['count']:3d}건 | 승률 {wr:5.1f}% | 평균 {avg:+.2f}%")

    # -- 6. 종목별 상세 -----------------------------------------
    print("\n[6] 종목별 상세 (3건 이상)")
    sep()
    code_stats = defaultdict(lambda: {"name": "", "trades": []})
    for t in closed:
        code_stats[t["code"]]["name"] = t["name"]
        code_stats[t["code"]]["trades"].append(t["profit_loss_pct"])
    for code, s in sorted(code_stats.items(), key=lambda x: -len(x[1]["trades"])):
        if len(s["trades"]) < 3:
            continue
        avg = sum(s["trades"]) / len(s["trades"])
        wr  = sum(1 for p in s["trades"] if p > 0) / len(s["trades"]) * 100
        print(f"  {code} {s['name']:<12}: {len(s['trades'])}건 | {wr:.0f}% | avg {avg:+.2f}%")

    # -- 7. 종합 판단 -------------------------------------------
    print("\n[7] 종합 판단")
    sep()
    score = 0
    notes = []

    if total < 10:
        notes.append("⚠️  거래 건수 부족 (10건 미만) — 통계 신뢰도 낮음")
    if win_rate >= 55:
        score += 1
        notes.append(f"✅ 승률 {win_rate:.1f}% — 양호")
    else:
        notes.append(f"❌ 승률 {win_rate:.1f}% — 미달 (목표 55%)")
    if rr_ratio >= 1.5:
        score += 1
        notes.append(f"✅ 손익비 {rr_ratio:.2f} — 양호")
    else:
        notes.append(f"❌ 손익비 {rr_ratio:.2f} — 미달 (목표 1.5)")
    if len(res_exit) > 0:
        notes.append(f"✅ 저항 거래량 익절 {len(res_exit)}회 발동 확인 — 신규 로직 작동")
    else:
        notes.append("ℹ️  저항 거래량 익절 미발동 — 조건 미충족 또는 로직 점검 필요")
    if len(cv_trades) > 0:
        notes.append(f"✅ 캔들 버팀 신호 진입 {len(cv_trades)}건 — 신규 신호 작동")
    else:
        notes.append("ℹ️  캔들 버팀 신호 진입 없음")

    if score >= 2:
        verdict = "🟢 실전 소액 테스트 검토 가능"
    elif score == 1:
        verdict = "🟡 파라미터 조정 후 페이퍼 추가 운영 권장"
    else:
        verdict = "🔴 로직 재점검 필요"

    for note in notes:
        print(f"  {note}")
    print(f"\n  > 종합: {verdict}")
    sep("=")
    print()


if __name__ == "__main__":
    run_report()
