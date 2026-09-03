---
name: all2trade-database-schema-design
abstract: All2Trade database schema design
type: procedure
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

Recommended MySQL database structure for All2Trade platform.

**Users Table**:
- id (primary key, auto-increment)
- username (unique)
- password (hashed)
- email
- first_name
- last_name

**Opinions Table**:
- id (primary key, auto-increment)
- user_id (foreign key to Users)
- currency (target currency)
- trend (predicted trend: "up", "down", "neutral")
- timestamp (opinion submission time)

**Trades Table**:
- id (primary key, auto-increment)
- currency (traded currency)
- trend (system-predicted trend)
- buy_price (purchase price)
- sell_price (sale price)
- profit (generated profit)
- timestamp (trade execution time)

**Payouts Table**:
- id (primary key, auto-increment)
- user_id (foreign key to Users)
- amount (payout amount)
- timestamp (payout time)

Note: This is a foundational schema that may be expanded based on specific requirements.
