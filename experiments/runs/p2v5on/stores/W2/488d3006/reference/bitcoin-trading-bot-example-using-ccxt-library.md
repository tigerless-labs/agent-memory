---
name: bitcoin-trading-bot-example-using-ccxt-library
abstract: Bitcoin trading bot example using ccxt library
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

# Simple Bitcoin Trading Bot Example

Uses the ccxt library to connect to Bitmex exchange and trade bitcoin with stop-loss and take-profit orders.

## Parameters
- Exchange: Bitmex
- Symbol: BTC/USD
- Amount: 1.0 BTC
- Stop-loss: -$100 from entry price
- Take-profit: +$200 from entry price
- Price check interval: 60 seconds

## Python Code

```python
import ccxt
import time

# Set up the bot's trading parameters
exchange = ccxt.bitmex()
symbol = "BTC/USD"
amount = 1.0
stop_loss = 100
take_profit = 200

# Connect to the exchange
exchange.load_markets()

# Check the current price of bitcoin
price = exchange.fetch_ticker(symbol)["last"]

# Set the initial stop loss and take profit levels
stop_loss_price = price - stop_loss
take_profit_price = price + take_profit

while True:
    # Check the current price of bitcoin
    price = exchange.fetch_ticker(symbol)["last"]

    # If the price has reached the take profit level, sell the bitcoin
    if price >= take_profit_price:
        exchange.create_order(symbol, "market", "sell", amount)
        print("Sold bitcoin at a profit!")
        break

    # If the price has reached the stop loss level, sell the bitcoin
    elif price <= stop_loss_price:
        exchange.create_order(symbol, "market", "sell", amount)
        print("Sold bitcoin at a loss :(")
        break

    # Otherwise, wait for the price to move
    else:
        time.sleep(60)
```

## How It Works
1. Connects to Bitmex exchange using ccxt
2. Fetches current BTC/USD price
3. Sets stop-loss threshold at price - $100
4. Sets take-profit threshold at price + $200
5. Continuously monitors price every 60 seconds
6. Executes sell order (market order) when price reaches either threshold
7. Exits loop after sale
