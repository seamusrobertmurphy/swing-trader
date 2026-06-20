# 2A - Universe selection, the four-gate screen

Chapter Two, Controls. Scopes the tradable universe before the model sees a coin:
scan wide, hold few.

## What it computes

Four gates per coin, all recorded whether the coin passes or fails:

- liquidity: 24h quote volume in USDT clears a floor (the cheap, hard gate, checked first)
- atr_band: the latest ATR(14)% sits inside the tradable band (lively, not detonating)
- spread: top-of-book spread under the ceiling, so the fee stays the binding cost
- history: enough candles to have lived through several regimes

## Functions

`screen_coin`, `run_screen`, `screen_scatter` (and `spread_bars` in the notebook).
`compute_atr_pct` is duplicated here for standalone use; the canonical band view is
[2B-atr-band](../2B-atr-band/NOTES.md).

## Outputs

- the dated sample table: `outputs/CSV/2A-sample_YYYYMMDD.csv`
- the screen scatter: `outputs/PNG/2A-screen_YYYYMMDD.png`

## Run in isolation

    python screen.py

Uses live Binance data through ccxt when reachable, otherwise deterministic synthetic
data so it runs offline. The script writes the sample CSV itself.

## Wire back into the notebook

The notebook is canonical; paste this where the screen is built (it currently writes
to `outputs/` root, then files are sorted by hand). This routes both artifacts into
the format folders with the 2A prefix:

```python
stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
(OUTPUTS / "CSV").mkdir(parents=True, exist_ok=True)
(OUTPUTS / "PNG").mkdir(parents=True, exist_ok=True)
screen.to_csv(OUTPUTS / "CSV" / f"2A-sample_{stamp}.csv", index=False)

fig = screen_scatter(screen)
try:
    fig.write_image(OUTPUTS / "PNG" / f"2A-screen_{stamp}.png", scale=2)   # needs kaleido + Chrome
except Exception:
    fig.write_html(OUTPUTS / "HTML" / f"2A-screen_{stamp}.html", include_plotlyjs="cdn")
```
