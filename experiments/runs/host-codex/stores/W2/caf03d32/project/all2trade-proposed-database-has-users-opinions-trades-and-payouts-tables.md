---
name: all2trade-proposed-database-has-users-opinions-trades-and-payouts-tables
abstract: "All2Trade proposed database has Users, Opinions, Trades, and Payouts tables"
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

Proposed schema:\n\n- Users: id (primary key, auto-increment), username (unique), password (hashed), email, first_name, last_name.\n- Opinions: id (primary key, auto-increment), user_id (foreign key), currency, trend (up/down/neutral), timestamp.\n- Trades: id (primary key, auto-increment), currency, trend (up/down/neutral), buy_price, sell_price, profit, timestamp.\n- Payouts: id (primary key, auto-increment), user_id (foreign key), amount, timestamp.\n\nThis was presented as an example subject to adjustment for application requirements.
