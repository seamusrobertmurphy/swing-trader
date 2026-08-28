"""Run the workflow's analysis engines against the book we actually trade.

Three months of work went into the MACD, confluence and Fibonacci engines under
`outputs/1A-macd`, `outputs/1B-confluence` and `outputs/1C-fibonacci`, and into
the four-gate screen under `outputs/2A-market-screening`. Every figure they had
produced was drawn on Binance crypto bars for a strategy that was later killed,
so the pictures in the README are a record of the research rather than a view of
the live book. Nothing was wrong with the engines: they take an OHLCV frame and
do not care where it came from.

This module feeds them US equity bars instead: the funds that stand for each
slice of the market, and the fifty stocks the paper book holds. The engines are
imported and called unchanged, so a signal drawn here is computed by the same
code the notebook documents.

Two kinds of output:

  dashboard/analysis/*.html   the three interactive dashboards, symbol dropdown
                              and all, self-contained, opened directly or shown
                              inside the main dashboard page
  outputs/dashboard/analysis.json
                              the tabular results (divergence matrix, four-gate
                              screen, per-symbol signal state and the bars the
                              journal sheet draws) for the dashboard to render
                              in its own dark house style

    .venv/bin/python inputs/analysis_charts.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "inputs"))

OUT_JSON = REPO / "outputs" / "dashboard" / "analysis.json"
OUT_HTML = REPO / "dashboard" / "analysis"
ET = ZoneInfo("America/New_York")

# The funds that stand in for a slice of the market. Same list the Markets page
# uses, so the two pages cannot quietly describe different universes.
INDEXES = ["SPY", "QQQ", "IWM", "GLD", "TLT"]
SECTORS = {"XLK": "Technology", "XLF": "Financials", "XLE": "Energy",
           "XLV": "Health care", "XLI": "Industrials",
           "XLY": "Consumer, discretionary", "XLP": "Consumer, staples",
           "XLU": "Utilities", "XLB": "Materials", "XLRE": "Real estate",
           "XLC": "Communications"}

HISTORY_DAYS = 760          # about two years of sessions, enough for a 200-day mean
JOURNAL_BARS = 260          # what the per-symbol study sheet draws

# The four gates, in the equity numbers the dataset builder already uses
# (`inputs/build_dataset_equity.SCREEN_OVERRIDES`). Restated here rather than
# imported because importing that module drags in the whole panel build.
GATE_DOLLAR_VOLUME = 20_000_000     # 20-day median, US dollars a day
GATE_ATR_FLOOR_PCT = 1.0            # too quiet to pay for the spread
GATE_ATR_CEILING_PCT = 8.0          # too wild to size safely
GATE_SPREAD_CEILING_PCT = 0.20      # Corwin-Schultz estimate, see below
GATE_MIN_BARS = 260                 # a year of history before we will rank it


def _load(path: Path, name: str):
    """Import one of the lab modules by file path.

    They live under `outputs/`, which is not a package and never will be: it is
    the notebook's working area. Loading by path is what lets this run them
    unchanged rather than copying their arithmetic into a fourth place.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def engines() -> dict:
    lab = REPO / "outputs"
    return dict(
        macd=_load(lab / "1A-macd" / "macd.py", "lab_macd"),
        macd_fig=_load(lab / "1A-macd" / "build_macd_charts.py", "lab_macd_fig"),
        conf=_load(lab / "1B-confluence" / "confluence.py", "lab_conf"),
        conf_fig=_load(lab / "1B-confluence" / "build_confluence.py", "lab_conf_fig"),
        fib=_load(lab / "1C-fibonacci" / "fib.py", "lab_fib"),
        fib_fig=_load(lab / "1C-fibonacci" / "build_fib_charts.py", "lab_fib_fig"),
    )


def held() -> list[str]:
    """What the paper book holds right now. Empty on any failure: the analysis
    of the wider market must still draw when the broker is unreachable."""
    try:
        from alpaca_trade import clients
        return sorted(p.symbol for p in clients().get_all_positions())
    except Exception:  # noqa: BLE001
        return []


def frames(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Adjusted daily OHLCV in the shape the lab engines expect.

    They want a `time` column and lower-case OHLCV, which is what ccxt handed
    them. Reusing `dashboard_data._api_bars` means the adjustment setting and
    the bad-print guard are applied in one place for the whole dashboard.
    """
    from dashboard_data import _api_bars, _clip_bad_prints, _local_bars
    bars = _api_bars(symbols, days=HISTORY_DAYS)
    out: dict[str, pd.DataFrame] = {}
    for s in symbols:
        b = bars.get(s)
        if b is None:
            lb = _local_bars(s)
            if lb is None:
                continue
            b = lb[["open", "high", "low", "close", "volume"]]
        if len(b) < 60:
            continue
        b, _ = _clip_bad_prints(b)
        f = b.reset_index().rename(columns={"date": "time", "index": "time"})
        f["time"] = pd.to_datetime(f["time"])
        out[s] = f[["time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
    return out


# --------------------------------------------------------------------------- #
# The three interactive dashboards, rebuilt on equities
# --------------------------------------------------------------------------- #
def interactive(data: dict[str, pd.DataFrame], eng: dict) -> list[dict]:
    """Write the three lab dashboards as standalone pages beside dashboard.html.

    They stay separate files rather than being folded into the main page for one
    reason: each carries its own copy of the plotting library, and three copies
    would treble the size of a page that is refreshed every twenty minutes. The
    dashboard shows them in a frame, so the symbol dropdown still works.
    """
    OUT_HTML.mkdir(parents=True, exist_ok=True)
    specs = [
        ("macd", eng["macd_fig"], "MACD, guarded signals and divergences",
         "The crossover of a fast and a slow average of the price, with the "
         "crossings that are too small to trust filtered out, and the places "
         "where price and momentum disagree marked."),
        ("confluence", eng["conf_fig"], "Confluence: four readings at once",
         "MACD stance, moving-average stance, candle pattern and Fibonacci "
         "position, scored together. One indicator agreeing with itself is not "
         "evidence; four disagreeing is the useful case."),
        ("fibonacci", eng["fib_fig"], "Fibonacci retracement and extension",
         "The swing the price is currently working within, its retracement "
         "levels, and the golden pocket where a pullback most often ends."),
    ]
    made = []
    for key, mod, title, blurb in specs:
        try:
            fig = mod.build(data)
            fig.update_layout(template="plotly_dark",
                              paper_bgcolor="#161b22", plot_bgcolor="#0d1117",
                              font=dict(color="#e6edf3"),
                              margin=dict(l=50, r=20, t=70, b=40))
            p = OUT_HTML / f"{key}.html"
            fig.write_html(str(p), include_plotlyjs="directory", full_html=True,
                           config=dict(displaylogo=False))
            made.append(dict(key=key, title=title, blurb=blurb,
                             file=f"analysis/{key}.html",
                             mb=round(p.stat().st_size / 1e6, 1)))
            print(f"  wrote {p.relative_to(REPO)} ({p.stat().st_size / 1e6:.1f} MB)")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {key} failed: {type(e).__name__}: {e}")
    return made


# --------------------------------------------------------------------------- #
# Divergence matrix
# --------------------------------------------------------------------------- #
def divergence_matrix(data: dict[str, pd.DataFrame], eng: dict,
                      window: int = 120) -> list[dict]:
    """Where price and momentum disagree, across the whole universe at once.

    A divergence is price making a higher high while the momentum behind it
    makes a lower high, or the mirror of that at a low. It is the one MACD read
    that is about the market changing its mind rather than confirming what the
    price already did, which is why the research kept a matrix of it rather than
    looking at one chart at a time. `compute_signals` places each one at the
    first bar it could have been known, so nothing here is drawn with hindsight.

    One trap worth naming, because the first version of this fell into it. The
    engine's `strength` is not a running conviction level: it is zero on every
    bar and set only on the bar a guarded signal actually fires. Reading the
    last bar's value therefore returns zero for every name that did not trade a
    signal today, which is nearly all of them. What follows reports the most
    recent signal it did fire and how long ago, which is the question anyone
    looking at this table is really asking.
    """
    rows = []
    for sym, df in data.items():
        try:
            sig = eng["macd"].compute_signals(df["close"])
            conf = eng["conf"].compute_confluence(df)
        except Exception:  # noqa: BLE001
            continue
        tail = sig.tail(window).reset_index(drop=True)
        last = sig.iloc[-1]

        def bars_ago(flag: pd.Series):
            idx = np.flatnonzero(np.asarray(flag))
            return None if not len(idx) else int(len(flag) - 1 - idx[-1])

        fired = tail[tail["strength"] != 0]
        if len(fired):
            f = fired.iloc[-1]
            sig_side = "buy" if f["strength"] > 0 else "sell"
            sig_strength = round(float(f["strength"]), 1)
            sig_ago = int(len(tail) - 1 - fired.index[-1])
        else:
            sig_side, sig_strength, sig_ago = None, None, None

        score_col = next((c for c in ("score", "confluence", "total")
                          if c in conf.columns), None)
        score = (None if score_col is None
                 else round(float(conf[score_col].iloc[-1]), 2))

        bull, bear = tail["bull_div"], tail["bear_div"]
        rows.append(dict(
            symbol=sym,
            bull=int(bull.sum()), bear=int(bear.sum()),
            bull_bars_ago=bars_ago(bull), bear_bars_ago=bars_ago(bear),
            net=int(bull.sum()) - int(bear.sum()),
            signal=sig_side, strength=sig_strength, signal_bars_ago=sig_ago,
            score=score,
            stance="above" if last["macd"] > last["signal"] else "below",
            side="above zero" if last["macd"] > 0 else "below zero",
            guarded_buy=int(tail["guarded_buy"].sum()),
            guarded_sell=int(tail["guarded_sell"].sum()),
            converging=bool(last["converging"]),
            last=round(float(df["close"].iloc[-1]), 4)))
    # Most recently traded signal first, strongest of those at the top: the
    # order someone scanning this table for something to look at wants.
    rows.sort(key=lambda r: (r["signal_bars_ago"] if r["signal_bars_ago"]
                             is not None else 10_000,
                             -(abs(r["strength"]) if r["strength"] else 0)))
    return rows


# --------------------------------------------------------------------------- #
# The four-gate screen, on equities
# --------------------------------------------------------------------------- #
def screen(data: dict[str, pd.DataFrame]) -> list[dict]:
    """Would each name pass the screen the strategy is allowed to trade from?

    Four gates. Enough trading to get in and out (dollar volume), enough
    movement to be worth the fee but not so much it cannot be sized (the ATR
    band), a narrow enough gap between what buyers offer and sellers ask, and
    enough history to rank it at all.

    The spread is the awkward one. Daily bars carry no top-of-book quote, so
    this uses the Corwin-Schultz estimator, which infers the spread from how
    much consecutive daily ranges overlap. It is an estimate, not the real
    spread, and the number is labelled as such wherever it is shown.
    """
    from build_dataset_1h import corwin_schultz_spread_pct
    rows = []
    for sym, df in data.items():
        if len(df) < 30:
            continue
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
        atr_pct = float((tr.rolling(14).mean() / df["close"]).iloc[-1] * 100)
        dollar_vol = float((df["close"] * df["volume"]).rolling(20).median().iloc[-1])
        spread = float(corwin_schultz_spread_pct(df, 20).iloc[-1])
        g_liq = dollar_vol >= GATE_DOLLAR_VOLUME
        g_atr = GATE_ATR_FLOOR_PCT <= atr_pct <= GATE_ATR_CEILING_PCT
        g_sp = spread <= GATE_SPREAD_CEILING_PCT if np.isfinite(spread) else False
        g_hist = len(df) >= GATE_MIN_BARS
        rows.append(dict(
            symbol=sym, atr=round(atr_pct, 3),
            vol_m=round(dollar_vol / 1e6, 1),
            spread=None if not np.isfinite(spread) else round(spread, 4),
            bars=int(len(df)),
            g_liq=bool(g_liq), g_atr=bool(g_atr), g_sp=bool(g_sp),
            g_hist=bool(g_hist),
            passed=bool(g_liq and g_atr and g_sp and g_hist),
            # what one round trip costs at this spread plus the measured fee,
            # against what one day's move is worth: the fee wall, in one number
            cost_vs_move=None if not (np.isfinite(spread) and atr_pct > 0)
                         else round((spread + 0.10) / atr_pct, 3)))
    rows.sort(key=lambda r: (not r["passed"], -(r["vol_m"] or 0)))
    return rows


def screen_note(rows: list[dict]) -> dict:
    """How much work each gate is actually doing.

    A gate that passes everything is not protecting anything, and printing it
    beside three that bite would flatter the screen. On daily US equity bars the
    Corwin-Schultz estimate collapses to exactly zero for the most heavily
    traded names, which means "too tight for this method to resolve", not
    "free". This counts that rather than leaving the reader to assume.
    """
    n = len(rows) or 1
    return dict(
        n=len(rows),
        passed=sum(r["passed"] for r in rows),
        blocked_by_liquidity=sum(not r["g_liq"] for r in rows),
        blocked_by_atr=sum(not r["g_atr"] for r in rows),
        blocked_by_spread=sum(not r["g_sp"] for r in rows),
        blocked_by_history=sum(not r["g_hist"] for r in rows),
        spread_measurable=sum(1 for r in rows if (r["spread"] or 0) > 0),
        spread_unresolved=sum(1 for r in rows if not (r["spread"] or 0) > 0),
        spread_binding=sum(not r["g_sp"] for r in rows) > 0)


# --------------------------------------------------------------------------- #
# The signal journal study sheet
# --------------------------------------------------------------------------- #
def journal(data: dict[str, pd.DataFrame], eng: dict, symbols: list[str]) -> dict:
    """Per-bar layers for the study sheet: candles, the MACD underneath, the
    confluence score, the Fibonacci levels in force, and every place a guarded
    signal or a divergence fired. This is the sheet the workflow used to grade a
    signal after the fact rather than argue about it from memory."""
    out = {}
    for sym in symbols:
        df = data.get(sym)
        if df is None or len(df) < 80:
            continue
        try:
            sig = eng["macd"].compute_signals(df["close"])
            conf = eng["conf"].compute_confluence(df)
        except Exception as e:  # noqa: BLE001
            print(f"  ! journal {sym}: {type(e).__name__}: {e}")
            continue
        score_col = next((c for c in ("score", "confluence", "total")
                          if c in conf.columns), None)
        n = len(df)
        f = pd.DataFrame(dict(
            date=df["time"].dt.strftime("%Y-%m-%d"),
            open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            volume=df["volume"],
            ema20=df["close"].ewm(span=20, adjust=False).mean(),
            ema50=df["close"].ewm(span=50, adjust=False).mean(),
            macd=sig["macd"].to_numpy()[:n], signal=sig["signal"].to_numpy()[:n],
            hist=sig["hist"].to_numpy()[:n],
            strength=sig["strength"].to_numpy()[:n],
            buy=sig["guarded_buy"].to_numpy()[:n],
            sell=sig["guarded_sell"].to_numpy()[:n],
            bull=sig["bull_div"].to_numpy()[:n],
            bear=sig["bear_div"].to_numpy()[:n],
            score=(conf[score_col].to_numpy()[:n] if score_col
                   else np.full(n, np.nan)),
        )).tail(JOURNAL_BARS).round(4)
        levels = {}
        try:
            sw = eng["fib"].detect_swing(df["high"], df["low"])
            levels = {str(k): round(float(v), 4)
                      for k, v in eng["fib"].retracement_levels(sw).items()}
            gp = eng["fib"].golden_pocket(sw)
            levels["golden_low"] = round(float(min(gp)), 4)
            levels["golden_high"] = round(float(max(gp)), 4)
        except Exception:  # noqa: BLE001
            levels = {}
        out[sym] = dict(
            symbol=sym,
            score_column=score_col,
            fib=levels,
            bars=f.where(pd.notna(f), None).to_dict("records"))
    return out


def build() -> dict:
    eng = engines()
    book = held()
    universe = list(dict.fromkeys(INDEXES + list(SECTORS) + book))
    print(f"analysis universe: {len(universe)} symbols "
          f"({len(INDEXES)} indexes, {len(SECTORS)} sectors, {len(book)} held)")
    data = frames(universe)
    print(f"  bars for {len(data)} of them")

    # The study sheet is heavy per symbol, so it is drawn for the market as a
    # whole and for the three holdings currently moving the account most.
    movers = sorted(
        (s for s in book if s in data),
        key=lambda s: -abs(float(data[s]["close"].iloc[-1] /
                                 data[s]["close"].iloc[-22] - 1)))[:3]
    sheet_for = [s for s in ["SPY", "QQQ", "IWM"] if s in data] + movers

    return dict(
        meta=dict(generated_at=datetime.now(ET).isoformat(),
                  universe=len(data), held=len(book),
                  history_days=HISTORY_DAYS,
                  gates=dict(dollar_volume=GATE_DOLLAR_VOLUME,
                             atr_floor=GATE_ATR_FLOOR_PCT,
                             atr_ceiling=GATE_ATR_CEILING_PCT,
                             spread_ceiling=GATE_SPREAD_CEILING_PCT,
                             min_bars=GATE_MIN_BARS)),
        sectors=SECTORS, indexes=INDEXES, book=book,
        pages=interactive(data, eng),
        divergence=divergence_matrix(data, eng),
        screen=(_scr := screen(data)),
        screen_note=screen_note(_scr),
        journal=journal(data, eng, sheet_for),
        journal_for=sheet_for,
    )


def main():
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    d = build()
    OUT_JSON.write_text(json.dumps(d, indent=1, default=str), encoding="utf-8")
    print(f"wrote {OUT_JSON} ({OUT_JSON.stat().st_size / 1024:.0f} KB)")
    print(f"  interactive pages {len(d['pages'])}  divergence rows "
          f"{len(d['divergence'])}  screened {len(d['screen'])} "
          f"({sum(r['passed'] for r in d['screen'])} pass)  "
          f"journal sheets {len(d['journal'])}")


if __name__ == "__main__":
    main()
