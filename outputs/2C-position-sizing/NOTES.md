# 2C - Position sizing

Chapter Two, Controls. Sizes each position so the dollar risk is roughly constant
across coins: a calmer coin earns a larger clip, a livelier one a smaller clip,
capped at a fraction of the account and floored at the venue minimum. At a small
account this favours a few larger positions over many tiny ones that waste edge on
fees.

## What it computes

    stop_pct    = stop_atr_mult * daily ATR%
    risk_budget = account * risk_per_trade_pct / 100
    raw_size    = risk_budget / (stop_pct / 100)
    position    = clamp(raw_size, min_notional, account * max_position_pct / 100)

Input is a coin's latest ATR% from [2B](../2B-atr-band/NOTES.md), for the sample
that cleared [2A](../2A-universe-screen/NOTES.md).

## Functions

`position_plan`, plus `size_table` here to build the table over several coins.

## Outputs

- the sizing table: `outputs/CSV/2C-sizing_YYYYMMDD.csv`
- the sizing chart: `outputs/PNG/2C-sizing_YYYYMMDD.png`

## Run in isolation

    python sizing.py

## Wire back into the notebook

Paste after the sizing cell builds `sized` and its bar chart `fig`:

```python
stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
(OUTPUTS / "CSV").mkdir(parents=True, exist_ok=True)
(OUTPUTS / "PNG").mkdir(parents=True, exist_ok=True)
sized.to_csv(OUTPUTS / "CSV" / f"2C-sizing_{stamp}.csv", index=False)
try:
    fig.write_image(OUTPUTS / "PNG" / f"2C-sizing_{stamp}.png", scale=2)   # needs kaleido + Chrome
except Exception:
    fig.write_html(OUTPUTS / "HTML" / f"2C-sizing_{stamp}.html", include_plotlyjs="cdn")
```
