"""acquire_vision.py - Stage A: survivorship-complete acquisition from Binance Vision.

Why this module exists
----------------------
flow_data.py builds its download list from Binance `exchangeInfo`, which returns ONLY
symbols whose status is TRADING today. Every coin that delisted, was rugged, or quietly
died is excluded before a single file is fetched. A model trained on that list learns the
statistics of survivors and overstates real-world performance; the bias enters at the
symbol-list step and is invisible by the time you split. See
tasks/task-request-data-pipeline-methodology.md (Stage A).

The data for dead coins is NOT the problem -- data.binance.vision retains delisted symbols
for years (the canonical Binance example uses ADABKRW, long delisted). The problem is
ENUMERATION. This module sources the symbol universe from the archive listing itself, which
records every symbol that ever had data, delisted ones included, rather than asking a live
endpoint what trades now.

What it provides
----------------
  crawl_archive_symbols()   the full historical USDT spot universe by crawling the
                            data.binance.vision S3 listing (includes dead coins)
  snapshot_exchange_info()  a DATED snapshot of currently-active symbols; the active/
                            delisted partition is only valid as of this date
  download_symbol()         resumable monthly+daily kline pull with SHA-256 .CHECKSUM
                            verification on every file
  partition_survivorship()  split the crawled universe into active vs delisted vs the
                            dated snapshot, and quantify the delisted share
  audit_dead_coins()        confirm known-delisted pairs are present (the Stage A.5 guard:
                            if they are absent, the universe was built from a live list)

Storage matches the rest of the repo: raw zips under inputs/binance-data/klines_1h/<SYMBOL>/,
exactly where flow_data.py and build_dataset_1h.py already read them, so a survivorship-
complete re-pull simply adds the dead coins alongside the survivors with no path changes.

The big download runs on the operator's Mac, not here. This module is resumable (skips
files already on disk) and verifies checksums, so a stalled pull is re-run safely.

Plain ASCII. No API key. No orders. Read-only public data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

# ----------------------------------------------------------------------------
# Endpoints and paths
# ----------------------------------------------------------------------------
BASE_URL = "https://data.binance.vision/"
# S3 bucket listing. The data.binance.vision vanity host serves the WEBSITE (HTML), not
# the S3 XML listing, so we must hit the underlying bucket directly via the path-style S3
# endpoint. Several regional/global hosts serve the same bucket; we try them in order.
LIST_URLS = [
    "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision",
    "https://data.binance.vision.s3.amazonaws.com",
]
EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
KLINES_PREFIX = "data/spot/monthly/klines/"

HERE = os.path.dirname(os.path.abspath(__file__))
BINANCE_DATA = os.path.join(HERE, "binance-data")
DEFAULT_START = "2017-08"          # spot history begins 2017-08-17; earlier 404s skip cleanly

# Stage A.5 guard. A handful of pairs that DID list against USDT and were later removed.
# If none of these surface in the crawl, the universe was built from a live list and the
# acquisition must be redone. Confirmed-present members are reported by audit_dead_coins().
KNOWN_DELISTED_USDT = ["FTTUSDT", "LUNAUSDT", "USTUSDT", "SRMUSDT", "VENUSDT",
                       "BCCUSDT", "ANTUSDT", "WAVESUSDT", "BTCSTUSDT", "RAYUSDT"]

# Leveraged tokens (the strategy forbids them, CLAUDE.md hard rules). Kept in the FULL
# universe artefact with a flag, but excluded from the default download set.
_LEVERAGED_RE = re.compile(r"(UP|DOWN|BULL|BEAR)USDT$")

# Binance spot kline CSV layout (no reliable header in the archives).
KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "num_trades", "taker_buy_base", "taker_buy_quote", "ignore"]


# --------------------------------------------------------------------------- #
# Low-level fetch
# --------------------------------------------------------------------------- #
def _get(url, timeout=60, retries=4, backoff=3.0):
    """Return raw bytes for url, or None on 404. Retries transient network errors with
    exponential backoff (the full-market pull stalled on read timeouts; a retry loop is
    the documented fix). Raises on a non-404 HTTP error after exhausting retries."""
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        if attempt < retries - 1:
            time.sleep(backoff * (2 ** attempt))
    raise last if last else RuntimeError(f"failed: {url}")


def _save(raw, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(raw)


# --------------------------------------------------------------------------- #
# A.3 -- enumerate the historical universe from the archive listing
# --------------------------------------------------------------------------- #
def _list_page(prefix, marker, list_base):
    """One S3 ListBucketResult page. Returns (common_prefixes, next_marker, is_truncated)."""
    q = f"?delimiter=/&prefix={urllib.parse.quote(prefix)}"
    if marker:
        q += f"&marker={urllib.parse.quote(marker)}"
    raw = _get(list_base + q)
    if raw is None:
        raise RuntimeError(f"listing 404 at {list_base + q}")
    body = raw.decode("utf-8", "ignore")
    prefixes = re.findall(r"<Prefix>([^<]+)</Prefix>", body)
    # The first <Prefix> echoes the request prefix; CommonPrefixes are the child folders.
    children = [p for p in prefixes if p != prefix]
    m = re.search(r"<NextMarker>([^<]+)</NextMarker>", body)
    next_marker = m.group(1) if m else None
    truncated = "<IsTruncated>true</IsTruncated>" in body
    return children, next_marker, truncated


def crawl_archive_symbols(quote="USDT", include_leveraged=False, list_base=None,
                          verbose=True):
    """Crawl data.binance.vision and return EVERY symbol that ever had monthly 1h kline
    data, delisted ones included -- the survivorship-complete universe. Filters to the
    given quote asset (default USDT). Leveraged tokens are excluded by default.

    Returns a dict: {"symbols": [...], "leveraged": [...], "crawled_at": iso,
                     "total_seen": int}. `symbols` is the download set; `leveraged` is
    kept separately so the full record is auditable."""
    bases = [list_base] if list_base else list(LIST_URLS)
    err = None
    for base in bases:
        try:
            seen, marker, page = [], None, 0
            while True:
                children, marker, truncated = _list_page(KLINES_PREFIX, marker, base)
                for c in children:
                    # c = 'data/spot/monthly/klines/BTCUSDT/'
                    sym = c.rstrip("/").rsplit("/", 1)[-1]
                    seen.append(sym)
                page += 1
                if verbose and page % 5 == 0:
                    print(f"  crawled {page} pages, {len(seen)} symbols so far...")
                if not truncated or not marker:
                    break
            break
        except Exception as e:                    # try the next listing host
            err = e
            seen = None
    if seen is None:
        raise RuntimeError(f"all listing hosts failed; last error: {err}")

    seen = sorted(set(seen))
    matched = [s for s in seen if s.endswith(quote)]
    leveraged = [s for s in matched if _LEVERAGED_RE.search(s)]
    if include_leveraged:
        symbols = matched
    else:
        symbols = [s for s in matched if not _LEVERAGED_RE.search(s)]
    if verbose:
        print(f"crawl: {len(seen)} total symbols, {len(matched)} {quote} pairs, "
              f"{len(leveraged)} leveraged ({'kept' if include_leveraged else 'excluded'})")
    return {"symbols": symbols, "leveraged": leveraged,
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "total_seen": len(seen), "quote": quote}


# --------------------------------------------------------------------------- #
# A.3 -- dated snapshot of the live (active) universe
# --------------------------------------------------------------------------- #
def snapshot_exchange_info(out_dir=BINANCE_DATA, quote="USDT"):
    """Pull exchangeInfo ONCE and write a DATED snapshot of currently-active symbols.
    The retrieval date is part of the artefact: the active/delisted partition is only
    valid as of when this was taken. Returns (active_symbols, path)."""
    raw = _get(EXCHANGE_INFO_URL)
    if raw is None:
        raise RuntimeError("exchangeInfo returned 404 (unexpected)")
    info = json.loads(raw)
    active = sorted({s["symbol"] for s in info.get("symbols", [])
                     if s.get("quoteAsset") == quote and s.get("status") == "TRADING"
                     and s.get("isSpotTradingAllowed", False)})
    stamp = datetime.now(timezone.utc)
    artefact = {"taken_at": stamp.isoformat(), "quote": quote,
                "active_symbols": active, "n_active": len(active)}
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"exchange_info_snapshot_{stamp:%Y-%m-%d}.json")
    with open(path, "w") as f:
        json.dump(artefact, f, indent=2)
    print(f"snapshot: {len(active)} active {quote} pairs as of {stamp:%Y-%m-%d} -> {path}")
    return active, path


def load_latest_snapshot(out_dir=BINANCE_DATA):
    """Return (active_symbols, taken_at, path) from the most recent dated snapshot, or
    (None, None, None) if none exists. The survivorship audit must use this dated file,
    never a live call at analysis time."""
    if not os.path.isdir(out_dir):
        return None, None, None
    snaps = sorted(f for f in os.listdir(out_dir)
                   if f.startswith("exchange_info_snapshot_") and f.endswith(".json"))
    if not snaps:
        return None, None, None
    path = os.path.join(out_dir, snaps[-1])
    with open(path) as f:
        a = json.load(f)
    return a["active_symbols"], a.get("taken_at"), path


# --------------------------------------------------------------------------- #
# A.2 -- download with checksum verification
# --------------------------------------------------------------------------- #
def _month_iter(start_ym, end_ym):
    sy, sm = (int(x) for x in start_ym.split("-"))
    ey, em = (int(x) for x in end_ym.split("-"))
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def _kline_url(symbol, period, kind, interval):
    return (f"{BASE_URL}data/spot/{kind}/klines/{symbol}/{interval}/"
            f"{symbol}-{interval}-{period}.zip")


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _verify_checksum(zip_bytes, checksum_url):
    """Fetch the .CHECKSUM companion and compare SHA-256. Returns True if it matches,
    False on mismatch, None if no checksum is published (older files sometimes lack one)."""
    craw = _get(checksum_url)
    if craw is None:
        return None
    expected = craw.decode("utf-8", "ignore").split()[0].strip().lower()
    return _sha256(zip_bytes) == expected


def _fetch_verified(url, dest, verify=True):
    """Download one zip to dest with optional checksum verification. Skips if already on
    disk. Returns 'cached' | 'ok' | 'ok-nochecksum' | 'missing' | 'badchecksum'."""
    if os.path.exists(dest):
        return "cached"
    raw = _get(url)
    if raw is None:
        return "missing"
    if verify:
        ok = _verify_checksum(raw, url + ".CHECKSUM")
        if ok is False:
            raw2 = _get(url)                       # one re-download on mismatch
            if raw2 is None or _verify_checksum(raw2, url + ".CHECKSUM") is False:
                return "badchecksum"
            raw = raw2
        status = "ok" if ok is True else "ok-nochecksum"
    else:
        status = "ok"
    _save(raw, dest)
    return status


def download_symbol(symbol, out_dir=BINANCE_DATA, interval="1h", start_ym=DEFAULT_START,
                    end_ym=None, verify=True, verbose=False):
    """Resumable monthly pull for one symbol, with daily-file top-up for the current open
    month, into out_dir/klines_<interval>/<SYMBOL>/. Every file is checksum-verified.
    Returns a counts dict. Months that 404 are simply absent (the coin had not listed yet,
    or delisted) -- that is expected and is exactly the lifespan signal Stage B reads."""
    end_ym = end_ym or datetime.now(timezone.utc).strftime("%Y-%m")
    sub = "klines" if interval == "1d" else f"klines_{interval}"
    sym_dir = os.path.join(out_dir, sub, symbol)
    counts = dict(cached=0, ok=0, nochecksum=0, missing=0, bad=0)
    today = date.today()
    for y, m in _month_iter(start_ym, end_ym):
        period = f"{y}-{m:02d}"
        dest = os.path.join(sym_dir, f"{symbol}-{interval}-{period}.zip")
        st = _fetch_verified(_kline_url(symbol, period, "monthly", interval), dest, verify)
        if st == "cached":
            counts["cached"] += 1
        elif st == "ok":
            counts["ok"] += 1
        elif st == "ok-nochecksum":
            counts["nochecksum"] += 1
        elif st == "badchecksum":
            counts["bad"] += 1
            print(f"  CHECKSUM MISMATCH {symbol} {period} -- not saved")
        elif st == "missing" and (y, m) == (today.year, today.month):
            # current open month has no monthly file yet: grab daily files
            for d in range(1, today.day + 1):
                dper = f"{y}-{m:02d}-{d:02d}"
                ddest = os.path.join(sym_dir, f"{symbol}-{interval}-{dper}.zip")
                ds = _fetch_verified(_kline_url(symbol, dper, "daily", interval), ddest, verify)
                if ds in ("ok", "ok-nochecksum"):
                    counts["ok"] += 1
        else:
            counts["missing"] += 1
    if verbose:
        print(f"  {symbol}: {counts}")
    return counts


def download_universe(symbols, out_dir=BINANCE_DATA, interval="1h", start_ym=DEFAULT_START,
                      end_ym=None, verify=True):
    """Drive download_symbol over the whole universe. Resumable: re-running skips files
    already on disk, so a stalled pull is simply re-launched. Prints a per-symbol line and
    a final tally; the heavy run belongs on the operator's Mac."""
    total = dict(cached=0, ok=0, nochecksum=0, missing=0, bad=0)
    for i, sym in enumerate(symbols, 1):
        c = download_symbol(sym, out_dir, interval, start_ym, end_ym, verify)
        for k in total:
            total[k] += c[k]
        got = c["cached"] + c["ok"] + c["nochecksum"]
        print(f"[{i}/{len(symbols)}] {sym}: {got} files "
              f"(new {c['ok']+c['nochecksum']}, cached {c['cached']}, bad {c['bad']})")
    print(f"\ntotal: {total}")
    if total["bad"]:
        print(f"WARNING: {total['bad']} files failed checksum and were not saved; re-run to retry.")
    return total


# --------------------------------------------------------------------------- #
# A.5 / B.5 -- survivorship partition and the dead-coin presence guard
# --------------------------------------------------------------------------- #
def partition_survivorship(universe_symbols, active_symbols):
    """Split the crawled universe against the dated active snapshot. Returns a dict with
    active/delisted lists and the delisted share. A delisted share near zero means the
    universe was built from a live list and Stage A must be revisited."""
    uni = set(universe_symbols)
    act = set(active_symbols) & uni
    delisted = sorted(uni - act)
    n = max(1, len(uni))
    return {"n_universe": len(uni), "n_active": len(act), "n_delisted": len(delisted),
            "delisted_share": len(delisted) / n,
            "active": sorted(act), "delisted": delisted}


def audit_dead_coins(universe_symbols, known=KNOWN_DELISTED_USDT, on_disk_dir=None,
                     interval="1h"):
    """Stage A.5 guard. Confirm known-delisted pairs are present in the crawled universe
    (and, if on_disk_dir is given, that their kline folders actually downloaded). Returns
    a dict; raises nothing, but the caller should treat an empty `present_in_universe` as
    a hard failure -- it means the dead coins never made it in."""
    uni = set(universe_symbols)
    present = [s for s in known if s in uni]
    absent = [s for s in known if s not in uni]
    on_disk = None
    if on_disk_dir:
        sub = "klines" if interval == "1d" else f"klines_{interval}"
        root = os.path.join(on_disk_dir, sub)
        on_disk = [s for s in present
                   if os.path.isdir(os.path.join(root, s))
                   and any(f.endswith(".zip") for f in os.listdir(os.path.join(root, s)))]
    res = {"checked": known, "present_in_universe": present, "absent_from_universe": absent,
           "downloaded": on_disk}
    print(f"dead-coin audit: {len(present)}/{len(known)} known-delisted present in universe"
          + (f"; {len(on_disk)} downloaded" if on_disk is not None else ""))
    if not present:
        print("FAIL: no known-delisted pairs in the universe -- it was built from a live "
              "list. Redo Stage A (crawl the archive, do not call exchangeInfo).")
    return res


# --------------------------------------------------------------------------- #
# Universe artefact persistence
# --------------------------------------------------------------------------- #
def write_universe(crawl_result, out_dir=BINANCE_DATA):
    """Persist the crawled universe (run-stamped) so a later re-run does not silently
    overwrite the symbol list a download was based on."""
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(out_dir, f"universe_vision_{crawl_result['quote']}_{stamp}.json")
    with open(path, "w") as f:
        json.dump(crawl_result, f, indent=2)
    print(f"universe -> {path} ({len(crawl_result['symbols'])} symbols)")
    return path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(description="Stage A: survivorship-complete Binance Vision acquisition")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("crawl", help="enumerate the full historical USDT universe (incl. dead coins)")
    pc.add_argument("--quote", default="USDT")
    pc.add_argument("--include-leveraged", action="store_true")
    pc.add_argument("--out", default=BINANCE_DATA)

    ps = sub.add_parser("snapshot", help="write a dated exchangeInfo active-symbol snapshot")
    ps.add_argument("--quote", default="USDT")
    ps.add_argument("--out", default=BINANCE_DATA)

    pd_ = sub.add_parser("download", help="download klines for the crawled universe (resumable, checksummed)")
    pd_.add_argument("--interval", default="1h")
    pd_.add_argument("--start", default=DEFAULT_START)
    pd_.add_argument("--end", default=None)
    pd_.add_argument("--quote", default="USDT")
    pd_.add_argument("--include-leveraged", action="store_true")
    pd_.add_argument("--no-verify", action="store_true", help="skip checksum verification (faster, unsafe)")
    pd_.add_argument("--limit", type=int, default=None, help="download only the first N symbols (smoke test)")
    pd_.add_argument("--symbols", nargs="+", default=None, help="explicit symbols instead of the crawl")
    pd_.add_argument("--out", default=BINANCE_DATA)

    pa = sub.add_parser("audit", help="survivorship partition + dead-coin presence guard")
    pa.add_argument("--quote", default="USDT")
    pa.add_argument("--out", default=BINANCE_DATA)

    a = p.parse_args()

    if a.cmd == "crawl":
        res = crawl_archive_symbols(a.quote, a.include_leveraged)
        write_universe(res, a.out)
    elif a.cmd == "snapshot":
        snapshot_exchange_info(a.out, a.quote)
    elif a.cmd == "download":
        if a.symbols:
            syms = a.symbols
        else:
            syms = crawl_archive_symbols(a.quote, a.include_leveraged)["symbols"]
        if a.limit:
            syms = syms[:a.limit]
        download_universe(syms, a.out, a.interval, a.start, a.end, verify=not a.no_verify)
    elif a.cmd == "audit":
        uni = crawl_archive_symbols(a.quote, verbose=False)["symbols"]
        active, taken, snap_path = load_latest_snapshot(a.out)
        if active is None:
            print("no dated snapshot found; run `acquire_vision.py snapshot` first.")
            active = []
        else:
            print(f"using snapshot from {taken} ({snap_path})")
        part = partition_survivorship(uni, active)
        print(f"survivorship: {part['n_universe']} universe, {part['n_active']} active, "
              f"{part['n_delisted']} delisted ({part['delisted_share']:.1%} dead)")
        audit_dead_coins(uni, on_disk_dir=a.out, interval="1h")


if __name__ == "__main__":
    main()
