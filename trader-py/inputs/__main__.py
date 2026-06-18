"""Command line for the trader-swing Python layer.

Run it as a module so the package imports resolve:

    python -m trader check
    python -m trader alpaca account
    python -m trader alpaca buy AAPL --notional 10
    python -m trader binance price BTCUSDT
    python -m trader binance account
    python -m trader binance buy BTCUSDT --quote 10     # real money, gated
    python -m trader binance sell BTCUSDT --qty 0.0002  # real money, gated

Every command prints a short, readable summary. Add --json for raw output.
Reading is always allowed. Placing a Binance order needs LIVE_TRADING=true.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import alpaca_client, binance_client, config


def _print(obj, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, indent=2, default=str))
    else:
        print(json.dumps(obj, indent=2, default=str))


def cmd_check(args) -> int:
    """Confirm both venues answer and report the safety state."""
    live = config.live_trading_enabled()
    print(f"LIVE_TRADING = {'true (REAL orders armed)' if live else 'false (safe)'}")
    print("-" * 56)

    # Alpaca (paper)
    try:
        acct = alpaca_client.get_account()
        print(f"Alpaca   OK   paper={acct['paper']}  equity={acct['equity']} "
              f"cash={acct['cash']}  status={acct['status']}")
    except Exception as e:
        print(f"Alpaca   FAIL  {e}")

    # Binance (live by default)
    try:
        cfg = config.load_binance()
        venue = "testnet" if cfg.testnet else f"binance.{cfg.tld} (LIVE, real funds)"
        acct = binance_client.get_account()
        n = len(acct["balances"])
        print(f"Binance  OK   {venue}  can_trade={acct['can_trade']}  "
              f"non-zero balances={n}")
    except Exception as e:
        print(f"Binance  FAIL  {e}")
    return 0


def cmd_alpaca(args) -> int:
    if args.action == "account":
        _print(alpaca_client.get_account(), args.json)
    elif args.action == "positions":
        _print(alpaca_client.get_positions(), args.json)
    elif args.action == "orders":
        _print(alpaca_client.list_orders(), args.json)
    elif args.action == "buy":
        if args.notional is None:
            print("alpaca buy needs --notional (dollars), e.g. --notional 10", file=sys.stderr)
            return 64
        res = alpaca_client.market_buy(args.symbol, args.notional)
        print(f"Paper order submitted: buy ${args.notional} of {args.symbol}")
        _print(res, args.json)
    return 0


def cmd_binance(args) -> int:
    if args.action == "price":
        _print(binance_client.get_price(args.symbol), args.json)
    elif args.action == "account":
        _print(binance_client.get_account(), args.json)
    elif args.action == "buy":
        if args.quote is None:
            print("binance buy needs --quote (amount in USDT etc.), e.g. --quote 10", file=sys.stderr)
            return 64
        res = binance_client.market_buy(args.symbol, args.quote)
        print(f"LIVE order filled: spent ~{args.quote} buying {args.symbol}")
        _print(res, args.json)
    elif args.action == "sell":
        if args.qty is None:
            print("binance sell needs --qty (base asset amount), e.g. --qty 0.0002", file=sys.stderr)
            return 64
        res = binance_client.market_sell(args.symbol, args.qty)
        print(f"LIVE order filled: sold {args.qty} of {args.symbol}")
        _print(res, args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m trader", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="raw JSON output")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="confirm both venues connect; show safety state")

    a = sub.add_parser("alpaca", help="US equities, paper money")
    a.add_argument("action", choices=["account", "positions", "orders", "buy"])
    a.add_argument("symbol", nargs="?", help="ticker, e.g. AAPL (for buy)")
    a.add_argument("--notional", type=float, help="dollars to buy (for buy)")

    b = sub.add_parser("binance", help="spot crypto, REAL money (orders gated)")
    b.add_argument("action", choices=["price", "account", "buy", "sell"])
    b.add_argument("symbol", nargs="?", help="pair, e.g. BTCUSDT")
    b.add_argument("--quote", type=float, help="quote-currency amount to spend (for buy)")
    b.add_argument("--qty", type=float, help="base-asset amount to sell (for sell)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "check":
            return cmd_check(args)
        if args.cmd == "alpaca":
            return cmd_alpaca(args)
        if args.cmd == "binance":
            return cmd_binance(args)
    except (config.ConfigError, binance_client.LiveTradingDisabled) as e:
        print(str(e), file=sys.stderr)
        return 1
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
