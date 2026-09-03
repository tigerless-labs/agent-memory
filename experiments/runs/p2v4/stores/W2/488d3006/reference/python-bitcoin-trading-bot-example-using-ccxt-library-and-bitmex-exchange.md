---
name: python-bitcoin-trading-bot-example-using-ccxt-library-and-bitmex-exchange
abstract: Python Bitcoin trading bot example using ccxt library and Bitmex exchange
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

Simple bot connecting to Bitmex via ccxt library for BTC/USD trading with stop-loss and take-profit orders.

Uses: ccxt library for exchange connectivity, Bitmex exchange, BTC/USD pair, market orders with fixed stop-loss (100 USD below entry) and take-profit (200 USD above entry) levels. Loops every 60 seconds checking current price against targets.

Key parameters: amount=1.0 BTC, stop_loss=100, take_profit=200.

Example implementation demonstrating basic bot pattern: fetch price, compare to thresholds, execute market orders, poll continuously.
