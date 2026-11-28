"""
Four ways to visualize the screen's spread gate, for comparison.

Reads the latest outputs/CSV/2A-sample_*.csv and writes four PNGs here. Each frames
the spread differently so you can pick which to fold into the notebook:

  option-1-sorted-bars.png        the gate at a glance (who clears 0.05%)
  option-2-spread-vs-liquidity.png  why the gate works (spread tightens with volume)
  option-3-cost-stack.png         spread as a cost added on top of the fee
  option-4-cost-vs-atr.png        spread (cost) against ATR (opportunity)

Run:  python build_spread_options.py
"""

import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "CSV"))

SPREAD_CEIL = 0.05      # max_spread_pct gate
LIQ_FLOOR_M = 30.0      # liquidity floor (USD millions)
ATR_FLOOR, ATR_CEIL = 2.5, 12.0
FEE_SLIP = 0.20         # round-trip fee + slippage (with BNB), percent
NAVY, GREEN, RED, GREY = "#0B3D66", "#2E8B57", "#B22222", "#888888"


def load():
    files = sorted(glob.glob(os.path.join(CSV_DIR, "2A-sample_*.csv")))
    df = pd.read_csv(files[-1])
    for c in ("g_liq", "g_atr", "g_sp", "g_hist", "passed"):
        if c in df.columns and df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip().str.lower().eq("true")
    return df.dropna(subset=["spread"]).copy()


def _ceil_label(ax, y, text):
    ax.annotate(text, xy=(0.995, y), xycoords=ax.get_yaxis_transform(),
                ha="right", va="bottom", color=GREY, fontsize=8)


def opt1_sorted_bars(df):
    d = df.sort_values("spread")
    colors = [GREEN if v <= SPREAD_CEIL else RED for v in d["spread"]]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.bar(d["symbol"], d["spread"], color=colors)
    ax.axhline(SPREAD_CEIL, color=GREY, ls="--", lw=1)
    _ceil_label(ax, SPREAD_CEIL, f"ceiling {SPREAD_CEIL}%")
    ax.set_ylabel("spread %")
    ax.set_title("Option 1 - Sorted spread vs the gate ceiling (green clears, red rejected)")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    ax.grid(True, axis="y", ls=":", alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "option-1-sorted-bars.png"), dpi=160)
    plt.close(fig)


def opt2_spread_vs_liquidity(df):
    fig, ax = plt.subplots(figsize=(7.8, 5.4))
    for grp, name, col in [(df[~df["g_sp"]], "fails spread", RED),
                           (df[df["g_sp"]], "clears spread", GREEN)]:
        if len(grp):
            ax.scatter(grp["vol_m"], grp["spread"].clip(lower=1e-4), s=70, c=col,
                       alpha=0.8, edgecolors="white", linewidths=1, label=name)
            for _, r in grp.iterrows():
                ax.annotate(r["symbol"], (r["vol_m"], max(r["spread"], 1e-4)),
                            textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7)
    ax.axhline(SPREAD_CEIL, color=GREY, ls="--", lw=1)
    ax.axvline(LIQ_FLOOR_M, color=GREY, ls=":", lw=1)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("24h quote volume (USD millions, log)")
    ax.set_ylabel("spread % (log)")
    ax.set_title("Option 2 - Spread vs liquidity (spreads tighten as volume rises)")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    ax.grid(True, which="both", ls=":", alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "option-2-spread-vs-liquidity.png"), dpi=160)
    plt.close(fig)


def opt3_cost_stack(df):
    d = df.copy()
    d["total"] = FEE_SLIP + d["spread"]
    d = d.sort_values("total")
    base = [FEE_SLIP] * len(d)
    spr_colors = [GREEN if v <= SPREAD_CEIL else RED for v in d["spread"]]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(d["symbol"], base, color=NAVY, label=f"fee + slippage ({FEE_SLIP}%)")
    ax.bar(d["symbol"], d["spread"], bottom=base, color=spr_colors, label="spread (added cost)")
    ax.axhline(FEE_SLIP + SPREAD_CEIL, color=GREY, ls="--", lw=1)
    _ceil_label(ax, FEE_SLIP + SPREAD_CEIL, f"gate budget ({FEE_SLIP}% + {SPREAD_CEIL}%)")
    ax.set_ylabel("round-trip cost %")
    ax.set_title("Option 3 - Spread as an add-on cost to the fee (total cost to round-trip)")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    ax.grid(True, axis="y", ls=":", alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "option-3-cost-stack.png"), dpi=160)
    plt.close(fig)


def opt4_cost_vs_atr(df):
    fig, ax = plt.subplots(figsize=(7.8, 5.6))
    ax.axvspan(ATR_FLOOR, ATR_CEIL, color=GREEN, alpha=0.06, lw=0)
    for grp, name, col in [(df[~df["passed"]], "rejected", RED),
                           (df[df["passed"]], "sample", GREEN)]:
        if len(grp):
            ax.scatter(grp["atr"].clip(lower=0.05), grp["spread"].clip(lower=1e-4), s=70,
                       c=col, alpha=0.8, edgecolors="white", linewidths=1, label=name)
            for _, r in grp.iterrows():
                if pd.notna(r["atr"]):
                    ax.annotate(r["symbol"], (max(r["atr"], 0.05), max(r["spread"], 1e-4)),
                                textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7)
    ax.axhline(SPREAD_CEIL, color=GREY, ls="--", lw=1)
    ax.axvline(ATR_FLOOR, color=GREEN, ls="--", lw=1)
    ax.axvline(ATR_CEIL, color=RED, ls="--", lw=1)
    ax.set_yscale("log")
    ax.set_xlabel("daily ATR(14) % - the typical move (opportunity)")
    ax.set_ylabel("spread % (cost, log)")
    ax.set_title("Option 4 - Spread (cost) vs ATR (opportunity): does the move justify the spread?")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    ax.grid(True, ls=":", alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "option-4-cost-vs-atr.png"), dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    df = load()
    opt1_sorted_bars(df)
    opt2_spread_vs_liquidity(df)
    opt3_cost_stack(df)
    opt4_cost_vs_atr(df)
    print(f"wrote 4 spread options from {len(df)} coins to {HERE}")
