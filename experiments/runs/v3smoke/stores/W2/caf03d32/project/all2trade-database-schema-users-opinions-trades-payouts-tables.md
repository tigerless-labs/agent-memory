---
name: all2trade-database-schema-users-opinions-trades-payouts-tables
abstract: "All2Trade database schema: Users, Opinions, Trades, Payouts tables"
type: fact
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

**Users Table**
- id (PK, auto-increment): unique identifier
- username: unique username
- password: hashed
- email: user email
- first_name, last_name: user names

**Opinions Table**
- id (PK, auto-increment)
- user_id (FK): which user submitted
- currency: cryptocurrency symbol
- trend: prediction value ("up", "down", "neutral")
- timestamp: when opinion was submitted

**Trades Table**
- id (PK, auto-increment)
- currency: cryptocurrency traded
- trend: system's predicted trend
- buy_price: entry price
- sell_price: exit price
- profit: trade profit amount
- timestamp: when trade executed

**Payouts Table**
- id (PK, auto-increment)
- user_id (FK): recipient user
- amount: payout amount
- timestamp: when payout was made

This schema enables tracking of opinion contributions, trade execution, and revenue distribution to users.
