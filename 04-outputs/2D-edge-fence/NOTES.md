# 2D - Net-edge fee fence

Chapter Two, Controls. This is defence two. A fence, not an alarm: it refuses rather
than warns, and it is measured on net, not gross.

## What it computes

    net_move = est_move_pct - round_trip_fee_pct - expected_slippage_pct
    allow if net_move >= edge_floor_pct

A trade is refused unless its expected move, after the round-trip fee and modelled
slippage, clears the minimum-edge floor.

`validate_exit_coupling` checks the CONFIG numbers are internally consistent: the edge
floor below the take-profit, the round trip below the edge floor, the take-profit
worth more than twice the round trip, and the take-profit reachable at the ATR floor
inside the hold window.

## Functions

`net_edge`, `net_edge_ok`, `validate_exit_coupling`.

## Outputs

- the fence-check report: `outputs/CSV/2D-fence-check.csv`

## Run in isolation

    python edge_fence.py

## The three stacked defences

The defences are a principle realized across modules, not a single unit, so they are
not built as one thing.

- Defence one, the trades-per-day cap. A CONFIG control (`max_trades_per_day = 3`),
  not a computation; enforced in execution code. It bounds how often the system can
  trade in a day, so churn cannot be used to bury thin losing trades in volume.
- Defence two, the net-edge floor. This module. Every prospective trade must clear a
  minimum edge after fees and slippage or it is refused.
- Defence three, out-of-sample validation. Chapter Three's walk-forward. No
  configuration earns live money until it beats buy-and-hold and a coin flip on data
  it has never seen, after fees.

Together they make volume-hiding impossible by construction. The framing belongs in
the chapter document (`02-swing-controls/02-swing-controls.md`) alongside the CONFIG
block; this note is the module-level record of it.

## Wire back into the notebook

```python
rows = ["est_move_pct,net_move_pct,allowed"]
for m in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5):
    rows.append(f"{m},{net_edge(m):.2f},{net_edge_ok(m)}")
(OUTPUTS / "CSV").mkdir(parents=True, exist_ok=True)
(OUTPUTS / "CSV" / "2D-fence-check.csv").write_text("\n".join(rows))
```
