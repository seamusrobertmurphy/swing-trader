# trade-log.md — append-only trade ledger

Every fill goes here. Newest at the bottom. Never edit or remove entries.

Each entry uses this block:

```
## YYYY-MM-DD HH:MM CT — <BUY|SELL> <SYMBOL>

- Order ID: <Alpaca order id>
- Side: <BUY|SELL>
- Quantity: <int>
- Fill price: <$>
- Notional: <$>
- Position size at entry: <% of equity>
- Stops set: hard −7% at <$>, trailing 10% from peak
- Rationale: <two to four sentences. Cite the catalyst, the research entry, the strategy clause that authorises this trade.>
- Expected horizon: <weeks|months>
- Exit plan: <thesis break conditions, stop levels, take-profit thinking>
- Outcome (filled at close-out): <P&L $ and %, days held, reason for exit>
```

For sells, also reference the buy entry by date and price.

---

<!-- entries below this line -->
