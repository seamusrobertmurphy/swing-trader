### Secrets via macOS Keychain

API keys live in the macOS Keychain (encrypted by the OS), never in the repo. `config.py` reads them at runtime, so it holds no secrets and is safe to commit.

### Store keys (run once in Terminal)

Omitting the value prompts you hidden, so the key never enters shell history.

```
security add-generic-password -U -a trader -s BINANCE_API_KEY -w
security add-generic-password -U -a trader -s BINANCE_API_SECRET -w
security add-generic-password -U -a trader -s ALPACA_API_KEY -w
security add-generic-password -U -a trader -s ALPACA_API_SECRET -w
```

### Read keys in config.py

```python
import subprocess

def _kc(name, account="trader"):
    return subprocess.run(
        ["security", "find-generic-password", "-a", account, "-s", name, "-w"],
        capture_output=True, text=True,
    ).stdout.strip()

ALPACA_API_KEY     = _kc("ALPACA_API_KEY")
ALPACA_API_SECRET  = _kc("ALPACA_API_SECRET")
ALPACA_BASE_URL    = "https://paper-api.alpaca.markets"

BINANCE_API_KEY    = _kc("BINANCE_API_KEY")
BINANCE_API_SECRET = _kc("BINANCE_API_SECRET")
BINANCE_TESTNET    = "true"
LIVE_TRADING       = "false"
```

### Use config in code

Import `config` and read keys from it; an env var of the same name overrides for a single run, so you can arm one session with `LIVE_TRADING=true python trade_binance.py`.

```python
import os, config
key = (os.environ.get("BINANCE_API_KEY") or config.BINANCE_API_KEY).strip()
```

### Manage a key

```
security find-generic-password -a trader -s BINANCE_API_KEY -w   # print one
security add-generic-password  -U -a trader -s BINANCE_API_KEY -w # update (re-run)
security delete-generic-password -a trader -s BINANCE_API_KEY     # remove
```

### Why this is safe

The secret never sits in a file in the repo tree, so it can't reach any commit, clone, or backup regardless of `.gitignore`. Rotating a key is just re-running the store command; no code changes.
