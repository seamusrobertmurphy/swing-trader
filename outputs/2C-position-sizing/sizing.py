"""
2C - Position sizing (Chapter Two, Controls).

Standalone workbench copy of the sizing module. Canonical version lives in the
controls notebook (02-swing-controls.ipynb, position_plan). Develop here, fold back.

What it computes: an ATR-scaled, constant-dollar-risk size. A calmer coin earns a
larger clip, a livelier one a smaller clip, so the dollar risk is roughly constant
across coins. The clip is capped at a fraction of the account and floored at the
venue minimum notional.

  stop_pct    = stop_atr_mult * daily ATR%
  risk_budget = account * risk_per_trade_pct / 100
  raw_size    = risk_budget / (stop_pct / 100)
  position    = clamp(raw_size, min_notional, account * max_position_pct / 100)

Input: a coin's latest ATR% (from 2B). Output: the sizing table (and, wired into
the notebook, outputs/CSV/2C-sizing_YYYYMMDD.csv and 2C-sizing_YYYYMMDD.png).

Run:  python sizing.py
"""

import pandas as pd

# CONFIG subset mirrored from the notebook CONFIG (cell 4). Notebook is canonical.
CONFIG = dict(
    account_usdt       = 750.0,
    risk_per_trade_pct = 1.0,
    stop_atr_mult      = 1.5,
    max_position_pct   = 30.0,
    min_notional_usdt  = 10.0,
)


def position_plan(atr_pct, cfg=CONFIG, account=None):
    """Size so dollar risk is ~constant across coins. Higher ATR -> smaller clip.
    Capped at max_position_pct, floored at the venue minimum notional."""
    account = account or cfg["account_usdt"]
    stop_pct = cfg["stop_atr_mult"] * atr_pct
    risk_budget = account * cfg["risk_per_trade_pct"] / 100.0
    raw = risk_budget / (stop_pct / 100.0) if stop_pct > 0 else 0.0
    capped = min(raw, account * cfg["max_position_pct"] / 100.0)
    final = max(capped, cfg["min_notional_usdt"])
    return {"atr_pct": round(atr_pct, 3), "stop_pct": round(stop_pct, 3),
            "risk_budget_usdt": round(risk_budget, 2), "raw_size_usdt": round(raw, 2),
            "position_usdt": round(final, 2),
            "floored_at_min": bool(final == cfg["min_notional_usdt"]
                                   and capped < cfg["min_notional_usdt"])}


def size_table(atr_pct_by_symbol, cfg=CONFIG):
    """Build a sizing table for {symbol: atr_pct}, sorted by clip size."""
    rows = []
    for sym, atr in atr_pct_by_symbol.items():
        plan = position_plan(atr, cfg)
        rows.append({"symbol": sym, **plan})
    return (pd.DataFrame(rows)
            .sort_values("position_usdt", ascending=False)
            .reset_index(drop=True))


if __name__ == "__main__":
    # A spread of volatilities to show the inverse ATR-to-size relationship.
    demo = {"calm_3pct": 3.0, "mid_6pct": 6.0, "lively_10pct": 10.0}
    tab = size_table(demo)
    print(tab[["symbol", "atr_pct", "stop_pct", "position_usdt", "floored_at_min"]]
          .to_string(index=False))
    cap = CONFIG["account_usdt"] * CONFIG["max_position_pct"] / 100
    print(f"\nposition cap = ${cap:.0f}  ({CONFIG['max_position_pct']}% of "
          f"${CONFIG['account_usdt']:.0f})   min notional = ${CONFIG['min_notional_usdt']:.0f}")
