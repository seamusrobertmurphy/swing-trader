# Moving this repo to another machine

Written 26 August 2026, after testing every step below on a clean clone with a
fresh environment and no macOS Keychain.

## What travels

The clone is about 250 MB. Two large things are deliberately left behind
because both rebuild from the API:

The daily price bars, 5.2 GB in `03-inputs/alpaca-data/daily/`. Rebuild with one
command, below. The Python environment, 44 GB on the Mac because it carries the
research stack. The new machine needs 261 MB of it.

Nothing else is machine-specific. No script contains an absolute path any more;
each works out where it lives.

## Five commands

On the new machine:

```
git clone <this repo> day-trader && cd day-trader
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./scripts/set_credentials.sh KEY SECRET     # or run it bare and it prompts
.venv/bin/python 03-inputs/alpaca_data.py download
./scripts/install_schedule.sh
```

The third line takes the two Alpaca keys, writes them to
`~/.config/daytrader/env` at mode 600, outside the repo so they can never be
committed, and then proves them by calling the live paper account. Skip it
entirely if the keys are already environment variables on that machine: the
loader checks the environment first.

The fourth line downloads about 5 GB of price history and takes a while. The
book cannot pick stocks without it.

## What runs, and when

One job, every twenty minutes, all day. It is called a tick. Almost every time
it wakes up it looks at the clock, sees nothing is due, writes one line to a
log and goes back to sleep.

When something is due it acts. While the market is open it checks the
catastrophe stop, which sells anything down 25% from what we paid. Once a week,
when the rebalance is due and the moment is calm, it downloads fresh bars,
rebalances the book and measures what the trades cost. After the close it writes
the daily report.

There are no clock times anywhere in the schedule. That is deliberate. A
schedule that says "Monday 07:30" is really saying "Monday 07:30 in the
timezone of the machine that wrote it", and moving the machine breaks it
silently: the job still runs, the market is shut, nothing trades, and no error
appears anywhere. The tick asks the exchange what time it is instead, so it is
correct in any timezone without being told which one it is in.

`install_schedule.sh` sets this up as a systemd timer on Linux and a launchd
agent on macOS, and then verifies it rather than assuming it worked.

## The one Linux-specific step

User services on Linux stop when you log out, which is exactly what happens on
a machine you connect to and then leave. To keep the schedule running after you
disconnect, once:

```
sudo loginctl enable-linger $USER
```

The installer checks and tells you if this is missing.

## Watching it

```
./scripts/install_schedule.sh verify     # is it registered, can it read, does a tick run
systemctl --user list-timers daytrader-tick.timer
journalctl --user -u daytrader-tick -n 50
tail -f 04-outputs/AA-evals/logs/tick-*.log
```

The daily report lands in `04-outputs/AA-evals/<date>/DAILY-*.md` and opens with
the account block: what the money is worth, what it did, what it cost to trade,
and whether that was within expectations.

## What is proven, and what is not

Tested 27 August 2026, on this Mac, against the live paper account.

The login Keychain is readable from a launchd agent. This was the second
suspected blocker and it is not one: a probe agent read `ALPACA_API_KEY` and
returned its length. Cron still cannot, which is why the schedule is a launchd
agent and not a crontab line.

The chain past `/bin/bash` is still unproven, because the grant below has not
been made. The venv interpreter is a different binary on the same blocked
volume, and macOS permits executing a file it refuses to read, so python can
start and then die reading its own library. `install_schedule.sh verify` now
runs a whole tick inside the background context rather than reading one file,
so the moment the grant is made it answers this rather than leaving it assumed.

## Why the Mac is the awkward one

The Mac keeps this repo on a portable SSD, and macOS refuses background jobs
read access to a removable volume until you grant it by hand. The job dies
before running a line, with the same symptom as nothing being scheduled. On the
Mac you must add `/bin/bash` under System Settings, Privacy & Security, Full
Disk Access. Linux has no equivalent restriction, so this problem disappears on
the new machine.

Cron is also not usable on the Mac here: it runs outside the login session and
cannot read the Keychain where the Mac's keys live, so it fails silently. On
Linux, where credentials come from a file or the environment, cron would be
fine, but the systemd timer is better because it catches up after the machine
sleeps.

## Still true after the move

The money switch is off. `LIVE_TRADING` defaults to false and the code refuses
the live endpoint without it being the exact string `true`. Never-short and
never-margin are enforced in code, not by configuration. The account is a paper
account.

## Optional: the research stack

Only if you want to run the notebooks or rebuild the feature datasets:

```
.venv/bin/pip install -r requirements-research.txt
```

TA-Lib in that list needs its C library installed first and is the one genuinely
awkward dependency. It is optional. Without it the code skips that feature block
and says so; it cannot silently change a live decision.
