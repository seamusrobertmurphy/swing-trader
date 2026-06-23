# Task Request: Time-Aware Splitting and Survivorship-Bias Controls

**Scope:** Data-processing and methodology stage of the OHLCV training notebook
**Dataset:** Hourly OHLCV, ~400 Binance crypto pairs, 2017–present
**Objective of the change:** Replace random/stratified splitting with a chronological walk-forward design, and document the survivorship and listing-bias controls, with rationale, in the methodology section.

---

## 1. Objective and rationale (methodology cell)

Insert a markdown cell at the top of the splitting section stating the objective in plain terms: estimate out-of-sample performance under regime drift, not interpolation within a known distribution.

The data-generating process drifts across time. The 2017–2018 ICO mania, the 2021 bull run, the 2022 deleveraging, and the current regime are different processes. A split that interleaves test bars among training bars borrows the future to predict the past and yields an error estimate that will not survive live trading.

State explicitly that stratified sampling is rejected. Stratifying on variance forces similar proportions across splits by drawing observations regardless of position in time, which destroys the temporal ordering that is the whole object of interest. It answers "can the model interpolate within a known distribution"; the question that matters is "can it extrapolate forward into an unknown regime." Only a forward-chained split measures that.

## 2. Walk-forward splitter

Replace any random or stratified split with an expanding-window (or rolling-window) walk-forward scheme.

- Boundaries are calendar dates shared across all coins.
- Train on the earliest block, validate on the next, test on the most recent holdout; slide forward and repeat to produce several out-of-sample folds spanning different regimes.
- Prefer a custom splitter over `TimeSeriesSplit` given the 400-coin panel; the baseline is fine conceptually but will not handle the panel structure or the purge/embargo below.
- Nothing past the training cutoff may leak backward into features, scaling, or normalisation. Fit all transforms on train only and apply forward.

## 3. Purge and embargo at every boundary

At each fold cut, drop a gap equal to the longest of the feature lookback window and the label horizon, on both sides of the boundary.

Features built on lookback windows and labels built on forward returns (e.g. next-24-hour return) cause bars near the seam to share information across the split. The gap removes that overlap. This is López de Prado's purging-and-embargo; with overlapping label windows in crypto it matters more than is commonly assumed. Record the chosen gap and the windows that determined it.

## 4. Split on time, not on coins

All coins share the same calendar boundaries. A given coin appears in both train and test, but only its earlier bars train and its later bars test.

Do not hold out whole coins. Whole-coin holdout answers a different question ("generalise to a coin never traded"); only add it as a separate, explicitly labelled experiment if that objective is actually wanted.

## 5. Per-fold reporting for regime stability

Report the chosen metric per fold, not pooled. This exposes whether performance is stable or regime-dependent, which a single averaged number hides. Weight or annotate folds by coin count (see §7) so thin early folds are not read as equal evidence to broad later ones.

---

## 6. Survivorship bias and the listing problem

### What the bias is

Survivorship bias is building a sample from coins that exist today and lasted long enough to be worth studying. Every coin that delisted, was rugged, or quietly died is absent. The survivors are by definition the ones that did not fail, so a model trained on them learns the statistics of survivors and overstates how a strategy would have performed when traded in real time without knowing which coins would last. In crypto this is severe: Binance lists hundreds of pairs and removes them constantly, and the graveyard is larger than the living set.

The listing problem is the structural side of the same fact. The panel is unbalanced because coins enter at different dates and some exit. A 2017 window holds a dozen coins; a 2023 window holds hundreds. Ignored, the composition shifts silently across time, and changes in *which coins exist* get mistaken for changes in market behaviour.

### Controls to implement and document

**Include the dead coins.** The single most important step and the most often skipped. Historical OHLCV for delisted pairs must be present, not just currently trading ones. Binance's public API serves only active symbols, so any dataset pulled today is survivorship-contaminated by construction. Source archived bars recorded while those coins were live, or historical dumps that preserve delisted symbols. If the dead coins cannot be recovered, state the limitation plainly and treat every performance number as an upper bound.

**Set a minimum-history threshold for a reason, not a round number.** The floor is driven by the feature and label windows. A coin needs enough bars to compute its longest-lookback feature, form a valid label, and contribute more than noise to any fold it enters. Set the floor above (longest feature window + label horizon + buffer), with a further requirement that the coin be present for some minimum fraction of any fold it joins. The exact value is a judgment call; the principle is that it must exceed what the pipeline needs to produce one clean labelled observation, with margin. Record the value and the windows that set it.

**Define and document the point-of-entry rule.** When a coin lists mid-window, choose one honest option and state it. Either the coin enters at its first valid bar (realistic, mirrors when trading would actually begin) or it must span the full fold to be included (cleaner panel, but discards information and biases toward longer-lived coins, reintroducing a flavour of survivorship). Do not let coins drift in and out invisibly.

**Handle early-window degeneracy.** The 2017–2018 folds may contain only BTC, ETH, and a few majors. A cross-sectional model trained there learns from almost nothing and is not comparable to later folds. Options: start usable history later (2019–2020) where breadth is adequate; weight folds by coin count when summarising; or report early folds separately and flag them as thin. Do not treat a 10-coin fold and a 300-coin fold as equal evidence.

**Track composition explicitly.** Produce a table or plot of coin count per fold and the entry/exit date of every symbol. This is the audit trail. When a metric jumps between folds, the first question is whether the model changed behaviour or the population did, and that cannot be answered without this.

**Beware look-ahead in the universe definition itself.** If the "400 coins" are selected by any criterion measured over the full history (top 400 by lifetime volume, coins that reached some market cap), the future has leaked into sample membership. Membership must use only information available at the start of each window. Top-by-volume means top-by-volume-as-of-the-window-open, recomputed forward, not once over the whole span.

### The recurring pitfall

None of these biases announce themselves. The model trains cleanly, the backtest looks good, and the damage stays invisible until capital is live. The defences are unglamorous: include the dead, fix the minimum-history rule to the pipeline's actual needs, define the universe point-in-time, and keep a composition log that can be interrogated.

---

## 7. Deliverables checklist

- [ ] Methodology markdown cell: objective, regime-drift rationale, explicit rejection of stratification (§1)
- [ ] Walk-forward splitter, calendar boundaries, transforms fit on train only (§2)
- [ ] Purge/embargo gap at every boundary, sized to max(feature lookback, label horizon), value recorded (§3)
- [ ] Time-based split confirmed; no whole-coin holdout unless separately scoped (§4)
- [ ] Per-fold metric reporting (§5)
- [ ] Dead/delisted coins included, or limitation documented (§6)
- [ ] Minimum-history threshold derived from windows and recorded (§6)
- [ ] Point-of-entry rule chosen and documented (§6)
- [ ] Early-window handling decided (§6)
- [ ] Coin-count-per-fold and symbol entry/exit log produced (§6)
- [ ] Universe selection made point-in-time, no full-history leakage (§6)
