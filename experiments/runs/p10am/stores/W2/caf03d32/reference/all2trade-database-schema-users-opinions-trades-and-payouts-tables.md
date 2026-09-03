---
name: all2trade-database-schema-users-opinions-trades-and-payouts-tables
abstract: "All2Trade database schema: Users, Opinions, Trades, and Payouts tables"
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

**Database Schema for All2Trade**

**Users Table**
- id (PK, auto-increment): unique identifier
- username: unique username
- password: hashed password
- email: email address
- first_name: user first name
- last_name: user last name

**Opinions Table**
- id (PK, auto-increment): unique identifier
- user_id (FK): references Users.id
- currency: cryptocurrency being traded
- trend: predicted trend ('up', 'down', 'neutral')
- timestamp: when opinion was submitted

**Trades Table**
- id (PK, auto-increment): unique identifier
- currency: cryptocurrency traded
- trend: system prediction ('up', 'down', 'neutral')
- buy_price: entry price
- sell_price: exit price
- profit: profit generated
- timestamp: when trade was executed

**Payouts Table**
- id (PK, auto-increment): unique identifier
- user_id (FK): references Users.id
- amount: payout amount to user
- timestamp: when payout was issued
