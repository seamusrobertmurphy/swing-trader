"""Alpaca wrapper: US equities on paper money, via the alpaca-py SDK.

Alpaca from Canada is paper only, so this is your safe sandbox: orders here
spend practice money, never real funds. The functions below are thin: they
build the official client, then call it and hand back plain Python objects.

Docs: https://docs.alpaca.markets  |  SDK: https://github.com/alpacahq/alpaca-py
"""

from __future__ import annotations

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from . import config


def make_client(cfg: config.AlpacaConfig | None = None) -> TradingClient:
    """Create an authenticated Alpaca trading client.

    paper=True points the SDK at the paper endpoint. We derive it from the base
    URL so the same stored keys cannot accidentally hit a live account.
    """
    cfg = cfg or config.load_alpaca()
    return TradingClient(
        api_key=cfg.api_key,
        secret_key=cfg.api_secret,
        paper=cfg.is_paper,
    )


def get_account(client: TradingClient | None = None) -> dict:
    """Account snapshot: equity, cash, buying power, trading status."""
    client = client or make_client()
    a = client.get_account()
    return {
        "account_number": a.account_number,
        "status": str(a.status),
        "currency": a.currency,
        "cash": a.cash,
        "equity": a.equity,
        "buying_power": a.buying_power,
        "paper": True,  # enforced by make_client
    }


def get_positions(client: TradingClient | None = None) -> list[dict]:
    """Open positions with symbol, quantity, and unrealised P&L."""
    client = client or make_client()
    out = []
    for p in client.get_all_positions():
        out.append(
            {
                "symbol": p.symbol,
                "qty": p.qty,
                "avg_entry_price": p.avg_entry_price,
                "market_value": p.market_value,
                "unrealized_pl": p.unrealized_pl,
            }
        )
    return out


def list_orders(client: TradingClient | None = None) -> list[dict]:
    """The most recent orders (open and closed)."""
    client = client or make_client()
    out = []
    for o in client.get_orders():
        out.append(
            {
                "symbol": o.symbol,
                "side": str(o.side),
                "qty": o.qty,
                "notional": o.notional,
                "type": str(o.order_type),
                "status": str(o.status),
                "submitted_at": str(o.submitted_at),
            }
        )
    return out


def market_buy(symbol: str, notional: float, client: TradingClient | None = None) -> dict:
    """Buy `notional` dollars of `symbol` at market (fractional shares allowed).

    Paper money, so this is not gated by LIVE_TRADING. A live Alpaca account
    (not available from Canada today) would be refused unless the switch is on.
    """
    cfg = config.load_alpaca()
    if not cfg.is_paper and not config.live_trading_enabled():
        raise RuntimeError(
            "Refusing a live Alpaca order: ALPACA_BASE_URL is not the paper host "
            "and LIVE_TRADING is not 'true'."
        )
    client = client or make_client(cfg)
    req = MarketOrderRequest(
        symbol=symbol,
        notional=round(float(notional), 2),
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )
    o = client.submit_order(req)
    return {
        "id": str(o.id),
        "symbol": o.symbol,
        "side": str(o.side),
        "notional": o.notional,
        "status": str(o.status),
        "submitted_at": str(o.submitted_at),
    }
