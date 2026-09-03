---
name: python-bitcoin-trading-bot-example-using-ccxt-library-with-stop-loss-and-take-pr
abstract: Python Bitcoin trading bot example using CCXT library with stop-loss and take-profit
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

Simple bot trading BTC/USD on Bitmex using ccxt library:

```python
import ccxt
import time

exchange = ccxt.bitmex()
symbol = 'BTC/USD'
amount = 1.0
stop_loss = 100
take_profit = 200

exchange.load_markets()

price = exchange.fetch_ticker(symbol)['last']

stop_loss_price = price - stop_loss
take_profit_price = price + take_profit

while True:
    price = exchange.fetch_ticker(symbol)['last']

    if price >= take_profit_price:
        exchange.create_order(symbol, 'market', 'sell', amount)
        print('Sold bitcoin at a profit!')
        break

    elif price <= stop_loss_price:
        exchange.create_order(symbol, 'market', 'sell', amount)
        print('Sold bitcoin at a loss :(')
        break

    else:
        time.sleep(60)
```

Uses ccxt library to connect to Bitmex exchange. Bot monitors BTC/USD price and sells when take-profit (price +200) or stop-loss (price -100) levels are reached.
