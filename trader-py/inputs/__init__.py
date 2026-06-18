"""trader-swing Python execution layer.

A small, readable package that talks to two venues:

  - Alpaca   (US equities, paper money)   via the alpaca-py SDK
  - Binance  (spot crypto, real money)    via the python-binance SDK

It shares the exact same environment-variable names as the shell scripts in
scripts/, so your stored Keychain secrets serve both. Nothing here holds a
secret; everything is read from the process environment at run time.

The one safety switch is LIVE_TRADING. It must equal the string "true" before
any real Binance order can leave this code. Reading the market is always
allowed; spending money is not, unless you flip that switch deliberately.

Entry point:  python -m trader <command>   (see python -m trader --help)
"""

__all__ = ["config", "alpaca_client", "binance_client"]
