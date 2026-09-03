---
name: all2trade-database-schema-design-with-users-opinions-trades-payouts-tables
abstract: "All2Trade database schema design with Users, Opinions, Trades, Payouts tables"
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

MySQL schema for All2Trade: Users (id, username, password, email, first_name, last_name); Opinions (id, user_id FK, currency, trend, timestamp); Trades (id, currency, trend, buy_price, sell_price, profit, timestamp); Payouts (id, user_id FK, amount, timestamp)
