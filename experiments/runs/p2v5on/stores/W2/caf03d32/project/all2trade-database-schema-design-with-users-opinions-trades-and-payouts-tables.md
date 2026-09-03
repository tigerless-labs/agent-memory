---
name: all2trade-database-schema-design-with-users-opinions-trades-and-payouts-tables
abstract: "All2Trade database schema design with Users, Opinions, Trades, and Payouts tables"
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

## All2Trade Database Schema

### Users Table
- **id** (PK, auto-increment): unique user identifier
- **username**: unique username
- **password**: hashed password
- **email**: user email address
- **first_name**: user first name
- **last_name**: user last name

### Opinions Table
- **id** (PK, auto-increment): unique opinion identifier
- **user_id** (FK): references Users.id
- **currency**: cryptocurrency symbol
- **trend**: predicted trend (e.g., 'up', 'down', 'neutral')
- **timestamp**: when opinion was submitted

### Trades Table
- **id** (PK, auto-increment): unique trade identifier
- **currency**: cryptocurrency symbol
- **trend**: system-predicted trend (user opinions + ML model)
- **buy_price**: entry price
- **sell_price**: exit price
- **profit**: profit/loss amount
- **timestamp**: when trade was executed

### Payouts Table
- **id** (PK, auto-increment): unique payout identifier
- **user_id** (FK): references Users.id
- **amount**: payout amount
- **timestamp**: when payout was issued
