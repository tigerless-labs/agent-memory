---
name: all2trade-database-schema-for-user-opinions-trades-and-payouts
abstract: "All2Trade database schema for user opinions, trades, and payouts"
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

## Core tables:\n\n**Users**\n- id (PK, auto-increment)\n- username (unique)\n- password (hashed)\n- email\n- first_name, last_name\n\n**Opinions**\n- id (PK, auto-increment)\n- user_id (FK)\n- currency\n- trend ("up" | "down" | "neutral")\n- timestamp\n\n**Trades**\n- id (PK, auto-increment)\n- currency\n- trend ("up" | "down" | "neutral")\n- buy_price\n- sell_price\n- profit (calculated)\n- timestamp\n\n**Payouts**\n- id (PK, auto-increment)\n- user_id (FK)\n- amount\n- timestamp\n\nNote: This is a starting schema; adjust based on specific requirements (e.g., tracking which users influenced which trades, model predictions table, etc.)
