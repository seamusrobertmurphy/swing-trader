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
import fcntl
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import config
from alpaca_execution_report import SIP_DELAY_MIN
from alpaca_trade import (CLOSE_BUFFER_MIN, MIN_REBALANCE_GAP_DAYS,
                          OPEN_BUFFER_MIN, STATE, clients)

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable
OUT = REPO / "04-outputs" / "AA-evals"
REPORT_AFTER_CLOSE_MIN = 15     # let the closing marks settle before reporting

# A one-shot that lets the NEXT calm moment rebalance even though the weekly
# cadence guard would refuse. It exists for risk-control corrections, not for
# trading more often: when a control that should have been enforcing was found
# not to be, waiting a week to apply it means carrying a risk we have already
# measured and named. Written by hand (or by arm_rebalance.py), consumed once,
# then deleted, so it can never quietly become a faster cadence.
OVERRIDE = REPO / "05-research" / "memory" / "rebalance-override.json"

# The execution report cannot run in the same tick as the rebalance it measures:
# the data plan withholds minute bars for about SIP_DELAY_MIN minutes, so the
# reference VWAP for every fill is missing and nothing is measurable. Found
# 2026-08-27, when it ran 21 seconds after the fills and crashed. The rebalance
# leaves this marker instead and a later tick picks it up.
PENDING_REPORT = REPO / "05-research" / "memory" / "execution-report-pending.json"
PENDING_MAX_HOURS = 24          # give up rather than retry a stale marker forever

# Only one tick at a time, ever. Two schedulers can be live at once on the Mac
# (the launchd agent, and the run_forever.sh stopgap that exists because the
# agent is blocked by privacy control), and nothing downstream is safe against
# that: the cadence guard reads the last-rebalance stamp BEFORE the orders go
# in and writes it AFTER, so two ticks starting together both see a due
# rebalance and both trade. This is the guard that makes the overlap harmless.
LOCK = REPO / "04-outputs" / "AA-evals" / "logs" / "tick.lock"


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


def run_sh(script: Path) -> int:
    """Run a shell helper, streaming its output into this tick's log."""
    log(f"RUN {script.name}")
    p = subprocess.run(["/bin/bash", str(script)], cwd=REPO,
                       capture_output=True, text=True)
    for line in (p.stdout + p.stderr).splitlines():
        print(f"    {line}", flush=True)
    if p.returncode != 0:
        log(f"FAILED rc={p.returncode}: {script.name}")
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

    # Held for the whole tick and released when the process exits, however it
    # exits. A second tick does not queue behind it: it says so and leaves,
    # because the work is due-based and the running tick is already doing it.
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    lock_fh = open(LOCK, "w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("another tick is already running; leaving this one to it.")
        return 0

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

    # 0. The execution report owed by an earlier tick's rebalance, once the
    #    data plan will actually serve the bars it needs.
    if PENDING_REPORT.exists() and not a.dry_run:
        try:
            since = datetime.fromisoformat(json.loads(
                PENDING_REPORT.read_text())["filled_at"])
            age_min = (now - since).total_seconds() / 60
        except Exception as e:  # noqa: BLE001
            log(f"pending execution-report marker unreadable ({e}); removing it.")
            PENDING_REPORT.unlink(missing_ok=True)
            age_min = None
        if age_min is not None:
            if age_min > PENDING_MAX_HOURS * 60:
                log(f"execution report owed since {since:%Y-%m-%d %H:%M}Z is over "
                    f"{PENDING_MAX_HOURS}h old; dropping it unmeasured.")
                PENDING_REPORT.unlink(missing_ok=True)
            elif age_min >= SIP_DELAY_MIN:
                if run("03-inputs/alpaca_execution_report.py") == 0:
                    PENDING_REPORT.unlink(missing_ok=True)
                    did.append("execution report (deferred)")
                else:
                    rc |= 1
            else:
                log(f"execution report owed, but the newest fill is only "
                    f"{age_min:.0f} min old and bars arrive at {SIP_DELAY_MIN}; "
                    f"waiting for the next tick.")

    # 1. Catastrophe stop, every tick the market is open.
    if clock.is_open:
        if a.dry_run:
            did.append("would run the catastrophe-stop check")
        else:
            rc |= run("03-inputs/alpaca_trade.py", "check")
            did.append("catastrophe-stop check")

    # 2. Rebalance, when the cadence is due and we are in a calm part of the day.
    gap = days_since_rebalance()
    due = gap is None or gap >= MIN_REBALANCE_GAP_DAYS
    override = None
    if OVERRIDE.exists():
        try:
            override = json.loads(OVERRIDE.read_text())
            expires = datetime.fromisoformat(override["expires"])
            if datetime.now(timezone.utc) > expires:
                log(f"one-shot rebalance override EXPIRED unused ({override['reason']}); "
                    f"removing it rather than acting on a stale instruction.")
                OVERRIDE.unlink()
                override = None
            else:
                due = True
                log(f"one-shot rebalance override armed: {override['reason']} "
                    f"(expires {expires:%Y-%m-%d %H:%M}Z)")
        except Exception as e:  # noqa: BLE001
            log(f"override file unreadable ({e}); ignoring it.")
            override = None
    calm = (clock.is_open and since_open is not None and to_close is not None
            and since_open >= OPEN_BUFFER_MIN and to_close >= CLOSE_BUFFER_MIN)
    if due and calm:
        if a.dry_run:
            did.append(f"would rebalance (last was {gap if gap is None else round(gap,1)} days ago)")
        else:
            rc |= run("03-inputs/alpaca_data.py", "download")
            cmd = ["03-inputs/alpaca_trade.py", "rebalance", "--execute"]
            if override:
                # --force overrides the CADENCE guard only. The session guard is
                # deliberately left on, so even a forced rebalance still refuses
                # to submit into an opening or closing auction.
                cmd.append("--force")
            rc2 = run(*cmd)
            rc |= rc2
            # Owed, not run: see PENDING_REPORT above.
            PENDING_REPORT.write_text(json.dumps(
                {"filled_at": datetime.now(timezone.utc).isoformat()}))
            log(f"execution report deferred by {SIP_DELAY_MIN} min "
                f"(the data plan withholds bars that new).")
            did.append("rebalance" + (" (one-shot override)" if override else ""))
            if override and rc2 == 0:
                OVERRIDE.unlink(missing_ok=True)
                log("one-shot override consumed and removed; cadence guard is "
                    "back in force.")
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
            rc |= run("03-inputs/alpaca_trade.py", "status")
            rc |= run("03-inputs/alpaca_daily_report.py")
            did.append("daily report")

    # 4. Refresh the dashboard whenever anything happened, and once after the
    #    close regardless, so the page is never stale on the day it matters.
    #    It is skipped silently where Quarto or R are absent: a machine that
    #    only trades is not broken for lacking a drawing tool.
    if did and not a.dry_run:
        rc |= run_sh(REPO / "05-research" / "scripts" / "render_dashboard.sh")
        did.append("dashboard refreshed")

    log("did: " + (", ".join(did) if did else "nothing, nothing was due"))
    return 1 if rc else 0


if __name__ == "__main__":
    raise SystemExit(main())
