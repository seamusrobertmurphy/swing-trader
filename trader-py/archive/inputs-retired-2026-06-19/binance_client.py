"""Binance wrapper: spot crypto, REAL money, via the python-binance SDK.

Read this twice: every order placed through market_buy / market_sell below
spends real funds on your live Binance account. Two things stand between you
and an accidental trade:

  1. LIVE_TRADING must equal "true". Otherwise the order functions raise before
     any network call. Reading prices and balances is never gated.
  2. You place the first live order yourself, deliberately, from your Mac.

Spot only. No futures, no margin, no leverage, per the project rules.

Docs: https://python-binance.readthedocs.io
"""

from __future__ import annotations

from binance.client import Client
from binance.exceptions import BinanceAPIException

from . import config


class LiveTradingDisabled(RuntimeError):
    """Raised when an order is attempted while LIVE_TRADING is not 'true'."""


def make_client(cfg: config.BinanceConfig | None = None) -> Client:
    """Create an authenticated Binance client for the chosen venue."""
    cfg = cfg or config.load_binance()
    return Client(
        api_key=cfg.api_key,
        api_secret=cfg.api_secret,
        tld=cfg.tld,
        testnet=cfg.testnet,
        requests_params={"timeout": 20},
    )


def _friendly(exc: BinanceAPIException) -> str:
    """Turn a raw Binance error into a sentence that says what to do.

    -2015 almost always means your home IP changed and no longer matches the
    API key's trusted-IP whitelist. This mirrors the guidance in binance.sh.
    """
    if exc.code == -2015:
        return (
            "Binance error -2015: invalid API key, IP, or permissions. "
            "Most often your home IP changed. Run `curl ifconfig.me`, then update "
            "the trusted-IP list on your Binance API key page, and retry."
        )
    if exc.code == -1021:
        return (
            "Binance error -1021: timestamp outside recvWindow. Your Mac clock "
            "is likely out of sync. Enable automatic time in System Settings."
        )
    return f"Binance error {exc.code}: {exc.message}"


def get_account(client: Client | None = None) -> dict:
    """Account permissions and non-zero balances."""
    client = client or make_client()
    try:
        a = client.get_account(recvWindow=config.load_binance().recv_window)
    except BinanceAPIException as e:
        raise RuntimeError(_friendly(e)) from e
    balances = [
        {"asset": b["asset"], "free": b["free"], "locked": b["locked"]}
        for b in a.get("balances", [])
        if float(b["free"]) > 0 or float(b["locked"]) > 0
    ]
    return {
        "can_trade": a.get("canTrade"),
        "can_withdraw": a.get("canWithdraw"),
        "account_type": a.get("accountType"),
        "balances": balances,
    }


def get_price(symbol: str, client: Client | None = None) -> dict:
    """Latest price for a symbol, e.g. BTCUSDT. Public, no key needed."""
    client = client or make_client()
    try:
        return client.get_symbol_ticker(symbol=symbol)
    except BinanceAPIException as e:
        raise RuntimeError(_friendly(e)) from e


def min_notional(symbol: str, client: Client | None = None) -> float | None:
    """The smallest order value the exchange accepts for this symbol, in quote
    currency (e.g. USDT). Useful so a too-small test order is caught early."""
    client = client or make_client()
    try:
        info = client.get_symbol_info(symbol)
    except BinanceAPIException as e:
        raise RuntimeError(_friendly(e)) from e
    if not info:
        return None
    for f in info.get("filters", []):
        if f.get("filterType") in ("MIN_NOTIONAL", "NOTIONAL"):
            return float(f.get("minNotional") or f.get("notional") or 0)
    return None


def _require_live() -> None:
    if not config.live_trading_enabled():
        raise LiveTradingDisabled(
            "Refusing to place a Binance order: LIVE_TRADING is not 'true'. "
            "This is the safety switch. To arm real trading for this shell only, "
            "run: export LIVE_TRADING=true"
        )


def market_buy(symbol: str, quote_amount: float, client: Client | None = None) -> dict:
    """Spend `quote_amount` of quote currency (e.g. USDT) to buy `symbol` at market.

    Example: market_buy("BTCUSDT", 10) spends about 10 USDT on BTC.
    Gated by LIVE_TRADING. Real money.
    """
    _require_live()
    cfg = config.load_binance()
    client = client or make_client(cfg)
    floor = min_notional(symbol, client)
    if floor and quote_amount < floor:
        raise ValueError(
            f"{symbol} requires a minimum order of about {floor} in quote currency; "
            f"{quote_amount} is below it."
        )
    try:
        order = client.order_market_buy(
            symbol=symbol,
            quoteOrderQty=round(float(quote_amount), 2),
            recvWindow=cfg.recv_window,
        )
    except BinanceAPIException as e:
        raise RuntimeError(_friendly(e)) from e
    return _summarize_order(order)


def market_sell(symbol: str, quantity: float, client: Client | None = None) -> dict:
    """Sell `quantity` of the base asset of `symbol` at market.

    Example: market_sell("BTCUSDT", 0.0002) sells 0.0002 BTC.
    Gated by LIVE_TRADING. Real money.
    """
    _require_live()
    cfg = config.load_binance()
    client = client or make_client(cfg)
    try:
        order = client.order_market_sell(
            symbol=symbol,
            quantity=quantity,
            recvWindow=cfg.recv_window,
        )
    except BinanceAPIException as e:
        raise RuntimeError(_friendly(e)) from e
    return _summarize_order(order)


def _summarize_order(order: dict) -> dict:
    fills = order.get("fills", [])
    return {
        "symbol": order.get("symbol"),
        "side": order.get("side"),
        "status": order.get("status"),
        "executed_qty": order.get("executedQty"),
        "cummulative_quote_qty": order.get("cummulativeQuoteQty"),
        "order_id": order.get("orderId"),
        "fills": [
            {"price": f.get("price"), "qty": f.get("qty"), "commission": f.get("commission")}
            for f in fills
        ],
    }
