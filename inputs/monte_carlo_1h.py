"""Monte Carlo robustness for a strategy's after-fee per-trade returns (the Stability gate).

A single backtest is ONE realized path. Monte Carlo asks the two questions that path cannot answer:
is the result robust or luck, and what is the realistic worst case? Three resamplings on the
after-fee per-trade return series:

  - Bootstrap (resample WITH replacement): distribution of total return, max drawdown and Sharpe ->
    confidence intervals and the probability of ending a loser. A block bootstrap (block>1) preserves
    short autocorrelation between consecutive trades.
  - Reorder (shuffle WITHOUT replacement): same trades, random order -> exposes how path-dependent the
    drawdown is (the realized max DD is just one ordering).
  - Sign-flip permutation null: under "no edge" each trade's direction is a coin flip; p = P(null mean
    >= actual mean) is a significance read on whether the magnitude/direction pairing carries edge.

Decision rule (Stability): a strategy is robust only if the bootstrap 5th-percentile total return is
positive, p(loss) is low, and the permutation p-value is small (< 0.05). This is SEPARATE from the
after-fee GO/NO-GO, which it gates.

No keys, no orders, read-only. Writes outputs/AA-evals/<date>/monte-carlo-<date>.md per protocol.

Usage:
  .venv/bin/python inputs/monte_carlo_1h.py --csv inputs/binance-data/trades.csv --col ret
  # or import: from monte_carlo_1h import summary; summary(trade_returns)
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

EPS = 1e-12


def _equity_stats(rets: np.ndarray):
    """Total return, max drawdown (negative), and a per-trade-annualized Sharpe for a return path."""
    eq = np.cumprod(1.0 + rets)
    peak = np.maximum.accumulate(eq)
    max_dd = float(((eq - peak) / peak).min())
    total = float(eq[-1] - 1.0)
    sharpe = float(rets.mean() / (rets.std(ddof=1) + EPS) * np.sqrt(len(rets))) if len(rets) > 1 else 0.0
    return total, max_dd, sharpe


def bootstrap(trade_returns, n_sims=10000, block=1, seed=0):
    """Resample the trade sequence n_sims times; return arrays of total/maxdd/sharpe per path."""
    r = np.asarray(trade_returns, float)
    n = len(r)
    rng = np.random.default_rng(seed)
    tot = np.empty(n_sims); mdd = np.empty(n_sims); shp = np.empty(n_sims)
    for s in range(n_sims):
        if block <= 1:
            sample = r[rng.integers(0, n, n)]
        else:                                              # block bootstrap (preserve local autocorr)
            starts = rng.integers(0, n, int(np.ceil(n / block)))
            idx = np.concatenate([np.arange(st, st + block) for st in starts]) % n
            sample = r[idx[:n]]
        tot[s], mdd[s], shp[s] = _equity_stats(sample)
    return dict(total=tot, maxdd=mdd, sharpe=shp)


def reorder_drawdown(trade_returns, n_sims=10000, seed=0):
    """Same trades, shuffled order -> distribution of max drawdown (path dependence)."""
    r = np.asarray(trade_returns, float)
    rng = np.random.default_rng(seed)
    mdd = np.empty(n_sims)
    for s in range(n_sims):
        _, mdd[s], _ = _equity_stats(rng.permutation(r))
    return mdd


def permutation_pvalue(trade_returns, n_sims=10000, seed=0):
    """Sign-flip null: under no edge each trade's sign is a coin flip (magnitudes kept).
    p = P(null mean return >= actual mean return)."""
    r = np.asarray(trade_returns, float)
    actual = r.mean()
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n_sims, len(r)))
    null_means = (signs * np.abs(r)).mean(axis=1)
    return float((null_means >= actual).mean())


def summary(trade_returns, n_sims=10000, block=1):
    r = np.asarray(trade_returns, float)
    if len(r) < 20:
        raise SystemExit(f"need >=20 trades for Monte Carlo, got {len(r)}")
    a_total, a_mdd, a_sharpe = _equity_stats(r)
    bs = bootstrap(r, n_sims, block)
    re_mdd = reorder_drawdown(r, n_sims)
    p = lambda arr, q: float(np.percentile(arr, q))
    return dict(
        n_trades=len(r), n_sims=n_sims, block=block,
        actual_total=a_total, actual_maxdd=a_mdd, actual_sharpe=a_sharpe,
        total_p5=p(bs["total"], 5), total_p50=p(bs["total"], 50), total_p95=p(bs["total"], 95),
        maxdd_worst5=p(bs["maxdd"], 5), maxdd_p50=p(bs["maxdd"], 50),       # p5 = worst 5% drawdown
        reorder_maxdd_worst5=p(re_mdd, 5),
        sharpe_p5=p(bs["sharpe"], 5), sharpe_p50=p(bs["sharpe"], 50),
        prob_loss=float((bs["total"] <= 0).mean()),
        perm_pvalue=permutation_pvalue(r, n_sims))


def verdict(s: dict) -> str:
    return "ROBUST" if (s["total_p5"] > 0 and s["prob_loss"] < 0.05 and s["perm_pvalue"] < 0.05) else "FRAGILE"


def write_record(s: dict, evals_dir: str, label: str = "") -> str:
    os.makedirs(evals_dir, exist_ok=True)
    cd = datetime.now(timezone.utc).strftime("%Y%m%d"); hd = f"{cd[:4]}-{cd[4:6]}-{cd[6:]}"
    run_dir = os.path.join(evals_dir, hd); os.makedirs(run_dir, exist_ok=True)
    stem = f"monte-carlo-{cd}"
    v = verdict(s)
    lines = [f"# Monte Carlo robustness ({hd})\n",
             f"{label} {s['n_sims']:,} simulations on {s['n_trades']:,} after-fee per-trade returns "
             f"(block={s['block']}). Bootstrap = resample with replacement; reorder = shuffle order; "
             f"sign-flip = no-edge null. ROBUST requires total P5 > 0, p(loss) < 5%, p-value < 0.05.\n",
             "| metric | actual | P5 (worst) | median | P95 |",
             "| --- | --- | --- | --- | --- |",
             f"| total return | {s['actual_total']:+.2%} | {s['total_p5']:+.2%} | {s['total_p50']:+.2%} | {s['total_p95']:+.2%} |",
             f"| max drawdown | {s['actual_maxdd']:.2%} | {s['maxdd_worst5']:.2%} | {s['maxdd_p50']:.2%} | - |",
             f"| Sharpe | {s['actual_sharpe']:.2f} | {s['sharpe_p5']:.2f} | {s['sharpe_p50']:.2f} | - |",
             f"\n- probability of a losing outcome: **{s['prob_loss']:.1%}**",
             f"\n- reorder worst-5% max drawdown: **{s['reorder_maxdd_worst5']:.2%}** (path dependence)",
             f"\n- sign-flip permutation p-value: **{s['perm_pvalue']:.4f}**",
             f"\n\n**Verdict: {v}.**\n"]
    md = os.path.join(run_dir, f"{stem}.md"); open(md, "w").write("\n".join(lines) + "\n")
    return md


def main():
    ap = argparse.ArgumentParser(description="Monte Carlo robustness on after-fee per-trade returns")
    ap.add_argument("--csv", required=True, help="CSV with a per-trade return column")
    ap.add_argument("--col", default="ret", help="the return column name (default: ret)")
    ap.add_argument("--n-sims", type=int, default=10000)
    ap.add_argument("--block", type=int, default=1, help="block size for the block bootstrap")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    import train_model as tm
    out = a.out or os.path.join(tm.OUT, "AA-evals")
    rets = pd.read_csv(a.csv)[a.col].dropna().to_numpy(float)
    s = summary(rets, a.n_sims, a.block)
    print(f"trades {s['n_trades']}  actual {s['actual_total']:+.2%}  "
          f"P5 {s['total_p5']:+.2%}  p(loss) {s['prob_loss']:.1%}  pval {s['perm_pvalue']:.4f}  "
          f"-> {verdict(s)}")
    print("record:", write_record(s, out, label=f"Source: {os.path.basename(a.csv)}."))


if __name__ == "__main__":
    main()
