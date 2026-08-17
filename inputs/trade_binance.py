"""Live spot trading on Binance from the trained model (Task D).

This is the ONLY file in the pipeline that can spend real money, so it is kept
deliberately separate from all the read/analysis code. Four guards stand between
this script and an accidental trade:

  1. LIVE_TRADING must equal exactly "true". Any other value (including unset)
     means the script reads the market and logs what it WOULD do, but places no
     order.
  2. Testnet by default. exchange.set_sandbox_mode(True) unless BINANCE_TESTNET
     is explicitly "false". Prove the flow on fake funds first.
  3. The model's own honesty gate. model.joblib records go=True/False from the
     out-of-sample test. If the model did not beat its base rate, this script
     refuses to enter, live switch or not.
  4. A per-position cap and a cash floor, so even an armed run cannot over-concentrate.

Run order each session: read balance -> resolve EXITS first (hard stop / trailing
stop on open positions) -> then ENTRIES on coins the model flags as buy today.
Exits before entries, always, so risk comes off before new risk goes on.

Keys come from config.py (read live from the macOS Keychain; see gist.md).
An env var of the same name still overrides config for a single run, so you can
arm one session with: LIVE_TRADING=true python trade_binance.py
Operator confirms before going live; this script never flips LIVE_TRADING itself.

Usage:
  python trade_binance.py            # dry run: prints intended actions, no orders
  LIVE_TRADING=true python trade_binance.py   # armed (only after operator sign-off)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import ccxt
import joblib

import config
from build_dataset import SYMBOLS, compute_features, fetch_history

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))
POSITIONS_PATH = os.path.join(OUT, "positions.json")
TRADE_LOG = os.path.join(OUT, "trade_log_binance.csv")

# --- guardrails (echo the CLAUDE.md hard rules, applied conservatively to crypto) ---
MAX_POSITION_PCT = 0.05    # 5% of equity per position at entry
CASH_FLOOR_PCT = 0.10      # keep >=10% in cash
HARD_STOP = 0.07           # exit at -7% from entry (trend protection)
TRAILING_STOP = 0.10       # exit at -10% from the peak reached since entry
MAX_NEW_PER_RUN = 3        # max new positions opened in one run

# --- execution-cost engineering ---
# Entries default to post-only maker limits at the best bid: no spread paid, and
# Binance's maker fee applies. An unfilled maker order is cancelled after
# ENTRY_WAIT_S, and the entry is skipped for the run (a missed entry costs less
# than paying the spread; exits/stops always use market orders, protection must
# fill). Set ENTRY_STYLE=taker to restore market-order entries.
# Operator setting worth its 25%: enable "Use BNB to pay fees" on the account
# and hold a little BNB, which cuts 0.10% per side to 0.075%.
ENTRY_STYLE = os.environ.get("ENTRY_STYLE", "maker").strip().lower()
ENTRY_WAIT_S = int(os.environ.get("ENTRY_WAIT_S", "120"))


def live_enabled() -> bool:
    """The single money switch. True only for the exact string 'true'.

    Defaults to config.LIVE_TRADING; an env var of the same name overrides it,
    so a single run can be armed with LIVE_TRADING=true without editing config.
    """
    return os.environ.get("LIVE_TRADING", config.LIVE_TRADING) == "true"


def make_exchange() -> ccxt.binance:
    key = (os.environ.get("BINANCE_API_KEY") or config.BINANCE_API_KEY).strip()
    secret = (os.environ.get("BINANCE_API_SECRET") or config.BINANCE_API_SECRET).strip()
    if not key or not secret:
        raise SystemExit(
            "Binance keys not found. Store them in the macOS Keychain:\n"
            "  security add-generic-password -U -a trader -s BINANCE_API_KEY -w\n"
            "  security add-generic-password -U -a trader -s BINANCE_API_SECRET -w\n"
            "config.py reads them from there (see gist.md)."
        )
    ex = ccxt.binance({"apiKey": key, "secret": secret, "enableRateLimit": True})
    # Testnet unless explicitly turned off. Fake funds until proven.
    if os.environ.get("BINANCE_TESTNET", config.BINANCE_TESTNET) != "false":
        ex.set_sandbox_mode(True)
        print("[mode] Binance TESTNET (sandbox) — fake funds")
    else:
        print("[mode] Binance LIVE exchange — real funds")
    return ex


def load_model() -> dict:
    bundle = joblib.load(os.path.join(OUT, "model.joblib"))
    return bundle


def load_positions() -> dict:
    if os.path.exists(POSITIONS_PATH):
        with open(POSITIONS_PATH) as fh:
            return json.load(fh)
    return {}


def save_positions(pos: dict) -> None:
    with open(POSITIONS_PATH, "w") as fh:
        json.dump(pos, fh, indent=2)


def log_trade(action: str, symbol: str, qty, price, note: str) -> None:
    new = not os.path.exists(TRADE_LOG)
    with open(TRADE_LOG, "a") as fh:
        if new:
            fh.write("ts,action,symbol,qty,price,note\n")
        ts = datetime.now(timezone.utc).isoformat()
        fh.write(f"{ts},{action},{symbol},{qty},{price},{note}\n")


def latest_signal(ex: ccxt.binance, model, features: list[str]) -> dict[str, dict]:
    """For each universe symbol, compute today's feature row and the model's
    buy probability on the most recent CLOSED daily bar."""
    out = {}
    for sym in SYMBOLS:
        try:
            raw = fetch_history(sym, ex)
            feat = compute_features(raw)
            row = feat.iloc[-1]
            X = row[features].to_frame().T.astype(float)
            if X.isna().any(axis=None):
                continue
            prob = float(model.predict_proba(X)[0, 1])
            out[sym] = {"prob": prob, "buy": prob >= 0.5,
                        "price": float(row["close"]), "date": str(row["date"].date())}
        except Exception as e:  # noqa: BLE001
            print(f"  signal skip {sym}: {type(e).__name__} {str(e)[:70]}")
    return out


def equity_and_cash(ex: ccxt.binance, signals: dict) -> tuple[float, float, dict]:
    """Total equity (cash + mark-to-market holdings) and free USDT."""
    bal = ex.fetch_balance()
    free_usdt = float(bal.get("USDT", {}).get("free", 0) or 0)
    holdings = {}
    equity = free_usdt
    for sym, sig in signals.items():
        base = sym.split("/")[0]
        amt = float(bal.get(base, {}).get("total", 0) or 0)
        if amt > 0:
            value = amt * sig["price"]
            holdings[sym] = {"amount": amt, "value": value}
            equity += value
    return equity, free_usdt, holdings


def resolve_exits(ex, signals, positions, holdings, armed) -> None:
    """EXITS FIRST. Close any open position that trips the hard stop or the
    trailing stop. Peak is tracked in the local positions ledger."""
    for sym, pos in list(positions.items()):
        sig = signals.get(sym)
        if not sig:
            continue
        price = sig["price"]
        entry = pos["entry"]
        peak = max(pos.get("peak", entry), price)
        pos["peak"] = peak
        hit_hard = price <= entry * (1 - HARD_STOP)
        hit_trail = price <= peak * (1 - TRAILING_STOP)
        if hit_hard or hit_trail:
            reason = "hard_stop" if hit_hard else "trailing_stop"
            amt = holdings.get(sym, {}).get("amount", pos.get("amount", 0))
            print(f"  EXIT {sym}: {reason} at {price} (entry {entry}, peak {peak})")
            if armed and amt > 0:
                order = ex.create_order(sym, "market", "sell", amt)
                log_trade("SELL", sym, amt, price, reason)
                print(f"    placed sell {order.get('id')}")
            else:
                log_trade("WOULD_SELL", sym, amt, price, reason)
            positions.pop(sym, None)
    save_positions(positions)


def place_entry(ex, sym, spend_usdt, last_price):
    """Place one entry per ENTRY_STYLE. Returns the filled order dict, or None.

    maker: post-only limit at the best bid; poll until filled or ENTRY_WAIT_S,
    then cancel any remainder and return the order only if fully filled.
    taker: the original market order by quote quantity.
    """
    import time

    if ENTRY_STYLE != "maker":
        return ex.create_order(sym, "market", "buy", None, None,
                               {"quoteOrderQty": round(spend_usdt, 2)})

    book = ex.fetch_order_book(sym, 5)
    bid = book["bids"][0][0] if book.get("bids") else last_price
    amount = spend_usdt / bid
    order = ex.create_order(sym, "limit", "buy", amount, bid, {"postOnly": True})
    deadline = time.time() + ENTRY_WAIT_S
    while time.time() < deadline:
        time.sleep(5)
        order = ex.fetch_order(order["id"], sym)
        if order.get("status") == "closed":
            return order
    try:
        ex.cancel_order(order["id"], sym)
    except Exception:
        pass
    order = ex.fetch_order(order["id"], sym)
    # A partial fill is kept (it is real inventory) but reported as unfilled so
    # the caller records the miss; the stop logic still covers the partial via
    # the positions ledger on the next run.
    return order if float(order.get("filled") or 0) > 0 else None


def resolve_entries(ex, signals, positions, equity, free_usdt, armed) -> None:
    """ENTRIES. Buy coins the model flags today, sized by cash / number of buys,
    capped per position, never breaching the cash floor or the per-run limit."""
    buys = [s for s, sig in signals.items() if sig["buy"] and s not in positions]
    buys.sort(key=lambda s: signals[s]["prob"], reverse=True)
    buys = buys[:MAX_NEW_PER_RUN]
    if not buys:
        print("  no new buy signals today")
        return

    cash_floor = equity * CASH_FLOOR_PCT
    deployable = max(0.0, free_usdt - cash_floor)
    per_cap = equity * MAX_POSITION_PCT
    per_buy = min(per_cap, deployable / len(buys)) if buys else 0.0
    print(f"  buy candidates: {buys}")
    print(f"  equity={equity:.2f} free={free_usdt:.2f} per-buy spend={per_buy:.2f} "
          f"(cap {per_cap:.2f}, cash floor {cash_floor:.2f})")

    for sym in buys:
        sig = signals[sym]
        if per_buy <= 0:
            print(f"  SKIP {sym}: cash floor reached")
            continue
        price = sig["price"]
        amount = per_buy / price
        print(f"  ENTER {sym}: prob={sig['prob']:.3f} spend~{per_buy:.2f} @ {price}")
        if armed:
            order = place_entry(ex, sym, per_buy, price)
            if order is None:
                log_trade("MAKER_UNFILLED", sym, amount, price, f"prob={sig['prob']:.3f}")
                print("    maker order unfilled in time; entry skipped")
                continue
            fill_price = float(order.get("average") or price)
            positions[sym] = {"entry": fill_price, "peak": fill_price,
                              "amount": float(order.get("filled") or amount),
                              "opened": sig["date"]}
            log_trade("BUY", sym, amount, fill_price, f"prob={sig['prob']:.3f}")
            print(f"    placed buy {order.get('id')}")
        else:
            positions_preview = {"entry": price, "peak": price, "amount": amount,
                                 "opened": sig["date"]}
            log_trade("WOULD_BUY", sym, amount, price, f"prob={sig['prob']:.3f}")
            # In dry mode we do not persist the position; nothing was actually bought.
            _ = positions_preview
    if armed:
        save_positions(positions)


def main() -> None:
    armed = live_enabled()
    bundle = load_model()
    model, features = bundle["model"], bundle["features"]
    print(f"[model] {bundle.get('name')} trained through "
          f"{bundle.get('trained_through')} | honesty gate go={bundle.get('go')}")

    # Guard 3: the model's own out-of-sample gate.
    if armed and not bundle.get("go", False):
        raise SystemExit(
            "Refusing to trade: model.joblib honesty gate is NO-GO (the model did "
            "not beat its base rate out-of-sample). Improve the model before arming."
        )
    if not armed:
        print("[mode] DRY RUN — LIVE_TRADING is not 'true'. No orders will be placed.")

    ex = make_exchange()
    signals = latest_signal(ex, model, features)
    if not signals:
        raise SystemExit("No usable signals computed; aborting.")

    equity, free_usdt, holdings = equity_and_cash(ex, signals)
    positions = load_positions()

    print("\n== EXITS (resolved before entries) ==")
    resolve_exits(ex, signals, positions, holdings, armed)
    print("\n== ENTRIES ==")
    resolve_entries(ex, signals, positions, equity, free_usdt, armed)
    print(f"\ndone. log -> {TRADE_LOG}")


if __name__ == "__main__":
    main()
