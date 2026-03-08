"""
전략 비교: A(구) vs B(분할TP) vs C(B+본전손절) vs D(C+분할SL)
오늘 체결된 페이퍼 트레이딩 종목을 기준으로 네 전략의 결과를 비교합니다.

Usage:
    python -m backend.compare_strategies
    python -m backend.compare_strategies --code 043200
    python -m backend.compare_strategies --code 043200 --price 1045
    python -m backend.compare_strategies --code 043200 --date 20260306
    python -m backend.compare_strategies --code 043200 --date 20260306 --price 1045
"""
import asyncio
import sys
import io
from pathlib import Path
from datetime import date

# Windows cp949 터미널 인코딩 문제 해결
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── 전략 파라미터 ─────────────────────────────────────────────

OLD_TARGETS = [
    {"ratio": 0.03, "volume_pct": 1.0, "name": "전략A +3% 전량"},
]

NEW_TARGETS = [
    {"ratio": 0.03, "volume_pct": 0.33, "name": "1차 +3%"},
    {"ratio": 0.07, "volume_pct": 0.50, "name": "2차 +7%"},
    {"ratio": 0.15, "volume_pct": 1.00, "name": "3차 +15%"},
]

SL_TARGETS = [
    {"ratio": -0.01, "volume_pct": 0.33, "name": "1차손절 -1%"},
    {"ratio": -0.02, "volume_pct": 1.00, "name": "2차손절 -2%"},
]

STOP_LOSS_RATIO = -0.02   # 고정 손절 (A/B/C 전략용)
TRAILING_RATIO  = -0.05   # 최고가 대비 -5%


# ── 시뮬레이터 ────────────────────────────────────────────────

def simulate(entry_price: float, candles: list, targets: list,
             use_breakeven: bool = False,
             use_split_sl: bool = False) -> dict:
    """
    분봉 시퀀스로 전략 시뮬레이션.

    Args:
        use_breakeven: True → 1차 TP 후 손절가를 진입가(본전)로 이동
        use_split_sl:  True → 1차 TP 전 구간에 분할 손절 적용
                              False → -2% 고정 손절 전량

    Returns: {"pct": float, "exits": list, "still_open": bool}
    """
    qty = 1000
    cash = 0.0
    remaining = qty
    highest = entry_price
    executed_tp: set = set()
    executed_sl: set = set()
    exits = []
    dynamic_stop = entry_price * (1 + STOP_LOSS_RATIO)  # 초기 손절가 (-2%)
    breakeven_active = False  # 1차 TP 실행 여부 (break-even 발동 조건)

    for c in candles:
        price = float(c["close"])
        if price <= 0:
            continue
        highest = max(highest, price)
        ratio = (price - entry_price) / entry_price

        # 1. 분할 익절
        partial_tp_fired = False
        for i, t in enumerate(targets):
            if i in executed_tp or remaining <= 0:
                continue
            if ratio >= t["ratio"]:
                close_qty = remaining if t["volume_pct"] >= 1.0 else max(1, int(remaining * t["volume_pct"]))
                close_qty = min(close_qty, remaining)
                cash += close_qty * price
                remaining -= close_qty
                executed_tp.add(i)
                exits.append({
                    "reason": t["name"], "price": price,
                    "qty": close_qty, "pct": ratio * 100,
                    "time": c.get("time", ""),
                })
                if remaining > 0:
                    partial_tp_fired = True
                if remaining <= 0:
                    break

        # 1차 TP 후 break-even 발동
        if use_breakeven and partial_tp_fired and not breakeven_active:
            dynamic_stop = max(dynamic_stop, entry_price)
            breakeven_active = True

        if remaining <= 0:
            break

        # 2. 손절 (Phase 분기)
        if breakeven_active:
            # Phase B: break-even 손절
            stop_ratio = (dynamic_stop - entry_price) / entry_price
            if ratio <= stop_ratio:
                cash += remaining * price
                exits.append({
                    "reason": "손절(본전)", "price": price,
                    "qty": remaining, "pct": ratio * 100,
                    "time": c.get("time", ""),
                })
                remaining = 0
                break
        elif use_split_sl:
            # Phase A: 분할 손절
            for i, sl in enumerate(SL_TARGETS):
                if i in executed_sl or remaining <= 0:
                    continue
                if ratio <= sl["ratio"]:
                    close_qty = remaining if sl["volume_pct"] >= 1.0 else max(1, int(remaining * sl["volume_pct"]))
                    close_qty = min(close_qty, remaining)
                    cash += close_qty * price
                    remaining -= close_qty
                    executed_sl.add(i)
                    exits.append({
                        "reason": sl["name"], "price": price,
                        "qty": close_qty, "pct": ratio * 100,
                        "time": c.get("time", ""),
                    })
            if remaining <= 0:
                break
        else:
            # 고정 손절 전량
            stop_ratio = (dynamic_stop - entry_price) / entry_price
            if ratio <= stop_ratio:
                cash += remaining * price
                exits.append({
                    "reason": f"손절 {STOP_LOSS_RATIO*100:.0f}%", "price": price,
                    "qty": remaining, "pct": ratio * 100,
                    "time": c.get("time", ""),
                })
                remaining = 0
                break

        # 3. 트레일링 스톱 (최고가 > 진입가인 경우에만)
        if highest > entry_price:
            trail_threshold = highest * (1 + TRAILING_RATIO)
            if price <= trail_threshold:
                cash += remaining * price
                exits.append({
                    "reason": f"트레일링({highest:,.0f}->{price:,.0f})", "price": price,
                    "qty": remaining, "pct": ratio * 100,
                    "time": c.get("time", ""),
                })
                remaining = 0
                break

    # 미청산 처리
    still_open = remaining > 0
    if still_open and candles:
        last_price = float(candles[-1]["close"])
        last_ratio = (last_price - entry_price) / entry_price
        cash += remaining * last_price
        exits.append({
            "reason": "미청산(종가)", "price": last_price,
            "qty": remaining, "pct": last_ratio * 100,
            "time": candles[-1].get("time", ""),
        })

    total_cost = qty * entry_price
    total_pct = (cash - total_cost) / total_cost * 100
    return {"pct": round(total_pct, 2), "exits": exits, "still_open": still_open}


# ── 출력 헬퍼 ────────────────────────────────────────────────

def _fmt_exits(exits: list) -> str:
    return "  ".join(
        f"{e['reason']}@{e['price']:,}({e['pct']:+.1f}%) {e['time'][11:16]}"
        for e in exits
    )

def _winner(results: list[tuple]) -> str:
    best_pct = max(r[1]["pct"] for r in results)
    for label, r in results:
        if r["pct"] == best_pct:
            return f"{label} ({best_pct:+.2f}%)"
    return "-"


# ── 분봉 캐시 (로컬 JSON 저장/로드) ─────────────────────────

CANDLE_DIR = Path(__file__).parent.parent / "data" / "candles"


def _candle_path(code: str, date_str: str) -> Path:
    return CANDLE_DIR / f"{code}_{date_str}.json"


def save_candles(code: str, candles: list[dict], date_str: str | None = None) -> Path:
    """분봉 데이터를 JSON 파일로 저장.

    Args:
        code: 종목 코드
        candles: 분봉 리스트
        date_str: 날짜 YYYYMMDD (None이면 오늘)

    Returns:
        저장된 파일 경로
    """
    import json
    if date_str is None:
        date_str = date.today().strftime("%Y%m%d")
    CANDLE_DIR.mkdir(parents=True, exist_ok=True)
    path = _candle_path(code, date_str)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(candles, f, ensure_ascii=False)
    return path


def load_candles(code: str, date_str: str) -> list[dict]:
    """저장된 분봉 JSON 로드. 파일 없으면 빈 리스트."""
    import json
    path = _candle_path(code, date_str)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── 단일 종목 직접 테스트 ─────────────────────────────────────

async def test_code(code: str, entry_price: float | None = None,
                    date_str: str | None = None, save: bool = False):
    today_str = date.today().strftime("%Y%m%d")
    target_date = date_str or today_str
    use_cache = date_str and date_str != today_str

    print(f"\n{'='*80}")
    src = f"캐시 {target_date}" if use_cache else "KIS 오늘"
    print(f"  직접 테스트: {code}  [{src}]")
    print(f"{'='*80}")

    if use_cache:
        candles = load_candles(code, target_date)
        if not candles:
            print(f"  캐시 없음: {_candle_path(code, target_date)}")
            print(f"  장중에 다음 명령으로 저장하세요:")
            print(f"    python -m backend.compare_strategies --code {code} --save")
            return
    else:
        from backend.kis.rest_client import get_kis_client
        candles = await get_kis_client().get_full_day_minute_chart(code, since_hour="090000")
        if save and candles:
            path = save_candles(code, candles, today_str)
            print(f"  분봉 저장: {path}")

    if not candles:
        print("  분봉 데이터 없음")
        return

    print(f"  분봉: {len(candles)}개 ({candles[0]['time'][11:16]} ~ {candles[-1]['time'][11:16]})")
    if entry_price is None:
        entry_price = float(candles[0]["close"])
    print(f"  진입가: {entry_price:,}원")

    a = simulate(entry_price, candles, OLD_TARGETS)
    b = simulate(entry_price, candles, NEW_TARGETS)
    c = simulate(entry_price, candles, NEW_TARGETS, use_breakeven=True)
    d = simulate(entry_price, candles, NEW_TARGETS, use_breakeven=True, use_split_sl=True)

    results = [("A", a), ("B", b), ("C", c), ("D", d)]
    labels  = ["A(구 +3%전량)", "B(분할TP)", "C(B+본전손절)", "D(C+분할SL)"]

    print()
    for (_, r), label in zip(results, labels):
        print(f"  {label:14s}: {r['pct']:+6.2f}%  {_fmt_exits(r['exits'])}")

    print(f"\n  => 승자: {_winner(results)}")
    print(f"{'─'*80}\n")


# ── 메인 (DB 페이퍼 거래 기반) ────────────────────────────────

async def main():
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import PaperTrade
    from backend.kis.rest_client import get_kis_client
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PaperTrade)
            .where(PaperTrade.status == "CLOSED")
            .order_by(PaperTrade.exit_time.desc())
        )
        trades = result.scalars().all()

    if not trades:
        print("페이퍼 거래 내역이 없습니다.")
        return

    today_str = date.today().isoformat()
    today_trades = [t for t in trades if t.exit_time and t.exit_time.date().isoformat() == today_str]
    if not today_trades:
        print(f"오늘({today_str}) 체결 거래 없음. 최근 3건으로 대신 비교합니다.")
        today_trades = trades[:3]

    print(f"\n{'='*80}")
    print(f"  전략 비교 A/B/C/D  |  대상: {len(today_trades)}건  |  기준일: {today_str}")
    print(f"  A=구(+3% 전량)  B=분할TP  C=B+본전손절  D=C+분할SL(-1%/1/3, -2%/전량)")
    print(f"{'='*80}\n")

    sa, sb, sc, sd = [], [], [], []

    for trade in today_trades:
        code = trade.code
        name = trade.name or code
        entry_price = trade.entry_price

        print(f"[{code}] {name}  진입: {entry_price:,}원")

        since = "090000"
        if trade.entry_time:
            h = trade.entry_time.hour
            m = max(0, trade.entry_time.minute - 5)
            since = f"{h:02d}{m:02d}00"

        try:
            candles = await get_kis_client().get_full_day_minute_chart(code, since_hour=since)
            print(f"   분봉: {len(candles)}개 ({since[:2]}:{since[2:4]} 이후)")
        except Exception as e:
            print(f"   분봉 조회 실패: {e} → 스킵")
            candles = []

        if not candles:
            actual_pct = trade.profit_loss_pct or 0
            print(f"   실제결과: {actual_pct:+.2f}%  ({trade.exit_reason})\n")
            continue

        if trade.entry_time:
            entry_iso = trade.entry_time.strftime("%Y-%m-%dT%H:%M")
            candles_after = [c for c in candles if c.get("time", "") >= entry_iso] or candles
        else:
            candles_after = candles

        a = simulate(entry_price, candles_after, OLD_TARGETS)
        b = simulate(entry_price, candles_after, NEW_TARGETS)
        c = simulate(entry_price, candles_after, NEW_TARGETS, use_breakeven=True)
        d = simulate(entry_price, candles_after, NEW_TARGETS, use_breakeven=True, use_split_sl=True)
        actual_pct = trade.profit_loss_pct or 0

        sa.append(a["pct"]); sb.append(b["pct"]); sc.append(c["pct"]); sd.append(d["pct"])

        results = [("A", a), ("B", b), ("C", c), ("D", d)]
        labels  = ["A(구 +3%전량)", "B(분할TP)", "C(B+본전손절)", "D(C+분할SL)"]
        for (_, r), label in zip(results, labels):
            print(f"   {label:14s}: {r['pct']:+6.2f}%  {_fmt_exits(r['exits'])}")
        print(f"   {'실제결과':14s}: {actual_pct:+6.2f}%  ({trade.exit_reason or '-'})")
        print(f"   => 승자: {_winner(results)}\n")

    if sa:
        avg = lambda lst: sum(lst) / len(lst)
        aa, ab, ac, ad = avg(sa), avg(sb), avg(sc), avg(sd)
        print(f"{'─'*80}")
        print(f"  평균 수익률")
        print(f"    A(구)         : {aa:+.2f}%")
        print(f"    B(분할TP)     : {ab:+.2f}%   (vs A: {ab-aa:+.2f}%p)")
        print(f"    C(B+본전손절) : {ac:+.2f}%   (vs A: {ac-aa:+.2f}%p)")
        print(f"    D(C+분할SL)   : {ad:+.2f}%   (vs A: {ad-aa:+.2f}%p, vs C: {ad-ac:+.2f}%p)")
        print(f"{'─'*80}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="전략 비교 시뮬레이터 (A/B/C/D)")
    parser.add_argument("--code",  "-c", help="직접 테스트할 종목 코드")
    parser.add_argument("--price", "-p", type=float, help="진입가 직접 지정")
    parser.add_argument("--date",  "-d", help="과거 날짜 YYYYMMDD (저장된 캐시 사용)")
    parser.add_argument("--save",  "-s", action="store_true",
                        help="오늘 분봉을 data/candles/ 에 저장 (장중 실행 시)")
    args = parser.parse_args()

    if args.code:
        asyncio.run(test_code(args.code, args.price, args.date, args.save))
    else:
        asyncio.run(main())
