---
name: initial-all2trade-mysql-schema-has-users-opinions-trades-and-payouts-tables
abstract: "Initial All2Trade MySQL schema has Users, Opinions, Trades, and Payouts tables"
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

Proposed initial schema:

- Users: id (primary key, auto-increment), username (unique), password (hashed), email, first_name, last_name.
- Opinions: id, user_id (foreign key), currency, trend ("up", "down", or "neutral"), timestamp.
- Trades: id, currency, trend predicted by the system, buy_price, sell_price, profit, timestamp.
- Payouts: id, user_id (foreign key), amount, timestamp.
