---
target: public friends app
total_score: 19
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 5
target_identity: "file:/Volumes/PortableSSD/Github/swing-trader/03-inputs/demo_site.py"
target_fingerprint: "sha256:081eacfef15069479619a6534153a59a804f3ffec400ccf3adb44db9fa969943"
target_path: /Volumes/PortableSSD/Github/swing-trader/03-inputs/demo_site.py
timestamp: 2026-09-26T06-43-51Z
slug: 03-inputs-demo-site-py
---
# Combined critique

Method dual-agent. Assessment A, the design review, is `A-critique.md`. Assessment B, the detector and technical audit, is `B-audit.md`. Both examined the live page at https://seamusrobertmurphy.github.io/swing-trader/ built from commit b2b60f47 on 25 and 26 September 2026, at 390 px phone and 1440 px desktop in headless Chrome. The Claude in Chrome extension connected only after both captures, and was used afterwards to confirm the page loads.

## Scores

Design review, Nielsen heuristics, 19 of 40, Poor, against 17 of 40 on 25 September.

| # | Heuristic | Score | Key issue |
|---|-----------|-------|-----------|
| 1 | Visibility of system status | 2 | Run status is a grey note with no live region, and the current panel chip is never marked |
| 2 | Match with the real world | 2 | Title reads Control Centre; settings read monte-carlo, LogReg.glm and f_wc_ |
| 3 | User control and freedom | 2 | Presets reset every field, but Back leaves the site and a reload forgets a run |
| 4 | Consistency and standards | 2 | Run Model is the same grey as the presets, and bars and candles name one unit |
| 5 | Error prevention | 1 | A run with no preset sends the operator's scratch settings, and the name is published without warning |
| 6 | Recognition rather than recall | 2 | Preset notes appear only after the tap, and the market choice sits on A1 away from the presets |
| 7 | Flexibility and efficiency | 3 | Two taps run a model from the first phone screen |
| 8 | Aesthetic and minimalist design | 1 | 52 settings over five panels, 12 Save buttons, C1 at 343,870 px on a phone |
| 9 | Error recovery | 2 | Relay errors are plain, but a failed run shows raw error text |
| 10 | Help and documentation | 2 | C2's guide is good; five panels name buttons that were removed |
| Total | | 19/40 | Poor |

Technical audit, 8 of 20, Poor, unchanged from 25 September. Accessibility 2, performance 1, responsive 2, theming 2, integrity 1. The detector returned 526 findings across 17 rules on the saved live page; its false positives are listed in `B-audit.md`.

## Specificity verdict

Both assessments reached the same verdict independently. The content is specific to this study, the three presets name their learner, coins and reason, and C2 is authored for a friend. The structure is the operator's board with parts cut out, and every cut left something behind that still claims to work, such as 219 reel images nobody can open, filters with no handler, and a variable-selection block on B1 that calls the operator's local server on every load and shows an error.

## Priority issues

1. P1, results cut off on C2. On a phone the Model scores chart and its note are drawn 700 px wide in a 334 px column, so the friend's own score sits past the right edge. On desktop the Runs table cuts the Theil's U2 column. Both assessments found it. Fix with `minmax(0,1fr)` grid tracks at `demo_site.py` lines 449, 477 and 492. Command layout.
2. P1, quick path unguarded. With no preset chosen, Run Model sends the operator's scratch settings. Run Model renders grey because `button.btn` at line 1225 outranks `.demo-go` at line 1228. The market choice lives only on A1. Fix by applying Quick and simple by default, adding a crypto or stocks toggle inside Quick start, making Run Model amber, and printing one line above it saying what will run. Commands onboard and polish.
3. P1, B1 shows an error to every visitor. `control_varselect.py` line 682 posts to `/varselect/fit`, which answers 405 on GitHub Pages. Fix by replacing the block with its precomputed table on the public page. Command harden.
4. P1, page weight. 14.4 MB transferred; at 1.6 Mbps the buttons are visible from 17 s but do nothing until 78 s. 10.3 MB are reel images nobody can open. Commands optimize and harden.
5. P1, settings wall and stale instructions. 52 visible settings, 12 Save buttons, What to do lists naming removed buttons, operator strings such as "this laptop" and "04-outputs/AA-evals" still visible. Commands distill and clarify.

Also P1 in the audit, lane colours and header grey used as text fail contrast (2.58 to 3.80 to 1), and the run status has no live region.

## Open decision

The masthead still shows the operator's paper stock account, $102,206 with 50 holdings, and the page is titled Control Centre. Hiding it or labelling it is handover item 2 and needs the operator.

## Persona red flags

A first-timer on a phone waits for 14.4 MB, sees a stranger's $102,206, finds four grey buttons with none marked as the start, runs with no preset and sends the operator's settings, then returns to C2 to find their own score cut off. A sceptical friend reads Best on record claiming the lowest error of 323 fits, then sees both friend runs at 1.041 and 1.124, worse than always guessing the average, with nothing in words saying so, and a run with an overfit ratio of 1.119 above the chart's own 1.1 line marked Done.

## Questions raised

1. If two taps run a model, should any setting be open by default on the public page?
2. Should C2 be built around one friend's run, with the verdict, tickets and settle date on one card?
3. Should the page say before Run that no preset has yet beaten always guessing on unseen data?
