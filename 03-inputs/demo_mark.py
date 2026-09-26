"""Settle the friends demo's paper tickets and rebuild the index the page reads.

    python 03-inputs/demo_mark.py settle site/data     # settle every ticket now due
    python 03-inputs/demo_mark.py index site/data      # rebuild data/index.json only

Run hourly by the demo-mark GitHub Actions workflow, and after every demo run.
A ticket is settled by the rule its model was trained on, applied to the bars
that closed after its entry. For the barrier outcome that is
build_dataset_1h.compute_label_return: the stop is checked before the target on
each bar, and if neither is touched the trade closes at the horizon. For the
three-way outcome it is the close-to-close return over the horizon. Both have
the 0.20 per cent round-trip cost taken off. PASS tickets are settled the same
way, so the record also says what the coins the model declined would have made.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import demo_run as dr              # noqa: E402


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


def settle_one(t: dict) -> bool:
    """Settle one ticket if its horizon has closed. True when it changed."""
    if t.get("status") != "open" or datetime.fromisoformat(t["due"]) > datetime.now(timezone.utc):
        return False
    sym = t["symbol"].replace("/", "")
    if t.get("market") == "equity":
        # Daily stock bars from Alpaca, the sessions after the entry close.
        start = datetime.fromisoformat(t["entry_time"]).strftime("%Y-%m-%d")
        got = dr.stock_bars([sym], start, log=lambda *_: None).get(sym, [])
        bars = [r for r in dr.stock_rows(got) if r[0] > _ms(t["entry_time"])]
    else:
        bars = dr.live_bars(sym, t["frame"], _ms(t["entry_time"]))
    h = int(t["horizon_bars"])
    if len(bars) < h:
        return False                    # the archive has not caught up yet
    bars = bars[:h]
    entry = float(t["entry_price"])
    how, exit_price = "time", float(bars[-1][4])
    exit_time = datetime.fromtimestamp((int(bars[-1][6]) + 1) / 1000, timezone.utc)
    if t["outcome"] == "barrier":
        for b in bars:
            if float(b[3]) <= t["stop"]:
                how, exit_price = "stop", t["stop"]
            elif float(b[2]) >= t["target"]:
                how, exit_price = "target", t["target"]
            else:
                continue
            exit_time = datetime.fromtimestamp((int(b[6]) + 1) / 1000, timezone.utc)
            break
    ret = exit_price / entry - 1.0
    t.update(status="settled", how=how, exit_price=exit_price,
             exit_time=exit_time.isoformat(timespec="seconds"),
             ret=round(ret, 6), after_cost=round(ret - dr.cost_of(t.get("market", "crypto")), 6),
             settled=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return True


# Deploy, round two task 7 of 26 September 2026. Orders are placed through the
# relay, which keeps them against an anonymous device id; each hour they are
# copied here, filled at the open of the first candle after they were placed,
# as a market order fills, and closed at the last candle that ends by the
# signal's expiry. The same cost as a ticket comes off. Prices only are read.
RELAY = "https://swing-trader-relay.seamusrobertmurphy.workers.dev"


def pull_orders(data: Path) -> int:
    """Copy every order the relay holds that this folder does not have yet."""
    import urllib.request
    # Cloudflare refuses Python's default user agent with a 403, so it is named.
    try:
        req = urllib.request.Request(RELAY + "/orders", headers={"user-agent": "swing-trader-demo-mark"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except Exception as e:                              # noqa: BLE001
        print(f"orders: the relay did not answer, {e}")
        return 0
    folder, new = data / "orders", 0
    folder.mkdir(parents=True, exist_ok=True)
    for o in json.loads(raw).get("orders", []):
        f = folder / f"{o['id']}.json"
        if not f.exists():
            f.write_text(json.dumps(o, indent=1))
            new += 1
    print(f"orders: {new} new")
    return new


def _bars(o: dict, after_iso: str) -> list:
    sym = o["symbol"].replace("/", "")
    if o.get("market") == "equity":
        start = datetime.fromisoformat(after_iso).strftime("%Y-%m-%d")
        got = dr.stock_bars([sym], start, log=lambda *_: None).get(sym, [])
        return [r for r in dr.stock_rows(got) if r[0] >= _ms(after_iso)]
    return [r for r in dr.live_bars(sym, o["frame"], _ms(after_iso)) if r[0] >= _ms(after_iso)]


def settle_order(o: dict) -> bool:
    """Fill an accepted order, then close a filled one once its signal expires."""
    now, changed = datetime.now(timezone.utc), False
    if o.get("status") == "accepted":
        bars = _bars(o, o["submitted_at"].replace("Z", "+00:00"))
        if bars:
            price = float(bars[0][1])
            o.update(status="filled", filled_avg_price=price, qty=round(o["notional"] / price, 8),
                     filled_at=datetime.fromtimestamp(bars[0][0] / 1000, timezone.utc).isoformat(timespec="seconds"))
            changed = True
    expires = datetime.fromisoformat(o["expires"].replace("Z", "+00:00"))
    if o.get("status") == "filled" and now >= expires:
        bars = [r for r in _bars(o, o["filled_at"]) if (int(r[6]) + 1) <= int(expires.timestamp() * 1000)]
        if bars:
            exit_price = float(bars[-1][4])
            ret = exit_price / float(o["filled_avg_price"]) - 1.0
            o.update(status="settled", how="expiry", exit_price=exit_price,
                     exit_time=datetime.fromtimestamp((int(bars[-1][6]) + 1) / 1000, timezone.utc).isoformat(timespec="seconds"),
                     ret=round(ret, 6), after_cost=round(ret - dr.cost_of(o.get("market", "crypto")), 6),
                     pnl=round(o["notional"] * (ret - dr.cost_of(o.get("market", "crypto"))), 2),
                     settled=now.isoformat(timespec="seconds"))
            changed = True
    return changed


# The forward record, round two tasks 12 to 14 of 26 September 2026. Each scan's
# signals arrive as tickets in forward_new.json and are kept in data/forward/,
# one file per entry day; they settle by settle_one like a user's ticket, and
# forward_summary applies 05-research/research/confirmed-best-rule.md and builds
# the calibration record the Performance Log shows.
def merge_forward(data: Path, new: Path) -> int:
    folder, added = data / "forward", 0
    folder.mkdir(parents=True, exist_ok=True)
    by_day: dict[str, list] = {}
    for t in json.loads(new.read_text()):
        by_day.setdefault(t["entry_time"][:10], []).append(t)
    for day, ts in by_day.items():
        f = folder / f"{day}.json"
        held = json.loads(f.read_text()) if f.exists() else {}
        for t in ts:
            if t["id"] not in held:
                held[t["id"]] = t
                added += 1
        f.write_text(json.dumps(held, indent=0, default=str))
    print(f"forward: {added} new tickets")
    return added


def _t_interval(x: np.ndarray, level: float) -> tuple[float, float]:
    from scipy import stats
    m, se = float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x)))
    h = float(stats.t.ppf(1 - (1 - level) / 2, len(x) - 1)) * se
    return m - h, m + h


def forward_summary(data: Path) -> dict:
    """Per configuration: counts, independent baskets, the rule's test and calibration."""
    tix = []
    for f in sorted((data / "forward").glob("????-??-??.json")):
        tix += list(json.loads(f.read_text()).values())
    configs: dict[str, dict] = {}
    for t in tix:
        c = configs.setdefault(t["config"], dict(issued=0, settled=0, buys=[], passes=[], rows=[]))
        c["issued"] += 1
        if t.get("status") == "settled" and t.get("after_cost") is not None:
            c["settled"] += 1
            (c["buys"] if t["call"] == "BUY" else c["passes"]).append(t)
            c["rows"].append(t)
    out = {}
    for cid, c in configs.items():
        # Independent baskets: BUY tickets entered together are averaged, and a
        # basket is kept only if it starts after the last kept one closed.
        baskets = {}
        for t in c["buys"]:
            b = baskets.setdefault(t["entry_time"], dict(due=t["due"], r=[]))
            b["r"].append(t["after_cost"]); b["due"] = max(b["due"], t["due"])
        kept, last = [], ""
        for entry in sorted(baskets):
            if entry >= last:
                kept.append(float(np.mean(baskets[entry]["r"])))
                last = baskets[entry]["due"]
        cal = []
        for q in range(1, 6):
            rs = [t for t in c["rows"] if t.get("confidence") == q and t.get("expected") is not None]
            if rs:
                cal.append(dict(confidence=q, n=len(rs), predicted=float(np.mean([t["expected"] for t in rs])),
                                realised=float(np.mean([t["after_cost"] for t in rs]))))
        out[cid] = dict(issued=c["issued"], settled=c["settled"], buys=len(c["buys"]), passes=len(c["passes"]),
                        buy_mean=float(np.mean([t["after_cost"] for t in c["buys"]])) if c["buys"] else None,
                        pass_mean=float(np.mean([t["after_cost"] for t in c["passes"]])) if c["passes"] else None,
                        baskets=len(kept), basket_mean=float(np.mean(kept)) if kept else None,
                        _kept=kept, calibration=cal)
    # The rule: 30 baskets, a Bonferroni-widened t interval above zero, BUYs
    # beating passes, and the highest lower bound among those that qualify.
    eligible = [k for k, v in out.items() if v["baskets"] >= 30]
    level = 1 - 0.05 / max(1, len(eligible))
    best, best_low = None, None
    for k in eligible:
        v = out[k]
        low, high = _t_interval(np.array(v["_kept"]), level)
        v.update(ci_low=low, ci_high=high, ci_level=level)
        v["confirmed"] = bool(low > 0 and v["buy_mean"] is not None and v["pass_mean"] is not None
                              and v["buy_mean"] > v["pass_mean"])
        if v["confirmed"] and (best_low is None or low > best_low):
            best, best_low = k, low
    for v in out.values():
        v.pop("_kept", None)
        v.setdefault("confirmed", False)
    doc = dict(built=datetime.now(timezone.utc).isoformat(timespec="seconds"), rule="confirmed-best-rule.md, version 1",
               eligible=len(eligible), best=best, configs=out)
    (data / "forward-summary.json").write_text(json.dumps(doc, indent=1))
    print(f"forward summary: {len(out)} configurations, {len(eligible)} with 30 baskets, best {best}")
    return doc


def settle(data: Path) -> int:
    changed = pull_orders(data)
    for f in sorted((data / "forward").glob("????-??-??.json")) if (data / "forward").is_dir() else []:
        held = json.loads(f.read_text())
        n = sum(settle_one(t) for t in held.values())
        if n:
            f.write_text(json.dumps(held, indent=0, default=str))
            changed += n
    for f in sorted((data / "orders").glob("*.json")):
        o = json.loads(f.read_text())
        if settle_order(o):
            f.write_text(json.dumps(o, indent=1))
            changed += 1
    for f in sorted((data / "runs").glob("*.json")):
        rec = json.loads(f.read_text())
        n = sum(settle_one(t) for t in rec.get("tickets", []))
        if n:
            f.write_text(json.dumps(rec, indent=1, default=str))
            changed += n
    print(f"tickets and orders changed: {changed}")
    return changed


def index(data: Path) -> dict:
    """One file the page loads: every run in brief, every ticket, and the tallies."""
    runs, tix = [], []
    for f in sorted((data / "runs").glob("*.json"), reverse=True):
        rec = json.loads(f.read_text())
        chosen = next((m for m in rec.get("models", []) if m.get("model") == rec.get("chosen")), {})
        runs.append(dict(run_id=rec["run_id"], name=rec.get("name"), started=rec.get("started"),
                         status=rec.get("status"), error=rec.get("error"),
                         frame=rec["config"]["data"]["frame"], symbols=rec["config"]["data"]["symbols"],
                         outcome=rec["config"]["label"]["kind"], chosen=rec.get("chosen"),
                         blind_u2=chosen.get("blind_u2"), blind_auc=chosen.get("blind_auc"),
                         blind_rmse=chosen.get("blind_rmse"), blind_mae=chosen.get("blind_mae"),
                         ratio=chosen.get("ratio"), blind_top=chosen.get("blind_top"),
                         blind_all=chosen.get("blind_all"), held=rec.get("held", []),
                         tickets=len(rec.get("tickets", [])), figures=rec.get("figures", [])))
        tix += rec.get("tickets", [])
    done = [t for t in tix if t.get("status") == "settled"]

    def tally(rows):
        r = np.array([t["after_cost"] for t in rows], float)
        return dict(n=len(rows), mean=float(r.mean()) if len(r) else None,
                    positive=int((r > 0).sum()), total=float(r.sum()) if len(r) else 0.0)

    orders = [json.loads(f.read_text()) for f in sorted((data / "orders").glob("*.json"))] \
        if (data / "orders").is_dir() else []
    out = dict(built=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               runs=runs, tickets=tix, orders=orders,
               totals=dict(runs=len(runs), friends=len({r["name"] for r in runs}),
                           open=sum(t.get("status") == "open" for t in tix),
                           buy=tally([t for t in done if t["call"] == "BUY"]),
                           passed=tally([t for t in done if t["call"] == "PASS"])))
    (data / "index.json").write_text(json.dumps(out, indent=1, default=str))
    print(f"index: {len(runs)} runs, {len(tix)} tickets, {len(done)} settled")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("settle", "index", "merge"))
    ap.add_argument("data", help="the site's data folder")
    ap.add_argument("new", nargs="?", help="merge: the scan's forward_new.json")
    a = ap.parse_args()
    data = Path(a.data)
    (data / "runs").mkdir(parents=True, exist_ok=True)
    if a.cmd == "merge":
        merge_forward(data, Path(a.new))
        return 0
    if a.cmd == "settle":
        settle(data)
    index(data)
    forward_summary(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
