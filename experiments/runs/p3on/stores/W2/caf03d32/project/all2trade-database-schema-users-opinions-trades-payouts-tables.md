---
name: all2trade-database-schema-users-opinions-trades-payouts-tables
abstract: "All2Trade database schema: Users, Opinions, Trades, Payouts tables"
type: decision
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

**Users Table**:
- id (PK, auto-increment)
- username (unique)
- password (hashed)
- email
- first_name
- last_name

**Opinions Table**:
- id (PK, auto-increment)
- user_id (FK → Users)
- currency
- trend (up/down/neutral)
- timestamp

**Trades Table**:
- id (PK, auto-increment)
- currency
- trend (predicted by system)
- buy_price
- sell_price
- profit
- timestamp

**Payouts Table**:
- id (PK, auto-increment)
- user_id (FK → Users)
- amount
- timestamp

Schema tracks user opinions, all trades executed, profits generated, and revenue payouts to users.
