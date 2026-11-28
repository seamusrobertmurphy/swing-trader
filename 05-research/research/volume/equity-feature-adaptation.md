# Equity feature adaptation

A translation of the indicator design in `research/rl_reference/indicators.py` to a long-only US-equity swing context. The source builds a feature pipeline for an RL agent on EURUSD hourly bars. The design choice worth preserving is what the source does *not* feed the agent: raw price levels, raw moving averages, anything with a dollar denomination. The agent sees only quantities that are invariant to where the price happens to be that day.

This note keeps the design principle and rewrites the feature list around the trader-swing brief: US equities, daily bars at the finest, multi-month horizon, benchmarked to SPY, with the cross-sectional cross-checks Principle 11 requires.

## The design principle

A feature is admissible if its statistical distribution is roughly stable across regimes and across names. Raw close price is not — a $50 stock and a $500 stock occupy different parts of the same axis without carrying different information. RSI is — it lives in [0, 100] regardless of the underlying. The source pipeline reflects this: it computes raw MAs internally for the env, then exposes only slopes, distances from price, and spreads between MAs to the agent.

The trader-swing book applies the same filter and extends it. Equity research adds a fundamentals layer the forex source did not have. Those features have the same admissibility property when expressed as cross-sectional ranks or z-scores against a peer group, or as differentials against a benchmark like the 10-year Treasury.

## Technical features, adapted

The eight features in `indicators.py` map onto US-equity daily bars with minor adjustments. The pip-denominated quantities become percentage-denominated; the hourly cadence becomes daily.

The RSI and ATR carry over unchanged in shape. RSI(14) on daily closes is standard. ATR(14) is computed in dollar terms, then normalised by the prior close to give a percentage volatility figure that is cross-sectionally comparable.

Moving averages: SMA(20) and SMA(50) are the source defaults. For a multi-month swing horizon the relevant pair is SMA(50) and SMA(200). The slopes are computed as the day-over-day change in the MA, scaled by the MA level to give a per-day percentage drift. The distance of close from the MA is `(close - ma) / ma`, a unitless percentage. The MA spread, `ma_50 - ma_200`, becomes `(ma_50 - ma_200) / ma_200`, again unitless. The spread slope is the day-over-day change in that ratio.

That gives a technical-feature row, per name per day:

```
rsi_14          : RSI on daily Close, length 14
atr_pct_14      : ATR(14) / Close, in percent
ma_50_slope_pct : (ma_50_t - ma_50_{t-1}) / ma_50_{t-1}
ma_200_slope_pct: (ma_200_t - ma_200_{t-1}) / ma_200_{t-1}
close_ma50_pct  : (Close - ma_50) / ma_50
close_ma200_pct : (Close - ma_200) / ma_200
ma_spread_pct   : (ma_50 - ma_200) / ma_200
ma_spread_slope : day-over-day change in ma_spread_pct
```

All eight are scale-invariant. None reference cost basis. None reference a forex pip or a lot size.

## Fundamental features, layered in

The source has no fundamentals. The brief requires them: Principle 11 prohibits single-method valuations and forces cross-checks across at least two of peer-group multiples, owner-earnings yield against the 10-year, and replacement-cost or sum-of-the-parts. The features below operationalise those cross-checks as relative quantities, consistent with the design principle.

Peer-group multiples are computed as z-scores within a GICS sub-industry. The features are `ev_ebitda_z` and `p_fcf_z`, where the z-score is `(name_value - subindustry_median) / subindustry_mad`. The median and MAD are computed over the rolling six-month window of available filings, not over the current snapshot, to avoid same-day bias.

Owner-earnings yield versus the 10-year Treasury is `oey_minus_10y = owner_earnings_yield - ust10y`. Owner earnings is Buffett's construction: net income plus depreciation and amortisation minus maintenance capex, divided by enterprise value. The 10-year yield is a single national series. The differential is unitless and bounded in practice.

Quality is captured as a z-score on return on invested capital, again within sub-industry, again on a trailing window: `roic_z = (name_roic - subindustry_median_roic) / subindustry_mad_roic`.

Size is a single feature, the log of market capitalisation, demeaned against the universe. Size is a tilt the Friday review monitors per the brief's twelve-principle Principle 12; the feature here is the raw input that estimate consumes.

That gives four fundamentals features, per name per day (the day part is mostly stable; fundamentals refresh on filings):

```
ev_ebitda_z     : EV/EBITDA z-score within GICS sub-industry, trailing 6M window
p_fcf_z         : P/FCF z-score within GICS sub-industry, trailing 6M window
oey_minus_10y   : owner-earnings yield minus current 10-year Treasury yield
roic_z          : ROIC z-score within GICS sub-industry, trailing 6M window
size_log_demean : log(market cap) minus universe mean log(market cap)
```

The first three are the explicit cross-checks Principle 11 names; the fourth supports the quality dimension that turns up in factor decomposition; the fifth feeds the size tilt the Friday review tracks.

## Market-context features

The brief mentions the VIX explicitly as a noise filter (Principle 6: SPY-level moves within ±VIX/√252 carry no thesis weight). The corresponding market-context features are:

```
vix_level       : raw VIX close
spy_noise_band  : VIX / sqrt(252), the per-day implied SPY move in percent
spy_return_1d   : SPY's 1-day total return, in percent
beta_60d        : 60-day rolling beta of the name to SPY
```

`beta_60d` informs the correlation budget (Principle 7). Single-name moves are compared against `1.5 * spy_noise_band` when no name-level IV is available; with IV available, that scalar is replaced.

## What is not a feature

A handful of quantities are deliberately excluded.

Raw close price. Raw market cap. Raw EBITDA. Raw FCF. Raw EPS. All of these are dollar-denominated absolutes with distributions that are not stable across names.

Cost basis, gain/loss, days-held. The brief's anchoring prohibition (Principle 5) applies to any feature that references entry. The source RL env violated this in its reward shaping; this feature list does not propagate the mistake into research.

Headlines, sentiment scores, social-media indicators. Out of scope for the current research skill; the brief's research workflow uses Perplexity for catalyst surfacing, which is qualitative input, not a feature.

## Where this lives in the runtime

This note is a research artifact. It does not modify any routine, skill, or memory file. If the Friday review decides to operationalise it, the implementation is a helper module in `scripts/` or a new `lib/` subtree, called by `skills/research.md`. The features feed the pre-market thesis-writing step, not a learned model.

The features above are the *inputs* the brief's hard rules already require. The contribution of this note is to write the list down explicitly, in the relative-feature shape that `indicators.py` taught, so the research skill has something concrete to compute when the Friday review picks it up.

## Trail

Produced 2026-05-11, consequent to the import documented in `rl-applicability-assessment.md`. References `research/synthesis-quant-methods.md` Principles 1, 5, 6, 7, 11, 12, and the technical-feature pattern from `research/rl_reference/indicators.py`.
