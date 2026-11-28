# TimesFM as an input, 2026-10-01

Record `bench-sweep-timesfm-20261001-001649.json`, written by `03-inputs/timesfm_feature_test.py`. Each preset was run as a user's run is and fitted twice on the same training rows, without and with three TimesFM columns (the median forecast's move, the band width and their ratio, each from the 512 closes up to its own candle), then scored once on the same test year. TimesFM helps a preset if, with it, the test year's Theil's U2 falls and the overfit ratio stays at or under 1.1 (win-or-loss presets), and the most confident fifth earns more after cost (every preset). Money is per cent per candle after cost, over overlapping holds.

| Preset | Outcome | Test Theil's U2 | Test AUC | Overfit ratio | Top fifth % | Every candle % | Helps |
|---|---|---|---|---|---|---|---|
| Best on record, crypto | barrier | 1.001 to 1.001 | 0.560 to 0.558 | 1.104 to 1.109 | -0.27 to -0.06 | -0.04 to -0.04 | no |
| Three-way outcome, crypto | three-way | n/a | n/a | n/a | +9.77 to +10.48 | -3.44 to -3.44 | yes |
| Quick and simple, crypto | barrier | 1.079 to 1.075 | 0.492 to 0.491 | 1.275 to 1.267 | -0.42 to -0.33 | -0.26 to -0.26 | no |
| Best on record, equity | barrier | 1.020 to 1.015 | 0.667 to 0.661 | 1.101 to 1.107 | +2.21 to +2.46 | +1.03 to +1.03 | no |
| Three-way outcome, equity | three-way | n/a | n/a | n/a | +0.55 to +0.52 | +1.30 to +1.30 | no |
| Quick and simple, equity | barrier | 1.026 to 1.024 | 0.566 to 0.574 | 1.109 to 1.106 | +1.68 to +1.76 | +0.97 to +0.97 | no |

Each cell reads without TimesFM, then with it.
