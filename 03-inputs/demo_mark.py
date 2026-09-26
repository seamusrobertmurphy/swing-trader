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


def settle(data: Path) -> int:
    changed = 0
    for f in sorted((data / "runs").glob("*.json")):
        rec = json.loads(f.read_text())
        n = sum(settle_one(t) for t in rec.get("tickets", []))
        if n:
            f.write_text(json.dumps(rec, indent=1, default=str))
            changed += n
    print(f"settled {changed} tickets")
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
                         tickets=len(rec.get("tickets", []))))
        tix += rec.get("tickets", [])
    done = [t for t in tix if t.get("status") == "settled"]

    def tally(rows):
        r = np.array([t["after_cost"] for t in rows], float)
        return dict(n=len(rows), mean=float(r.mean()) if len(r) else None,
                    positive=int((r > 0).sum()), total=float(r.sum()) if len(r) else 0.0)

    out = dict(built=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               runs=runs, tickets=tix,
               totals=dict(runs=len(runs), friends=len({r["name"] for r in runs}),
                           open=sum(t.get("status") == "open" for t in tix),
                           buy=tally([t for t in done if t["call"] == "BUY"]),
                           passed=tally([t for t in done if t["call"] == "PASS"])))
    (data / "index.json").write_text(json.dumps(out, indent=1, default=str))
    print(f"index: {len(runs)} runs, {len(tix)} tickets, {len(done)} settled")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("settle", "index"))
    ap.add_argument("data", help="the site's data folder")
    a = ap.parse_args()
    data = Path(a.data)
    (data / "runs").mkdir(parents=True, exist_ok=True)
    if a.cmd == "settle":
        settle(data)
    index(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
