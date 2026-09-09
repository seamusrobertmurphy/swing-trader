"""The timeline's milestones: the few points where the approach changed.

A milestone is a notable change to the model design, the input data, or the
workflow strategy. Operator definition, 8 September 2026. It is not a run. The
timeline draws every run as its background and marks these on top of it, because
there are hundreds of the former and a few dozen of the latter, and a chart that
treats them alike says nothing.

Held as JSON at 04-outputs/AA-evals/milestones.json so it can be edited by hand
and read by the page. Seeded below from what actually changed in this
repository, each entry naming the record or the file that shows it, because a
milestone nobody can check is a caption.

    .venv/bin/python 03-inputs/milestones.py            # print the timeline
    .venv/bin/python 03-inputs/milestones.py --seed     # write the seed, keeping any additions
    .venv/bin/python 03-inputs/milestones.py --add "2026-09-09|design|What changed|where.md"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORE = REPO / "04-outputs" / "AA-evals" / "milestones.json"

# Three kinds, and every entry is one of them. The operator's own words: a
# notable change to the model design, the input data, or the workflow strategy.
KINDS = {
    "design": "model design",
    "data": "input data",
    "workflow": "workflow strategy",
}

SEED = [
    ("2026-06-21", "data",
     "The frame moved from ten fixed coins on daily bars to the whole active "
     "USDT market on hourly bars, roughly 433 pairs, screened point-in-time.",
     "05-research/tasks/data-standards.md"),
    ("2026-06-21", "data",
     "Storage moved from CSV to Parquet. Round-tripping timestamps through CSV "
     "silently turned datetimes into strings and broke the train-test split on "
     "load; Parquet preserves the types.",
     "03-inputs/build_dataset_1h.py"),
    ("2026-06-21", "design",
     "The label became an ATR-scaled triple barrier on a day-trade horizon, "
     "replacing the inherited plus ten per cent, minus five per cent, twenty-day "
     "geometry.",
     "03-inputs/build_dataset_1h.py"),
    ("2026-06-21", "data",
     "The universe was enumerated from the public archive listing rather than "
     "from the live exchange, which added 612 pairs against 433 and included "
     "every coin since delisted. Survivorship bias removed at the source.",
     "03-inputs/acquire_vision.py"),
    ("2026-06-23", "design",
     "The model set widened past LightGBM to seven estimators, and four causal "
     "feature families were added, including relative strength against bitcoin, "
     "the first family not derived from the asset's own price.",
     "03-inputs/model_assessment_1h.py"),
    ("2026-06-23", "workflow",
     "Diagnosed that hourly direction prediction sits at the efficient-market "
     "floor. Edge requires changing the problem, not tuning the model.",
     "04-outputs/AA-evals/evaluation-scores.md"),
    ("2026-06-24", "data",
     "The four-hour frame was built survivorship-complete, 567 coins, and became "
     "the working frame: it carries more signal than hourly, AUC 0.55 against 0.51.",
     "03-inputs/binance-data/dataset_4h_allmarket.parquet"),
    ("2026-06-24", "design",
     "Cross-sectional relative strength found: 25 of 42 signals sign-stable "
     "between training and test. The first stable signal in the project, and "
     "still the one never disproved.",
     "03-inputs/cross_sectional_4h.py"),
    ("2026-08-17", "workflow",
     "The crypto edge search was closed. No candidate cleared the fee line at "
     "15 to 20 basis points on any frame or gate.",
     "05-research/tasks/workplan-alpaca-hires-2026-08-17.md"),
    ("2026-08-18", "data",
     "The equity track opened: 12,539 US equities enumerated, 2,673 past the "
     "dollar-volume screen, adjusted daily bars back to 2016.",
     "03-inputs/alpaca_data.py"),
    ("2026-08-18", "design",
     "Twelve-month momentum skipping the last month survived every check, the "
     "first result in the project to do so. Spread of about one per cent a month "
     "on non-overlapping monthly holds.",
     "03-inputs/equity_momentum_monthly.py"),
    ("2026-08-18", "workflow",
     "The paper book went live on the equity result: fifty names at 1.8 per cent, "
     "rebalanced weekly, never short and never on margin, in code.",
     "03-inputs/alpaca_trade.py"),
    ("2026-09-06", "workflow",
     "The repository was reorganised into five numbered folders and the overfit "
     "ratio, which had been computed upside down, was corrected. A reader "
     "applying the rejection rule to the old column would have passed exactly "
     "the models it exists to catch.",
     "03-inputs/model_metrics.py"),
    ("2026-09-07", "workflow",
     "The workflow moved from a notebook to Quarto. Pandoc had been silently "
     "discarding every saved record because they arrived as raw blocks addressed "
     "to another format, so the document had no model results in it at all.",
     "02-runtime/trader-workflow.qmd"),
    ("2026-09-08", "design",
     "Probability calibration measured for the first time. Expected calibration "
     "error 0.2344 raw, and two thirds of it caused by one argument, the balanced "
     "class weight, on the metric the models are ranked by.",
     "04-outputs/AA-evals/2026-09-08/calibration-4h-balanced-20260908.md"),
    ("2026-09-08", "design",
     "Theil's U and MISE added, defined for a nought-or-one outcome rather than "
     "taken off a shelf. U2 gives the first single number for whether a model "
     "beats always predicting the base rate.",
     "03-inputs/model_metrics.py"),
    ("2026-09-08", "workflow",
     "The bench: one configuration in ten sections, edited by the panel that owns "
     "each part and consumed by one runner, with every record embedding the "
     "settings that produced it.",
     "03-inputs/bench_config.py"),
    ("2026-09-08", "design",
     "Seventy-two sweeps over six conditions and four axes overturned the "
     "configuration ranking found on a single condition. The class weight moves "
     "held-out error nearly as far as the whole nine-parameter space.",
     "04-outputs/AA-evals/bench-digest.md"),
]


def load() -> list[dict]:
    if not STORE.exists():
        return []
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save(rows: list[dict]) -> Path:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r["date"], r["kind"], r["what"][:40]))
    STORE.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return STORE


def seed(keep_additions: bool = True) -> list[dict]:
    """Write the seed. Anything added by hand since is kept."""
    seeded = [dict(date=d, kind=k, what=w, where=src) for d, k, w, src in SEED]
    if keep_additions:
        known = {(r["date"], r["what"][:60]) for r in seeded}
        seeded += [r for r in load() if (r["date"], r["what"][:60]) not in known]
    save(seeded)
    return seeded


def add(date: str, kind: str, what: str, where: str = "") -> list[dict]:
    if kind not in KINDS:
        raise SystemExit(f"kind must be one of {', '.join(KINDS)}; got {kind!r}")
    rows = load()
    rows.append(dict(date=date, kind=kind, what=what, where=where))
    save(rows)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", action="store_true", help="write the seed set")
    ap.add_argument("--add", default=None,
                    help='"YYYY-MM-DD|kind|what changed|where it shows"')
    a = ap.parse_args()

    if a.seed:
        rows = seed()
        print(f"seeded {len(rows)} milestones to {STORE.relative_to(REPO)}")
    elif a.add:
        parts = a.add.split("|")
        if len(parts) < 3:
            raise SystemExit('need "date|kind|what" and optionally "|where"')
        rows = add(parts[0].strip(), parts[1].strip(), parts[2].strip(),
                   parts[3].strip() if len(parts) > 3 else "")
        print(f"{len(rows)} milestones now in {STORE.relative_to(REPO)}")
    else:
        rows = load() or seed()

    for r in rows:
        print(f"  {r['date']}  {KINDS[r['kind']]:16s}  {r['what'][:82]}")
    counts = {k: sum(1 for r in rows if r["kind"] == k) for k in KINDS}
    print(f"\n{len(rows)} milestones: "
          + ", ".join(f"{v} {KINDS[k]}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
