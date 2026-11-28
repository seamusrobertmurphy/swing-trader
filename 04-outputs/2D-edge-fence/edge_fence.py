"""
2D - Net-edge fee fence (Chapter Two, Controls). This is defence two.

Standalone workbench copy. Canonical version lives in the controls notebook
(02-swing-controls.ipynb: net_edge, net_edge_ok, validate_exit_coupling). Develop
here, fold back.

The fence refuses, it does not warn, and it is measured on net, not gross. A trade
is allowed only if its expected move, after the round-trip fee and modelled slippage,
clears the minimum-edge floor:

  net_move = est_move_pct - round_trip_fee_pct - expected_slippage_pct
  allow if net_move >= edge_floor_pct

validate_exit_coupling checks that the CONFIG numbers are internally consistent: the
edge floor below the take-profit, the round trip below the edge floor, the take-profit
worth more than twice the round trip, and the take-profit reachable at the ATR floor
inside the hold window.

The three stacked defences (see NOTES.md): defence one is the trades-per-day cap (a
CONFIG control), defence two is this net-edge floor, defence three is Chapter Three's
out-of-sample validation. They are a principle realized across modules, not one unit.

Run:  python edge_fence.py
"""

# CONFIG subset mirrored from the notebook CONFIG (cell 4). Notebook is canonical.
CONFIG = dict(
    round_trip_fee_pct    = 0.15,
    expected_slippage_pct = 0.05,
    edge_floor_pct        = 1.5,
    take_profit_pct       = 3.0,
    atr_floor_pct         = 2.5,
    hold_window_days_max  = 10,
    max_trades_per_day    = 3,   # defence one, the cap; enforced in execution code
)


def net_edge(est_move_pct, cfg=CONFIG):
    """NET expected move after round-trip fee and slippage (not gross)."""
    return est_move_pct - cfg["round_trip_fee_pct"] - cfg["expected_slippage_pct"]


def net_edge_ok(est_move_pct, cfg=CONFIG):
    """The fence: refuse unless net move clears the floor. Refuses, does not warn."""
    return net_edge(est_move_pct, cfg) >= cfg["edge_floor_pct"]


def validate_exit_coupling(cfg=CONFIG):
    """Internal-consistency checks on the entry/exit economics."""
    rt = cfg["round_trip_fee_pct"] + cfg["expected_slippage_pct"]
    days_to_tp = cfg["take_profit_pct"] / cfg["atr_floor_pct"]  # at the ATR floor
    return {
        "edge_floor < take_profit":              cfg["edge_floor_pct"] < cfg["take_profit_pct"],
        "round_trip < edge_floor":               rt < cfg["edge_floor_pct"],
        "take_profit > 2x round_trip (alive)":   cfg["take_profit_pct"] > 2 * rt,
        f"TP reachable at ATR floor within window (~{days_to_tp:.1f} days)":
            days_to_tp <= cfg["hold_window_days_max"],
    }


if __name__ == "__main__":
    print("Net-edge fence (gross est. move -> net -> allowed?):")
    for m in (1.0, 1.5, 2.0, 3.5):
        print(f"  est {m:>4}%  ->  net {net_edge(m):>5.2f}%  ->  "
              f"{'ALLOW' if net_edge_ok(m) else 'refuse'}")
    print("\nExit-coupling checks (config must satisfy all):")
    for k, v in validate_exit_coupling().items():
        print(f"  [{'ok' if v else 'XX'}] {k}")
    print(f"\nDefence one (the cap): max {CONFIG['max_trades_per_day']} trades per day.")
