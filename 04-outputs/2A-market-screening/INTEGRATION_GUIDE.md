# Chapter Two screen: paste-in integration

These cells fold the recent script-side refinements back into the canonical
`02-trader-controls.ipynb`. The notebook stays the source of truth; paste these where
noted and run. They are matched to your notebook's current screen-table schema
(`symbol, vol_m, atr, spread, candles, g_liq, g_atr, g_sp, g_hist, passed, reason,
stop, pos`) and assume the screen result is in a variable named `screen` and the figure
functions are `screen_scatter` and `spread_bars`, as in your notebook. Adjust the names
if yours differ.

## 1. Save the screen outputs (module-prefixed, into the format folders)

Today the notebook writes `Candidates_*.csv` to the `outputs/` root and only `show()`s
the figures. Paste this after the screen and the figures are built, to route every
artifact into `CSV/`, `PNG/`, and `HTML/` with the `2A-` prefix:

```python
from datetime import datetime, timezone
stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
for sub in ("CSV", "PNG", "HTML"):
    (OUTPUTS / sub).mkdir(parents=True, exist_ok=True)

# the sample table (the coins that passed the screen), renamed from "candidates"
screen.to_csv(OUTPUTS / "CSV" / f"2A-sample_{stamp}.csv", index=False)

# four-gate scatter: interactive HTML always; PNG if kaleido/Chrome is available
fig = screen_scatter(screen)
fig.write_html(OUTPUTS / "HTML" / f"2A-screen_{stamp}.html", include_plotlyjs="cdn")
try:
    fig.write_image(OUTPUTS / "PNG" / f"2A-screen_{stamp}.png", scale=2)
except Exception as e:
    print("PNG via kaleido unavailable:", str(e)[:60],
          "- run outputs/2A-market-screening/build_screen_charts.py for a matplotlib PNG")

# spread gate bars
sfig = spread_bars(screen)
sfig.write_html(OUTPUTS / "HTML" / f"2A-spread_{stamp}.html", include_plotlyjs="cdn")
try:
    sfig.write_image(OUTPUTS / "PNG" / f"2A-spread_{stamp}.png", scale=2)
except Exception:
    pass
```

If `write_image` fails in your environment too (it needs kaleido plus Chrome), the
static PNG is produced reliably by `outputs/2A-market-screening/build_screen_charts.py`,
which reads the saved `2A-sample_*.csv` and renders with matplotlib. That is what made
the current `outputs/PNG/2A-screen_20260620.png`.

## 2. candidates becomes sample

The coins that pass the screen are the sample, not candidates (candidates wrongly
implies a wider pool still to choose from). Two edits in the notebook:

- In `screen_scatter`, change the passed group's legend label from `"candidate"` to
  `"sample"` (the line `for d, name, col in [(failed, "rejected", ...), (passed,
  "candidate", ...)]`).
- The saved table is now `2A-sample_*.csv` (handled by the cell above), replacing
  `Candidates_*.csv`. Update the artifact-listing cell at the end of the notebook to
  glob `2A-sample_*.csv` instead of `Candidates_*.csv`.

## 3. universe becomes market reference / market

Plain terms: the full Binance/ccxt pool you screen is the market reference (or just
the market); the coins it selects are the sample. Optional renames where they read
clearly:

- `build_universe()` to `build_market()`, the `universe` variable to `market`.
- Markdown and titles that say "universe" to "market reference" or "market".

These are wording only; the logic is unchanged.

## 4. The README image

The static image now exists at `outputs/PNG/2A-screen_20260620.png`. The line to drop
into the README (note: no `trader-py/` prefix, since the README sits inside `trader-py`):

```markdown
![Four-gate market screen](outputs/PNG/2A-screen_20260620.png)
```

Caption note for accuracy: green dots are the sample that clears all four gates; some
coins sit inside the shaded ATR band yet are still red, because the scatter shows only
two of the four gates and they failed on history, spread, or liquidity.

---

Separately: the standalone `screen.py` in this folder still uses the older long column
names (`atr_pct`, `quote_volume_24h_usdt`, `pass`). It is a workbench copy and is now
behind your notebook's compact schema; reconcile it when convenient, or treat the
notebook as canonical and regenerate `screen.py` from it.
