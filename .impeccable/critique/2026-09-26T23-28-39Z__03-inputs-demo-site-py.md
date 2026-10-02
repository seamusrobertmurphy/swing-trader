---
target: swing-trader home page
total_score: 21
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 2
target_identity: "file:/Volumes/PortableSSD/Github/swing-trader/03-inputs/demo_site.py"
target_fingerprint: "sha256:451ea4b81a311edbd81165b2779c624e5545f1e8a159ef626bfda64c5b65a1a2"
target_path: /Volumes/PortableSSD/Github/swing-trader/03-inputs/demo_site.py
timestamp: 2026-09-26T23-28-39Z
slug: 03-inputs-demo-site-py
---
Method dual-agent. A, design review in Chrome at desktop and 390 px. B, detector on the saved live page and measurements in sized frames. Home page only, live build of 26 September 2026 15:49.

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | System status | 2 | No preset is selected on load, so nothing says what Run Model will send |
| 2 | Real world match | 1 | Control Centre, Ledger, Scoreboard and the A1 to C2 codes are the operator's words |
| 3 | User control | 2 | Presets and the switch save silently, with no reset |
| 4 | Consistency | 2 | Results are called "See results", "C2 Ledger" and "C2"; Run Model looks like a preset |
| 5 | Error prevention | 2 | Run Model works with no preset chosen and sends whatever is stored |
| 6 | Recognition | 2 | The "your design now" line exists on panels but not where the choice is made |
| 7 | Flexibility | 3 | Presets serve newcomers, panels serve experts |
| 8 | Minimalism | 1 | Six research cards, a timeline band and the operator's account compete with the task |
| 9 | Error recovery | 3 | Plain messages such as "Could not reach the runner. Try again in a minute." |
| 10 | Help | 3 | Glossary link and dotted glossary terms |
| Total | | 21/40 | Acceptable, up from 19 on 26 September morning |

Specificity. Half authored. The run copy and the market switch are specific to this app. The rest is the operator's private board with a run form on top, so a visitor meets the operator's research, the operator's paper account and the operator's change timeline first.

Detector. 74 findings on the home page, 382 more inside the hidden panels. True positives are 43 text items at 8 to 10 px on the cards and masthead, lane-coloured card titles and tags at 2.2 to 4.2 to 1 contrast, a flat type scale (title and block headings both 12 px at desktop), and a skipped heading level. False positives are the side-tab and dark-glow rules, the flow arrows and the reel padding. Overlay did not run; Chrome held the localhost script request, most likely its local network permission prompt.

Priority issues.
P0 Run Model is grey. button.btn outranks .demo-go in demo_site.py lines 2118 and 2121, measured rgb(236,235,231). Fix with button.btn.demo-go and make it the only amber, full-width element. polish.
P0 No default preset and no statement of what will run. Preselect Quick and simple and put a one-line summary above the button. clarify.
P1 Results are hidden and misnamed. Rename C2 Ledger to Results, add a Your results card under Run showing the user's last run state, and put the paper trades table first on C2. clarify, layout.
P1 Operator content dominates. Cards take 1,853 of 2,814 px on a phone. Hide the timeline band, label or move the account line, fold the cards under one closed heading. distill.
P2 Small type and targets. 17 of 23 controls under 44 px at desktop, switch options 34 px on a phone, tags 9.5 px and clipped. Type floor 11 px, lane text darkened to 4.5 to 1. typeset, colorize, adapt.
