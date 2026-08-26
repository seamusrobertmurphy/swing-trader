"""One wake-up of the trading schedule: decide what is due, do it, or exit quiet.

WHY A TICK AND NOT A CALENDAR. A cron or timer entry hard-codes a wall-clock
time, which means it encodes a timezone. Move the machine (a Mac in Los Angeles
to a Linux box anywhere) and every entry is silently wrong, and the failure is
invisible: the job runs, the market is shut, nothing trades. This asks Alpaca's
own clock instead, so the schedule is correct on any machine in any timezone
without editing anything.

Run it every 15-30 minutes all day. It is cheap and almost always a no-op.

    REBALANCE  when the market is open, we are at least OPEN_BUFFER_MIN past
               the bell and not inside CLOSE_BUFFER_MIN of the close, and the
               last rebalance was at least MIN_REBALANCE_GAP_DAYS ago.
               alpaca_trade.py re-checks all of that itself and refuses
               otherwise, so this can only ever be over-cautious, never
               over-eager.
    REPORT     once per trading day, after the close, if today has no report.
    STOP CHECK every tick while the market is open: the catastrophe stop is the
               one control that should not wait for a scheduled slot.

Exit codes: 0 nothing due or work done; 1 something failed and was logged.

    .venv/bin/python inputs/schedule_tick.py            act
    .venv/bin/python inputs/schedule_tick.py --dry-run  say what it would do
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import config
from alpaca_trade import (CLOSE_BUFFER_MIN, MIN_REBALANCE_GAP_DAYS,
                          OPEN_BUFFER_MIN, STATE, clients)

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable
OUT = REPO / "outputs" / "AA-evals"
REPORT_AFTER_CLOSE_MIN = 15     # let the closing marks settle before reporting


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} {msg}", flush=True)


def run(*args: str) -> int:
    """Run one repo tool, streaming its output into this tick's log."""
    log(f"RUN {' '.join(args)}")
    p = subprocess.run([PY, *args], cwd=REPO, capture_output=True, text=True)
    for line in (p.stdout + p.stderr).splitlines():
        print(f"    {line}", flush=True)
    if p.returncode != 0:
        log(f"FAILED rc={p.returncode}: {' '.join(args)}")
    return p.returncode


def days_since_rebalance() -> float | None:
    if not STATE.exists():
        return None
    last = datetime.fromisoformat(json.loads(STATE.read_text())["last_rebalance"])
    return (datetime.now(timezone.utc) - last).total_seconds() / 86400


def report_written_today(day: str) -> bool:
    d = OUT / day
    return d.exists() and any(d.glob("DAILY-*.md"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report what is due, change nothing")
    a = ap.parse_args()

    config.require("ALPACA_API_KEY", "ALPACA_API_SECRET")
    tc = clients()
    clock = tc.get_clock()
    now = datetime.now(timezone.utc)
    et = clock.timestamp                      # exchange-local, tz-aware
    today = et.date()

    # Today's actual session times, from the exchange calendar rather than
    # assumed. Two things break the assumed version: while the market is shut,
    # clock.next_close is TOMORROW's close, so "minutes since the close" is a
    # large positive number and an after-close test never fires; and half-day
    # sessions close at 13:00, so a hard-coded 390-minute session puts the
    # "minutes since the bell" out by three hours.
    from alpaca.trading.requests import GetCalendarRequest
    cal = tc.get_calendar(GetCalendarRequest(start=today, end=today))
    session = cal[0] if cal else None
    since_open = to_close = None
    if session is not None:
        s_open = session.open.replace(tzinfo=et.tzinfo) if session.open.tzinfo is None \
            else session.open.astimezone(et.tzinfo)
        s_close = session.close.replace(tzinfo=et.tzinfo) if session.close.tzinfo is None \
            else session.close.astimezone(et.tzinfo)
        s_open = et.replace(hour=s_open.hour, minute=s_open.minute,
                            second=0, microsecond=0)
        s_close = et.replace(hour=s_close.hour, minute=s_close.minute,
                             second=0, microsecond=0)
        since_open = (et - s_open).total_seconds() / 60
        to_close = (s_close - et).total_seconds() / 60

    if session is None:
        log(f"tick: {today} is not a trading day (exchange time {et:%H:%M %Z}). "
            f"Next open {clock.next_open:%Y-%m-%d %H:%M %Z}.")
    else:
        log(f"tick: market {'OPEN' if clock.is_open else 'shut'}, exchange time "
            f"{et:%Y-%m-%d %H:%M %Z}, {since_open:+.0f} min from the bell, "
            f"{to_close:+.0f} min to the close")

    did, rc = [], 0
    day = f"{today:%Y-%m-%d}"      # exchange date; after 20:00 ET the UTC date
                                   # has already rolled and would misfile it

    # 1. Catastrophe stop, every tick the market is open.
    if clock.is_open:
        if a.dry_run:
            did.append("would run the catastrophe-stop check")
        else:
            rc |= run("inputs/alpaca_trade.py", "check")
            did.append("catastrophe-stop check")

    # 2. Rebalance, when the cadence is due and we are in a calm part of the day.
    gap = days_since_rebalance()
    due = gap is None or gap >= MIN_REBALANCE_GAP_DAYS
    calm = (clock.is_open and since_open is not None and to_close is not None
            and since_open >= OPEN_BUFFER_MIN and to_close >= CLOSE_BUFFER_MIN)
    if due and calm:
        if a.dry_run:
            did.append(f"would rebalance (last was {gap if gap is None else round(gap,1)} days ago)")
        else:
            rc |= run("inputs/alpaca_data.py", "download")
            rc |= run("inputs/alpaca_trade.py", "rebalance", "--execute")
            rc |= run("inputs/alpaca_execution_report.py")
            did.append("rebalance")
    elif due and not calm:
        log(f"rebalance is due ({gap and round(gap, 1)} days) but this is not a calm "
            f"moment to trade; waiting for the next tick inside the session.")

    # 3. Daily report, once, after the close of a day that actually had a
    # session. No session, no report: a Saturday tick should be silent.
    after_close = (session is not None and not clock.is_open
                   and to_close is not None and to_close <= -REPORT_AFTER_CLOSE_MIN)
    if after_close and not report_written_today(day):
        if a.dry_run:
            did.append("would write the daily report")
        else:
            rc |= run("inputs/alpaca_trade.py", "status")
            rc |= run("inputs/alpaca_daily_report.py")
            did.append("daily report")

    log("did: " + (", ".join(did) if did else "nothing, nothing was due"))
    return 1 if rc else 0


if __name__ == "__main__":
    raise SystemExit(main())
