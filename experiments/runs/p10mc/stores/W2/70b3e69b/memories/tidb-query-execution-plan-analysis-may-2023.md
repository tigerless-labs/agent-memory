---
created: 2026-09-02T23:45:08.551307321Z
updated: 2026-09-02T23:45:08.551307321Z
weight: 1.0
last_accessed: 2026-09-02T23:45:08.551307321Z
access_count: 0
pinned: false
links: []
abstract: May 22 2023 TiDB execution plan analysis for bbbb table, f_bookmark index scan, 6.09s execution time, 1M rows, index range scan with Selection filter on encoded bookmark value
---

## TiDB Execution Plan Analysis (May 22, 2023)

User analyzed a TiDB query execution plan with these characteristics:

**Query Structure:**
- Database: `aaaa_feed_bbbbs`
- Table: `bbbb`
- Primary index scanned: `f_bookmark(f_bookmark)`
- Operation type: IndexRangeScan with Selection filter

**Performance Metrics:**
- Total execution time: **6.09 seconds**
- Estimated rows returned: **1,000,000**
- Memory used: 675.6 KB
- Concurrency: 5

**Execution Plan Operations:**
1. **Projection_7** — root operation selecting columns (f_bookmark, f_bbbb_component_type, f_bbbb_options, f_id, f_label, f_product_bbbb_type, f_title)
2. **Limit_9** — limiting results, offset:0
3. **IndexRangeScan_14** — scans f_bookmark index, cop[tikv] operation
4. **Selection_16** — filters on `f_bookmark = "[base64-encoded value starting with Y2JVSG81V2sxcmNHRlpWM1J5...]"`
5. **TableRowIDScan_15** — fetches table rows by ID

**Performance Breakdown:**
- Index task total: 6.08s (fetch_handle: 373ms, build: 339µs, wait: 5.71s)
- Table task: 30s total, 253 rows processed, concurrency: 5
- Processed keys: 5,191,584 (index) + 5,006,611 (table) 
- Total data read: ~1.17 GB via RocksDB blocks
- RPC calls: 1,442 to TiKV coordinators
- Coprocessor cache hit ratio: 0.00%

**Key Observations:**
- High wait time (5.71s) in index task suggests potential resource contention
- No coprocessor cache hits indicate either first-time query or cache eviction
- Significant gap between estimated rows (1M) and actual processing suggests range predicate may not be selective enough
- Table read size (1.17 GB) relative to returned rows suggests large column values or inefficient filtering

## Interpretation for Optimization
The query shows potential bottlenecks in the table fetch phase with high RPC count and network roundtrips. The encoded bookmark value in the Selection filter suggests this might be a pagination or cursor-based query. Consider:
- Index selectivity on f_bookmark
- Column width optimization (selected columns are numerous)
- Predicate pushdown effectiveness