# App version, 26 September 2026

The swing-trader public app as it stood at the close of 26 September 2026, after the round-three design revisions, approved by the operator as a version to return to if later changes are not accepted. It is marked by two git tags and one relay version, listed below, and this note says what the version contains and how to restore it.

## Identifiers

| Part | Where it lives | Mark |
|---|---|---|
| Code, every script, workflow and setting | `main` branch | tag `app-2026-09-26`, on the commit that adds this note |
| Published page | `gh-pages` branch, `index.html` | tag `page-2026-09-26`, commit `7d3ff67b` |
| Relay, the Cloudflare worker that starts runs and keeps orders | Cloudflare, `swing-trader-relay` | version `0491760f-8a2f-40e5-937b-5ee973597710`, deployed 2026-09-26 20:40 UTC |
| Last code change before this note | `main` | commit `e236986f` |

The page is live at https://seamusrobertmurphy.github.io/swing-trader/.

## What it contains

The home page opens on Quick start, with a Binance and Alpaca switch above the three presets, and Run Model beside it, with the six panel cards below. Scan, Compare and Deploy are built but not shown.

A1 Data keeps its Trade geometry and Figures blocks, and its Choose Filter carries the cost floor at the 80th percentile, relative volume, the money flow gate and the edge floor, each defined under its box and in the Screening table.

A2, B1, B2 and C1 open on a Quick start guide, with model building folded under Advanced. B2 reads Choose Training Regime first and Choose Train-Test Split second, in standard machine learning terms. C1 tunes at Light, Standard, Thorough or Custom, choosing settings on validation folds only.

C2 Ledger shows Paper trades with the tiles Open, Settled and Edge, the Taken against skipped chart, Model scores as ranked bars, What carries the book, model pictures per run, the column guide, the Paper trades and Runs tables with a report per run, and the Performance Log with the calibration record under the confirmed-best rule.

A glossary opens over any page from its Glossary link, and terms in notes link to their entries.

## Running jobs

Four scheduled GitHub workflows run with this version. `demo-run` fits a user's run when the relay starts it. `demo-mark` settles paper trades and orders every hour. `demo-scan` rates every coin and stock with the presets and one test slot per market every four hours, keeping each rating as a forward paper trade. `demo-deploy` publishes the page after each of them.

## Restoring it

The code and page restore separately, and the data the jobs have gathered since is kept either way.

1. Code. From the repository, run `git checkout app-2026-09-26 -- .`, check the result with `git status`, then commit it as a new change and push, so history keeps both versions.
2. Page. With the code restored, run `.venv/bin/python 03-inputs/demo_site.py --relay https://swing-trader-relay.seamusrobertmurphy.workers.dev --publish`, which rebuilds and publishes the page from it. The page as it was built on 26 September is also kept at tag `page-2026-09-26` for comparison.
3. Relay. From `05-research/demo/relay`, run `npx wrangler rollback 0491760f-8a2f-40e5-937b-5ee973597710`, only if the relay was changed after this version.

Restoring does not delete paper trades, orders, runs or forward records gathered after 26 September; they stay in `data/` on the `gh-pages` branch.
