# R/alpaca.R — direct REST layer for Alpaca, no third-party Alpaca package.
#
# Why this exists: AlpacaforR breaks on R >= 4.3 (length-2 `&&`, deprecated
# purrr internals). This module talks to the Alpaca REST API directly with
# httr2, so it depends only on maintained, current packages and you can read
# every line of what it does.
#
# It reads the same keys your shell scripts and the Python layer use, so one
# set of secrets serves the whole repo. Source it once:
#
#     source("R/alpaca.R")
#
# Then: alpaca_account(); alpaca_paper_buy("AAPL", notional = 10)

# Dependencies. Installed by the QUICKSTART setup chunk if missing.
suppressMessages({
  library(httr2)
  library(jsonlite)
})

# ---- Configuration ---------------------------------------------------------

# Read a key from the environment, trying the repo-standard name first and the
# older AlpacaforR name second, so an existing .Renviron keeps working.
.alpaca_key <- function() {
  k <- Sys.getenv("ALPACA_API_KEY", "")
  if (k == "") k <- Sys.getenv("APCA-PAPER-KEY", "")
  k
}
.alpaca_secret <- function() {
  s <- Sys.getenv("ALPACA_API_SECRET", "")
  if (s == "") s <- Sys.getenv("APCA-PAPER-SECRET", "")
  s
}

# Settings in one place. Paper unless ALPACA_BASE_URL points at the live host.
alpaca_config <- function() {
  key <- .alpaca_key()
  secret <- .alpaca_secret()
  if (key == "" || secret == "") {
    stop(
      "Alpaca keys not found. Set them in your .Renviron, then restart R:\n",
      "  ALPACA_API_KEY=...\n  ALPACA_API_SECRET=...\n",
      "(The older APCA-PAPER-KEY / APCA-PAPER-SECRET names also work.)",
      call. = FALSE
    )
  }
  base <- Sys.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
  list(
    key = key,
    secret = secret,
    base_url = base,
    data_url = Sys.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets"),
    is_paper = grepl("paper", base, fixed = TRUE)
  )
}

# The one money switch, identical in spirit to the Python layer.
# TRUE only when LIVE_TRADING is exactly the string "true".
live_trading_enabled <- function() {
  identical(Sys.getenv("LIVE_TRADING", "false"), "true")
}

# ---- Core request ----------------------------------------------------------

# Build, send, and parse one Alpaca call. Returns parsed JSON as an R list.
# On an HTTP error it stops with Alpaca's own message rather than a raw dump.
.alpaca_call <- function(method, path, body = NULL, host = c("trading", "data")) {
  host <- match.arg(host)
  cfg <- alpaca_config()
  base <- if (host == "data") cfg$data_url else cfg$base_url

  req <- request(base) |>
    req_url_path_append(path) |>
    req_method(method) |>
    req_headers(
      "APCA-API-KEY-ID" = cfg$key,
      "APCA-API-SECRET-KEY" = cfg$secret,
      "Accept" = "application/json"
    )
  if (!is.null(body)) req <- req_body_json(req, body)  # scalars auto-unboxed

  resp <- req |>
    req_error(is_error = function(r) FALSE) |>   # we handle status ourselves
    req_perform()

  status <- resp_status(resp)
  parsed <- tryCatch(resp_body_json(resp, simplifyVector = TRUE),
                     error = function(e) NULL)

  if (status < 200 || status >= 300) {
    msg <- if (!is.null(parsed$message)) parsed$message else resp_body_string(resp)
    stop(sprintf("Alpaca HTTP %d: %s", status, msg), call. = FALSE)
  }
  parsed
}

# ---- Reads -----------------------------------------------------------------

alpaca_clock <- function() .alpaca_call("GET", "/v2/clock")

alpaca_account <- function() {
  a <- .alpaca_call("GET", "/v2/account")
  data.frame(
    account_number = a$account_number,
    status = a$status,
    currency = a$currency,
    cash = a$cash,
    equity = a$equity,
    buying_power = a$buying_power,
    paper = alpaca_config()$is_paper,
    stringsAsFactors = FALSE
  )
}

alpaca_positions <- function() {
  p <- .alpaca_call("GET", "/v2/positions")
  if (length(p) == 0) return(data.frame())
  p[, intersect(c("symbol", "qty", "avg_entry_price", "market_value",
                  "unrealized_pl"), names(p)), drop = FALSE]
}

alpaca_orders <- function(status = "all", limit = 20) {
  o <- .alpaca_call("GET", sprintf("/v2/orders?status=%s&limit=%d", status, limit))
  if (length(o) == 0) return(data.frame())
  o[, intersect(c("symbol", "side", "qty", "notional", "type", "status",
                  "submitted_at"), names(o)), drop = FALSE]
}

# ---- Order -----------------------------------------------------------------

# Buy `notional` dollars of `symbol` at market (fractional shares allowed).
# Paper money, so it is not gated. A live account (not available from Canada
# today) is refused unless LIVE_TRADING == "true".
alpaca_paper_buy <- function(symbol, notional, side = "buy") {
  cfg <- alpaca_config()
  if (!cfg$is_paper && !live_trading_enabled()) {
    stop("Refusing a live Alpaca order: base URL is not the paper host and ",
         "LIVE_TRADING is not 'true'.", call. = FALSE)
  }
  body <- list(
    symbol = symbol,
    notional = round(as.numeric(notional), 2),
    side = side,
    type = "market",
    time_in_force = "day"
  )
  o <- .alpaca_call("POST", "/v2/orders", body = body)
  list(id = o$id, symbol = o$symbol, side = o$side,
       notional = o$notional, status = o$status, submitted_at = o$submitted_at)
}
