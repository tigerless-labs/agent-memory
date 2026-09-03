---
name: bitcoin-trading-bot-example-code-ccxt-library-python
abstract: "Bitcoin trading bot example code (CCXT library, Python)"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Simple bot using ccxt library to trade BTC/USD on Bitmex exchange.

Key features:
- Connects to Bitmex via ccxt library
- Symbol: BTC/USD, Amount: 1.0
- Stop loss: 100 USD below entry
- Take profit: 200 USD above entry
- Polls current price every 60 seconds
- Exits on take profit or stop loss hit
- Uses market orders to buy/sell

Language: Python  
Library: ccxt  
Exchange: Bitmex  
Trading pair: BTC/USD
