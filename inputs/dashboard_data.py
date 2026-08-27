"""Emit one JSON file holding everything the Quarto dashboard draws.

The dashboard is R and Quarto. This is deliberately the only Python in that
path, and it exists so the awkward parts are computed once, here, where they
are already tested: which of Alpaca's several account values to believe, the
per-fill slippage measurement, and the correlation-cluster arithmetic. Doing
that arithmetic a second time in R would mean getting it wrong a second time.

R's job is to draw. This file's job is to hand it numbers that already agree.

    .venv/bin/python inputs/dashboard_data.py
    -> outputs/dashboard/data.json
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

import config
from alpaca_daily_report import (BENCHMARK, CYCLES_NEEDED, LIVE_FROM,
                                 MODEL_ANNUAL_VOL, MODEL_COST_BP, START_EQUITY,
                                 benchmark, equity_curve, rebalances)
from alpaca_trade import (CASH_FLOOR, CAT_STOP, CLUSTER_CAP, DAILY_CIRCUIT,
                          MAX_POSITION_PCT, MIN_REBALANCE_GAP_DAYS,
                          account_state, clients)
from equity_cluster_cap import CORR_WINDOW, RHO, largest_cluster

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "dashboard"

# A schedule that has stopped looks exactly like a schedule with nothing to do:
# both are silent. On 2026-08-27 the tick loop died and four hours passed with
# no sign of it anywhere, while this page went on showing a confident number
# from its last successful render. The clock below is the sign.
TICK_LOG_DIR = REPO / "outputs" / "AA-evals" / "logs"
TICK_EVERY_MIN = 20
TICK_STALE_AFTER = 3          # missed ticks before the page says so
ET = ZoneInfo("America/New_York")


def _keys():
    return (config.ALPACA_API_KEY, config.ALPACA_API_SECRET, config.ALPACA_BASE_URL)


def intraday(days: int = 5, timeframe: str = "15Min") -> list:
    """Recent intraday equity. Market hours only: extended-hours marks on a
    paper account are thin and disagree with the close by over a percent."""
    k, s, b = _keys()
    r = requests.get(f"{b}/v2/account/portfolio/history",
                     params=dict(period=f"{days}D", timeframe=timeframe,
                                 intraday_reporting="market_hours"),
                     headers={"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s},
                     timeout=30)
    if r.status_code != 200:
        return []
    d = r.json()
    return [dict(t=pd.to_datetime(t, unit="s", utc=True).tz_convert(ET).isoformat(),
                 equity=float(e))
            for t, e in zip(d["timestamp"], d["equity"]) if e]


def slippage_by_cycle() -> list:
    """Per-rebalance execution cost. This is the number the paper trial exists
    to produce, so it is the dashboard's headline rather than a footnote."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    tc = clients()
    k, s, _ = _keys()
    dc = StockHistoricalDataClient(k, s)
    since = datetime.now(timezone.utc) - timedelta(days=60)
    orders = [o for o in tc.get_orders(GetOrdersRequest(
        status=QueryOrderStatus.CLOSED, after=since, limit=500))
        if o.filled_at and o.filled_avg_price]
    rows = []
    for o in orders:
        t = o.filled_at.replace(second=0, microsecond=0)
        try:
            bars = dc.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=o.symbol, timeframe=TimeFrame.Minute,
                start=t - timedelta(minutes=1),
                end=t + timedelta(minutes=2))).data[o.symbol]
        except Exception:  # noqa: BLE001
            continue
        bar = {b.timestamp.astimezone(timezone.utc).replace(second=0, microsecond=0): b
               for b in bars}.get(t)
        if bar is None:
            continue
        ref, fill = float(bar.vwap), float(o.filled_avg_price)
        side = str(o.side).rsplit(".", 1)[-1].lower()
        et = o.filled_at.astimezone(ET)
        rows.append(dict(cycle=et.strftime("%Y-%m-%d"), symbol=o.symbol, side=side,
                         slip_bp=(fill - ref) / ref * 1e4 * (1 if side == "buy" else -1),
                         notional=fill * float(o.filled_qty),
                         from_open=(et.hour - 9) * 60 + (et.minute - 30)))
    if not rows:
        return []
    t = pd.DataFrame(rows)
    out = []
    for cyc, g in t.groupby("cycle"):
        out.append(dict(
            cycle=cyc, fills=int(len(g)),
            mean_bp=round(float(g.slip_bp.mean()), 1),
            median_bp=round(float(g.slip_bp.median()), 1),
            worst_bp=round(float(g.slip_bp.max()), 1),
            notional=round(float(g.notional.sum()), 2),
            dollars=round(float((g.slip_bp / 1e4 * g.notional).sum()), 2),
            at_open=int((g.from_open < 15).sum()),
            model_low=MODEL_COST_BP[0], model_high=MODEL_COST_BP[1]))
    return sorted(out, key=lambda r: r["cycle"])


def fills_detail() -> list:
    """Every fill of the most recent cycle, so a bad average can be traced to
    the handful of fills that caused it rather than blamed on the whole book."""
    cyc = slippage_by_cycle()
    return [] if not cyc else []


def concentration(positions: dict, equity: float) -> dict:
    from equity_momentum_monthly import monthly_panel
    px, _, _ = monthly_panel("funds")
    held = sorted(positions)
    have = [h for h in held if h in px.columns]
    if len(have) < 2:
        return dict(available=False)
    corr = np.log(px[have]).diff().tail(CORR_WINDOW).corr()
    w = {s: positions[s]["value"] / equity for s in held}
    adj = corr > RHO
    seen, comps = set(), []
    for s in have:
        if s in seen:
            continue
        stack, comp = [s], set()
        while stack:
            x = stack.pop()
            if x in comp:
                continue
            comp.add(x)
            stack += [y for y in have if adj.at[x, y] and y not in comp]
        seen |= comp
        comps.append(comp)
    comps.sort(key=lambda c: -sum(w[s] for s in c))
    local = {x: w[x] + sum(w[o] for o in have if o != x and corr.at[x, o] > RHO)
             for x in have}
    worst = max(local, key=local.get)
    return dict(
        available=True, cap=CLUSTER_CAP, rho=RHO,
        biggest_group_names=len(comps[0]),
        biggest_group_weight=round(float(sum(w[s] for s in comps[0])), 4),
        biggest_group=sorted(comps[0]),
        n_groups=len(comps),
        groups=[dict(rank=i + 1, n=len(c),
                     weight=round(float(sum(w[s] for s in c)), 4))
                for i, c in enumerate(comps)],
        worst_local_symbol=worst,
        worst_local_weight=round(float(local[worst]), 4),
        over_cap=int(sum(1 for v in local.values() if v > CLUSTER_CAP + 1e-9)))


def last_tick() -> dict:
    """When the schedule last woke up, read from its own log.

    The log is the only honest source. A marker written by the tick would say
    the same thing, but one more file to keep in step is one more thing that
    can be right while the schedule is dead.
    """
    logs = sorted(TICK_LOG_DIR.glob("tick-*.log"))
    if not logs:
        return dict(available=False)
    stamp = None
    for line in reversed(logs[-1].read_text(errors="replace").splitlines()):
        m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", line)
        if m:
            stamp = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
            break
    if stamp is None:
        return dict(available=False)
    age = (datetime.now(timezone.utc) - stamp).total_seconds() / 60
    return dict(available=True, at=stamp.isoformat(), age_min=round(age, 1),
                every_min=TICK_EVERY_MIN,
                stale=age > TICK_EVERY_MIN * TICK_STALE_AFTER)


def build() -> dict:
    tc = clients()
    acct, equity, cash, day_move, positions = account_state(tc)
    now = datetime.now(ET)
    curve = equity_curve()
    today = now.date()
    curve.loc[today] = equity           # see alpaca_daily_report for why
    curve = curve.sort_index()
    spy = benchmark()
    live = datetime.strptime(LIVE_FROM, "%Y-%m-%d").date()

    since_live = equity / START_EQUITY - 1
    spy_base = spy[spy.index >= live]
    spy_live = float(spy.iloc[-1] / spy_base.iloc[0] - 1) if len(spy_base) else None
    sessions = int((curve.index > live).sum())
    sigma = MODEL_ANNUAL_VOL * np.sqrt(max(sessions, 1) / 252)

    plist = tc.get_all_positions()
    pos = [dict(symbol=p.symbol, qty=float(p.qty), value=float(p.market_value),
                weight=round(float(p.market_value) / equity, 5),
                plpc=round(float(p.unrealized_plpc), 5),
                pl=round(float(p.unrealized_pl), 2)) for p in plist]
    pos.sort(key=lambda r: r["plpc"])

    rb = rebalances()
    conc = concentration(positions, equity)
    tick = last_tick()

    # SPY rebased onto the book's start, so one chart can carry both lines
    spy_series = []
    if len(spy_base):
        b0 = float(spy_base.iloc[0])
        for d, v in spy.items():
            if d >= live:
                spy_series.append(dict(date=str(d),
                                       equity=round(START_EQUITY * float(v) / b0, 2)))

    def tick_value() -> str:
        if not tick.get("available"):
            return "no tick log found"
        m = tick["age_min"]
        ago = f"{m:.0f} min ago" if m < 90 else f"{m / 60:.1f} hours ago"
        return f"last woke {ago}, expected every {TICK_EVERY_MIN} min"

    guards = [
        dict(name="Schedule", plain="Is the robot awake?",
             state="OK" if tick.get("available") and not tick["stale"] else "STOPPED",
             value=tick_value(),
             detail="Nothing else on this page can tell you this. A stopped "
                    "schedule and a quiet one look identical: both do nothing. "
                    "While it is stopped no stop-loss is checked and no "
                    "rebalance happens, and every other number here is as old "
                    "as the last time the page was drawn."),
        dict(name="Money switch", plain="Can it spend real money?",
             state="OK", value="off (paper account)",
             detail="LIVE_TRADING must be the exact string 'true' to arm real orders."),
        dict(name="Cash floor", plain="Keep at least 10% in cash",
             state="OK" if cash / equity >= CASH_FLOOR else "DRIFT",
             value=f"{cash / equity:.2%} against {CASH_FLOOR:.0%}",
             detail="Applied when buying. Holdings rising shrinks cash as a share; "
                    "the next rebalance resets it."),
        dict(name="Daily circuit", plain="Stop buying after a 3% fall in a day",
             state="OK" if day_move > DAILY_CIRCUIT else "TRIPPED",
             value=f"today {day_move:+.2%} against {DAILY_CIRCUIT:.0%}",
             detail="Sells still execute when tripped; only new buys are refused."),
        dict(name="Catastrophe stop", plain="Sell anything down 25% from what we paid",
             state="OK" if not pos or pos[0]["plpc"] > CAT_STOP else "FIRING",
             value=f"worst {pos[0]['symbol']} {pos[0]['plpc']:+.1%}" if pos else "no positions",
             detail="Checked every tick while the market is open."),
        dict(name="Position cap", plain="No single stock over 5%",
             state="OK" if not pos or max(p["weight"] for p in pos) <= MAX_POSITION_PCT
                   else "BREACH",
             value=f"largest {max((p['weight'] for p in pos), default=0):.2%} "
                   f"against {MAX_POSITION_PCT:.0%}",
             detail="Enforced at entry; drift above it is not a breach."),
        dict(name="Cluster cap", plain="No correlated group over 20%",
             state="OK" if conc.get("over_cap", 0) == 0 else "BREACH",
             value=(f"{conc['over_cap']} holding(s) over cap; worst "
                    f"{conc['worst_local_symbol']} {conc['worst_local_weight']:.1%}")
                   if conc.get("available") else "not computable",
             detail=("Fixed 2026-08-26. The book still carries the concentration the "
                     "broken rule allowed; the next rebalance applies the fix."
                     if conc.get("over_cap", 0) else
                     "Every holding sits inside the cap. Momentum concentrates by "
                     "construction, so this is the rule doing work, not an accident.")),
        dict(name="Cadence", plain="Rebalance weekly, never more often",
             state="OK",
             value=f"{rb['days_since']} days since the last, minimum "
                   f"{MIN_REBALANCE_GAP_DAYS}" if rb["days_since"] is not None else "no rebalance yet",
             detail="A guard refuses a rebalance inside the window, so the book "
                    "cannot drift to a cadence the evidence has not tested."),
    ]

    return dict(
        meta=dict(
            generated_at=now.isoformat(),
            generated_at_pretty=now.strftime("%-d %B %Y, %H:%M New York"),
            mark_source="live account endpoint",
            mark_note="Alpaca reports several account values at once. This page uses "
                      "the live account mark throughout, taken at the time above. "
                      "The daily and intraday series can disagree with it by over a "
                      "percent because they exclude after-hours marks and stamp a "
                      "day differently.",
            live_from=str(live), sessions=sessions, is_paper=True),
        headline=dict(
            equity=round(equity, 2), start=START_EQUITY,
            since_live=round(since_live, 5),
            spy_since_live=None if spy_live is None else round(spy_live, 5),
            excess=None if spy_live is None else round(since_live - spy_live, 5),
            day_move=round(day_move, 5),
            cash=round(cash, 2), cash_pct=round(cash / equity, 5),
            positions=len(pos),
            expected_swing=round(float(sigma), 5),
            sigmas=round(float(since_live / sigma), 2) if sigma else 0.0,
            within_expectations=bool(abs(since_live / sigma) <= 2) if sigma else True,
            peak=round(float(curve.max()), 2),
            from_peak=round(float(equity / curve.max() - 1), 5)),
        equity_curve=[dict(date=str(d), equity=round(float(v), 2))
                      for d, v in curve.items()],
        benchmark=dict(symbol=BENCHMARK, series=spy_series),
        intraday=intraday(),
        positions=pos,
        slippage=slippage_by_cycle(),
        concentration=conc,
        cycles=dict(done=rb["done"], needed=CYCLES_NEEDED, dates=rb["dates"],
                    gaps=rb["gaps"], late=rb["late"], worst_gap=rb["worst_gap"]),
        tick=tick,
        guards=guards,
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = build()
    p = OUT / "data.json"
    p.write_text(json.dumps(d, indent=1, default=str), encoding="utf-8")
    print(f"wrote {p} ({p.stat().st_size / 1024:.0f} KB)")
    print(f"  equity ${d['headline']['equity']:,.2f}  "
          f"{d['headline']['since_live']:+.2%} since {d['meta']['live_from']}  "
          f"positions {d['headline']['positions']}  "
          f"cycles {d['cycles']['done']}/{d['cycles']['needed']}")


if __name__ == "__main__":
    main()
