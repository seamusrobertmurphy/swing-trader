"""Single source of secrets and run config for the trader pipeline.

THIS FILE HOLDS NO SECRETS. It only decides where to look for them, so it is
safe to commit, and it is committed on purpose: it was gitignored until
2026-08-26, which meant a fresh clone had no config module at all and every
tool died on `import config` before printing anything useful.

Resolution order for each key, first hit wins:

  1. the process environment          works everywhere; how Linux/systemd feeds it
  2. a .env file in the repo root     gitignored, one KEY=value per line
  3. the macOS login Keychain         only when the `security` binary exists

Nothing here raises. A missing key resolves to an empty string, and the caller
decides whether that is fatal; `require()` below turns it into one clear abort
naming exactly which variable is absent, which is what CLAUDE.md's Environment
section asks for.

Store keys on macOS:

    security add-generic-password -U -a trader -s ALPACA_API_KEY -w
    security add-generic-password -U -a trader -s ALPACA_API_SECRET -w

Store keys on Linux (or anywhere), in <repo>/.env, mode 600:

    ALPACA_API_KEY=...
    ALPACA_API_SECRET=...
"""
from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENV_FILE = REPO / ".env"


@lru_cache(maxsize=1)
def _dotenv() -> dict:
    """Parse <repo>/.env. Absent file is normal, not an error."""
    out: dict = {}
    if not ENV_FILE.exists():
        return out
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip("'").strip('"')
    return out


@lru_cache(maxsize=1)
def _have_keychain() -> bool:
    """macOS only. On Linux the binary is absent and subprocess would raise
    FileNotFoundError at import time, taking every tool down with it."""
    return shutil.which("security") is not None


def _kc(name: str, account: str = "trader") -> str:
    if not _have_keychain():
        return ""
    try:
        return subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", name, "-w"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def get(name: str, default: str = "") -> str:
    """Resolve one key: environment, then .env, then Keychain."""
    v = os.environ.get(name)
    if v:
        return v.strip()
    v = _dotenv().get(name)
    if v:
        return v.strip()
    v = _kc(name)
    return v if v else default


def source_of(name: str) -> str:
    """Where a key came from. For diagnostics, never prints the value."""
    if os.environ.get(name):
        return "environment"
    if _dotenv().get(name):
        return f"{ENV_FILE}"
    if _kc(name):
        return "macOS Keychain"
    return "NOT FOUND"


def require(*names: str) -> None:
    """Abort with one clear message naming every missing key."""
    missing = [n for n in names if not get(n)]
    if missing:
        raise SystemExit(
            "ABORT: missing credential(s): " + ", ".join(missing) + ".\n"
            f"Set them in the environment, or in {ENV_FILE} (mode 600), "
            "or in the macOS Keychain. See inputs/config.py for the exact form."
        )


# --- Alpaca (US equities) ---
ALPACA_API_KEY     = get("ALPACA_API_KEY")
ALPACA_API_SECRET  = get("ALPACA_API_SECRET")
ALPACA_BASE_URL    = get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# --- Binance (spot crypto; track closed 2026-08-17, kept for the archive) ---
BINANCE_API_KEY    = get("BINANCE_API_KEY")
BINANCE_API_SECRET = get("BINANCE_API_SECRET")
BINANCE_TESTNET    = get("BINANCE_TESTNET", "true")
LIVE_TRADING       = get("LIVE_TRADING", "false")   # the money switch


if __name__ == "__main__":
    print(f"repo:     {REPO}")
    print(f".env:     {ENV_FILE} ({'present' if ENV_FILE.exists() else 'absent'})")
    print(f"keychain: {'available' if _have_keychain() else 'not on this platform'}")
    for n in ("ALPACA_API_KEY", "ALPACA_API_SECRET", "BINANCE_API_KEY",
              "BINANCE_API_SECRET"):
        v = get(n)
        print(f"  {n:20s} {'set (' + str(len(v)) + ' chars)' if v else 'MISSING':22s} "
              f"from {source_of(n)}")
    print(f"  {'ALPACA_BASE_URL':20s} {ALPACA_BASE_URL}")
    print(f"  {'LIVE_TRADING':20s} {LIVE_TRADING}")
