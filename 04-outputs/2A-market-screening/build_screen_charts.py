"""
Build the four-gate market-screen visuals from a saved sample table.

Reads the most recent outputs/CSV/2A-sample_*.csv (the screen output: one row per
coin with its four gate results), and writes two charts in two formats each:

  liquidity vs volatility scatter -> outputs/PNG/2A-screen_DATE.png   (static)
                                     outputs/HTML/2A-screen_DATE.html (interactive)
  spread gate bars                -> outputs/PNG/2A-spread_DATE.png
                                     outputs/HTML/2A-spread_DATE.html

The interactive HTML uses plotly; the static PNG uses matplotlib (no Chrome /
kaleido needed), the same split the indicator labs use. Colours and thresholds
mirror the controls notebook.

Run:  python build_screen_charts.py
"""

import glob
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUTS = os.path.abspath(os.path.join(HERE, ".."))
CSV_DIR = os.path.join(OUTPUTS, "CSV")
PNG_DIR = os.path.join(OUTPUTS, "PNG")
HTML_DIR = os.path.join(OUTPUTS, "HTML")

# Thresholds, mirrored from the controls notebook CONFIG.
ATR_FLOOR = 2.5
ATR_CEIL = 12.0
LIQ_FLOOR_M = 30.0      # 24h quote volume floor, in USD millions ($30M)
SPREAD_CEIL = 0.05      # spread ceiling, percent

GREEN = "#2E8B57"
RED = "#B22222"
GREY = "#888888"
NAVY = "#0B3D66"


def latest_sample_csv():
    files = sorted(glob.glob(os.path.join(CSV_DIR, "2A-sample_*.csv")))
    if not files:
        raise FileNotFoundError("no outputs/CSV/2A-sample_*.csv found")
    return files[-1]


def date_tag(path):
    m = re.search(r"(\d{8})", os.path.basename(path))
    return m.group(1) if m else "latest"


def load(path):
    df = pd.read_csv(path)
    for c in ("g_liq", "g_atr", "g_sp", "g_hist", "passed"):
        if c in df.columns and df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip().str.lower().eq("true")
    return df


# --------------------------------------------------------------------------- #
# Static PNG (matplotlib)
# --------------------------------------------------------------------------- #
def scatter_png(df, out):
    d = df.dropna(subset=["atr", "vol_m"]).copy()
    passed = d[d["passed"]]
    failed = d[~d["passed"]]
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    ax.axvspan(ATR_FLOOR, ATR_CEIL, color=GREEN, alpha=0.07, lw=0)
    ax.axvline(ATR_FLOOR, color=GREEN, ls="--", lw=1)
    ax.axvline(ATR_CEIL, color=RED, ls="--", lw=1)
    ax.axhline(LIQ_FLOOR_M, color=GREY, ls=":", lw=1)
    ax.annotate("liquidity floor", xy=(0.99, LIQ_FLOOR_M),
                xycoords=ax.get_yaxis_transform(), ha="right", va="bottom",
                color=GREY, fontsize=8)
    for grp, name, col in [(failed, "rejected", RED), (passed, "sample", GREEN)]:
        if len(grp):
            ax.scatter(grp["atr"], grp["vol_m"], s=70, c=col, alpha=0.8,
                       edgecolors="white", linewidths=1, label=name, zorder=3)
            for _, r in grp.iterrows():
                ax.annotate(r["symbol"], (r["atr"], r["vol_m"]),
                            textcoords="offset points", xytext=(0, 7),
                            ha="center", fontsize=7.5, color="#333333")
    ax.set_yscale("log")
    ax.set_xlabel("daily ATR(14) %")
    ax.set_ylabel("24h quote volume (USD millions, log)")
    ax.set_title("Selection screen: liquidity vs volatility "
                 "(sample inside the band, above the floor)", fontsize=11)
    ax.legend(loc="lower right", framealpha=0.9)
    ax.grid(True, which="both", ls=":", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def spread_png(df, out):
    d = df.dropna(subset=["spread"]).sort_values("spread").copy()
    colors = [GREEN if v <= SPREAD_CEIL else RED for v in d["spread"]]
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    ax.bar(d["symbol"], d["spread"], color=colors)
    ax.axhline(SPREAD_CEIL, color=GREY, ls="--", lw=1)
    ax.annotate(f"ceiling {SPREAD_CEIL}%", xy=(0.99, SPREAD_CEIL),
                xycoords=ax.get_yaxis_transform(), ha="right", va="bottom",
                color=GREY, fontsize=8)
    ax.set_ylabel("spread %")
    ax.set_title("Spread gate: top-of-book spread vs ceiling", fontsize=11)
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    ax.grid(True, axis="y", ls=":", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Interactive HTML (plotly, optional)
# --------------------------------------------------------------------------- #
def scatter_html(df, out):
    import plotly.graph_objects as go
    d = df.dropna(subset=["atr", "vol_m"]).copy()
    passed = d[d["passed"]]
    failed = d[~d["passed"]]
    fig = go.Figure()
    for grp, name, col in [(failed, "rejected", RED), (passed, "sample", GREEN)]:
        if len(grp):
            fig.add_trace(go.Scatter(
                x=grp["atr"], y=grp["vol_m"], mode="markers+text",
                text=grp["symbol"], textposition="top center",
                textfont=dict(size=9), name=name,
                marker=dict(size=11, color=col, opacity=0.8,
                            line=dict(width=1, color="white"))))
    fig.add_vrect(x0=ATR_FLOOR, x1=ATR_CEIL, fillcolor=GREEN, opacity=0.07, line_width=0)
    fig.add_vline(x=ATR_FLOOR, line=dict(color=GREEN, dash="dash"))
    fig.add_vline(x=ATR_CEIL, line=dict(color=RED, dash="dash"))
    fig.add_hline(y=LIQ_FLOOR_M, line=dict(color=GREY, dash="dot"),
                  annotation_text="liquidity floor", annotation_position="bottom right")
    fig.update_layout(
        title="Selection screen: liquidity vs volatility (sample inside the band, above the floor)",
        template="plotly_white", height=460, yaxis_type="log",
        xaxis_title="daily ATR(14) %", yaxis_title="24h quote volume (USD millions, log)",
        margin=dict(l=60, r=20, t=50, b=40))
    fig.write_html(out, include_plotlyjs=True, full_html=True)


def spread_html(df, out):
    import plotly.graph_objects as go
    d = df.dropna(subset=["spread"]).sort_values("spread").copy()
    colors = [GREEN if v <= SPREAD_CEIL else RED for v in d["spread"]]
    fig = go.Figure(go.Bar(x=d["symbol"], y=d["spread"], marker_color=colors))
    fig.add_hline(y=SPREAD_CEIL, line=dict(color=GREY, dash="dash"),
                  annotation_text=f"spread ceiling {SPREAD_CEIL}%")
    fig.update_layout(title="Spread gate: top-of-book spread vs ceiling",
                      template="plotly_white", height=360, yaxis_title="spread %",
                      margin=dict(l=50, r=20, t=50, b=40))
    fig.write_html(out, include_plotlyjs=True, full_html=True)


def main():
    csv = latest_sample_csv()
    tag = date_tag(csv)
    df = load(csv)
    os.makedirs(PNG_DIR, exist_ok=True)
    os.makedirs(HTML_DIR, exist_ok=True)
    print(f"source: {os.path.relpath(csv, OUTPUTS)}  ({len(df)} rows, "
          f"{int(df['passed'].sum())} passed)")

    scatter_png(df, os.path.join(PNG_DIR, f"2A-screen_{tag}.png"))
    spread_png(df, os.path.join(PNG_DIR, f"2A-spread_{tag}.png"))
    print(f"wrote PNG/2A-screen_{tag}.png and PNG/2A-spread_{tag}.png")

    try:
        scatter_html(df, os.path.join(HTML_DIR, f"2A-screen_{tag}.html"))
        spread_html(df, os.path.join(HTML_DIR, f"2A-spread_{tag}.html"))
        print(f"wrote HTML/2A-screen_{tag}.html and HTML/2A-spread_{tag}.html")
    except ImportError:
        print("plotly not installed: skipped HTML (PNG still written). "
              "pip install plotly to enable.")


if __name__ == "__main__":
    main()
