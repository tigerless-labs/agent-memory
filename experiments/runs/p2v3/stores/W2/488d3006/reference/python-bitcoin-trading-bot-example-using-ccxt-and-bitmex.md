---
name: python-bitcoin-trading-bot-example-using-ccxt-and-bitmex
abstract: Python Bitcoin trading bot example using ccxt and Bitmex
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-21
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

From 2023/05/21: A simple bot trading example in Python provided to the user:

**Libraries:** ccxt (cryptocurrency exchange trading library)

**Exchange:** Bitmex

**Key components:**
- Symbol: BTC/USD
- Amount: 1.0
- Stop loss: 100 (points)
- Take profit: 200 (points)

**Logic:**
- Fetches current Bitcoin price
- Sets stop-loss at (current price - 100)
- Sets take-profit at (current price + 200)
- Polls price every 60 seconds
- Sells at take-profit or stop-loss level

**Pattern:** Basic long position with fixed exit levels (incomplete code in conversation)

The code demonstrates a simple algorithmic trading pattern for educational purposes.
