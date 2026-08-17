"""Paper-trading engine: simulate the book locally against live Binance prices.

Pure simulation. No API keys, no orders, not even testnet: prices come from the
public market-data endpoint, fills are assumed at the quoted price, and state
lives in memory/paper-portfolio.json. Journals entries and exits to
memory/trade-log.md and rewrites memory/portfolio.md on every mark.

Hard rules enforced: max 3 new positions per rolling week, 5% notional cap
(default 2%), 10% cash floor, -7% hard stop from entry, 10% trailing stop from
peak, never average down (an open position is never added to). Kelly inputs are
journaled with every entry; when f* <= 0 the entry is flagged as a rehearsal
override, because honest Kelly says bet zero until a signal clears the bar.

Usage (day-trader venv):
    .venv/bin/python inputs/paper_trade.py open --from-ratings   # committee Buy/Overweight
    .venv/bin/python inputs/paper_trade.py open BTC --size-pct 2
    .venv/bin/python inputs/paper_trade.py mark [--line]
    .venv/bin/python inputs/paper_trade.py status
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / "memory" / "paper-portfolio.json"
TRADE_LOG = REPO / "memory" / "trade-log.md"
PORTFOLIO = REPO / "memory" / "portfolio.md"
DECISIONS = REPO / "memory" / "ta-decisions.md"

START_EQUITY = 10_000.0
FEE_SIDE = 0.001          # Binance spot taker fee per side; charged on entry and exit
HARD_STOP = -0.07
TRAIL = 0.10
CASH_FLOOR = 0.10
MAX_NEW_PER_WEEK = 3
PRICE_URLS = [
    "https://api.binance.com/api/v3/ticker/price",
    "https://data-api.binance.vision/api/v3/ticker/price",
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# Yahoo collision-suffixed forms (used by ta_research.py) back to real bases.
_YAHOO_BASES = {"SUI20947": "SUI", "TON11419": "TON", "PEPE24478": "PEPE"}


def pair(sym: str) -> str:
    """BTC / BTC-USD / BTCUSDT / SUI20947-USD -> Binance pair like BTCUSDT."""
    s = sym.strip().upper().replace("-USD", "").replace("USDT", "")
    return f"{_YAHOO_BASES.get(s, s)}USDT"


def live_price(binance_pair: str) -> float:
    for url in PRICE_URLS:
        try:
            r = requests.get(url, params={"symbol": binance_pair}, timeout=10)
            if r.ok:
                return float(r.json()["price"])
        except requests.RequestException:
            continue
    raise RuntimeError(f"no live price for {binance_pair}")


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"start_equity": START_EQUITY, "cash": START_EQUITY,
            "positions": [], "closed": []}


def save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2))


def journal(line: str) -> None:
    TRADE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(TRADE_LOG, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def latest_ratings() -> dict:
    """Latest committee rating per ticker from ta-decisions.md tag lines."""
    if not DECISIONS.exists():
        return {}
    tag = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) \| ([A-Z-]+) \| (\w+) \|")
    out = {}
    for line in DECISIONS.read_text().splitlines():
        m = tag.match(line.strip())
        if m:
            out[m.group(2)] = {"date": m.group(1), "rating": m.group(3)}
    return out


def new_positions_this_week(st: dict) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    n = 0
    for p in st["positions"] + st["closed"]:
        if datetime.fromisoformat(p["opened"]) >= cutoff:
            n += 1
    return n


def equity(st: dict, prices: dict) -> float:
    return st["cash"] + sum(p["qty"] * prices[p["pair"]] for p in st["positions"])


def open_position(st: dict, sym: str, size_pct: float, reason: str) -> bool:
    bp = pair(sym)
    if any(p["pair"] == bp for p in st["positions"]):
        print(f"skip {bp}: already open (never average down)")
        return False
    if new_positions_this_week(st) >= MAX_NEW_PER_WEEK:
        print(f"skip {bp}: max {MAX_NEW_PER_WEEK} new positions per week reached")
        return False
    px = live_price(bp)
    prices = {p["pair"]: live_price(p["pair"]) for p in st["positions"]}
    eq = st["cash"] + sum(p["qty"] * prices[p["pair"]] for p in st["positions"])
    notional = eq * size_pct / 100.0
    if st["cash"] - notional < eq * CASH_FLOOR:
        print(f"skip {bp}: entry would breach the 10% cash floor")
        return False
    qty = notional / px
    fee = notional * FEE_SIDE
    st["positions"].append({
        "pair": bp, "qty": qty, "entry": px, "peak": px, "entry_fee": fee,
        "opened": datetime.now(timezone.utc).isoformat(), "reason": reason,
    })
    st["cash"] -= notional + fee
    # Kelly honesty: b from the 10% trail vs 7% stop; p has no validated
    # estimate (no signal has cleared the after-fee bar), so f* <= 0 and any
    # entry is a rehearsal override, journaled as such.
    journal(f"- {now()} PAPER OPEN {bp} qty={qty:.6f} @ {px:.6g} "
            f"notional=${notional:.2f} fee=${fee:.2f} ({size_pct:.1f}% eq) stop={HARD_STOP:.0%} "
            f"trail={TRAIL:.0%} | Kelly: p=unvalidated, b={TRAIL/abs(HARD_STOP):.2f}, "
            f"f*<=0 -> rehearsal override | {reason}")
    print(f"OPEN {bp} {qty:.6f} @ {px:.6g} (${notional:.2f})")
    return True


def mark(st: dict, one_line: bool = False) -> None:
    prices = {}
    for p in list(st["positions"]):
        px = live_price(p["pair"])
        prices[p["pair"]] = px
        p["peak"] = max(p["peak"], px)
        ret = px / p["entry"] - 1
        trail_hit = px <= p["peak"] * (1 - TRAIL)
        stop_hit = ret <= HARD_STOP
        if stop_hit or trail_hit:
            why = "hard stop -7%" if stop_hit else "trailing stop 10% off peak"
            proceeds = p["qty"] * px * (1 - FEE_SIDE)
            st["cash"] += proceeds
            p["closed_at"] = datetime.now(timezone.utc).isoformat()
            p["exit"] = px
            p["pnl"] = proceeds - (p["qty"] * p["entry"] + p.get("entry_fee", 0.0))
            st["closed"].append(p)
            st["positions"].remove(p)
            journal(f"- {now()} PAPER EXIT {p['pair']} @ {px:.6g} "
                    f"pnl=${p['pnl']:+.2f} ({ret:+.2%}) | {why}")
    eq = equity(st, prices)
    realised = sum(p["pnl"] for p in st["closed"])
    unreal = eq - st["cash"] - sum(p["qty"] * p["entry"] for p in st["positions"])
    total_ret = eq / st["start_equity"] - 1

    lines = [f"# Paper portfolio", "",
             f"Marked {now()}. Start ${st['start_equity']:,.2f}.", "",
             f"- Equity: ${eq:,.2f} ({total_ret:+.2%})",
             f"- Cash: ${st['cash']:,.2f}",
             f"- Realised P&L: ${realised:+,.2f} | Unrealised: ${unreal:+,.2f}",
             f"- Open positions: {len(st['positions'])} | Closed: {len(st['closed'])}", ""]
    if st["positions"]:
        lines.append("| Pair | Qty | Entry | Last | Peak | Return | Stop dist |")
        lines.append("|---|---|---|---|---|---|---|")
        for p in st["positions"]:
            px = prices[p["pair"]]
            ret = px / p["entry"] - 1
            trail_px = p["peak"] * (1 - TRAIL)
            stop_px = p["entry"] * (1 + HARD_STOP)
            eff = max(trail_px, stop_px)
            lines.append(f"| {p['pair']} | {p['qty']:.6f} | {p['entry']:.6g} | "
                         f"{px:.6g} | {p['peak']:.6g} | {ret:+.2%} | "
                         f"{px/eff-1:+.2%} above exit |")
    PORTFOLIO.write_text("\n".join(lines) + "\n")

    if one_line:
        pos = " ".join(f"{p['pair']}:{prices[p['pair']]/p['entry']-1:+.2%}"
                       for p in st["positions"]) or "flat"
        print(f"{now()} eq=${eq:,.2f} ({total_ret:+.2%}) cash=${st['cash']:,.2f} {pos}")
    else:
        print("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open")
    o.add_argument("symbols", nargs="*", help="explicit symbols; empty with --from-ratings")
    o.add_argument("--from-ratings", action="store_true",
                   help="open committee Buy/Overweight names from ta-decisions.md")
    o.add_argument("--size-pct", type=float, default=2.0, help="notional %% of equity (cap 5)")
    m = sub.add_parser("mark")
    m.add_argument("--line", action="store_true", help="one-line output for loops")
    sub.add_parser("status")
    args = ap.parse_args()

    st = load_state()
    if args.cmd == "open":
        if args.size_pct > 5.0:
            print("ABORT: size above the 5% hard cap", file=sys.stderr)
            return 1
        targets = []
        if args.from_ratings:
            for tkr, r in latest_ratings().items():
                if r["rating"] in ("Buy", "Overweight"):
                    targets.append((tkr, f"committee {r['rating']} {r['date']}"))
        targets += [(s, "manual entry") for s in args.symbols]
        if not targets:
            print("nothing to open (no Buy/Overweight ratings, no symbols given)")
            return 0
        for sym, reason in targets:
            open_position(st, sym, args.size_pct, reason)
        save_state(st)
        mark(st, one_line=True)
    elif args.cmd == "mark":
        mark(st, one_line=args.line)
        save_state(st)
    else:
        mark(st, one_line=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
