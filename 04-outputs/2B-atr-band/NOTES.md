# 2B - ATR volatility band

Chapter Two, Controls. One metric doing two jobs: a selection filter that admits or
rejects a coin, and a live guardrail that keeps the model out of a coin that has
drifted out of the tradable band.

## What it computes

ATR(14) as a percent of price. The floor sits above the net-edge requirement (below
it a coin cannot reach the take-profit in the window); the ceiling sits below where a
coin gaps through its stops (above it the exits are unreliable).

## Functions

`compute_atr_pct`, `atr_band_figure`, plus `in_band` here for the gate check. This is
the canonical ATR calc; [2A](../2A-universe-screen/NOTES.md) keeps a local copy for
its screen and [2C](../2C-position-sizing/NOTES.md) sizes off the same atr_pct.

## Outputs

- the ATR band chart per coin: `outputs/PNG/2B-atr-band_SYMBOL.png`

Also feeds 2A (the band gate) and 2C (sizing).

## Run in isolation

    python atr_band.py

Live through ccxt when reachable, else synthetic, offline-safe.

## Wire back into the notebook

```python
sym = universe[0]
tag = sym.replace("/USDT", "")
fig = atr_band_figure(sym)
(OUTPUTS / "PNG").mkdir(parents=True, exist_ok=True)
try:
    fig.write_image(OUTPUTS / "PNG" / f"2B-atr-band_{tag}.png", scale=2)   # needs kaleido + Chrome
except Exception:
    fig.write_html(OUTPUTS / "HTML" / f"2B-atr-band_{tag}.html", include_plotlyjs="cdn")
```
