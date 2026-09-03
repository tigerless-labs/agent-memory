---
name: sharepoint-indexing-network-shares-without-ingestion
abstract: "SharePoint: indexing network shares without ingestion"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-07-12
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Approach to integrate network share content into SharePoint search while maintaining access controls.

**Methods to index without ingesting:**
- Create links/shortcuts to network share locations (format: `\\server_name\folder_name`)
- Configure content source in Search Service Application to crawl network share
- SharePoint crawlers index content, but original stays on network share

**Access control for indexed content:**
1. **SharePoint permissions** – search results filtered by user's existing permissions
2. **Item-level permissions** – restrict specific files/folders within library
3. **Result Sources** – filter search results by criteria, hide content from unauthorized users
4. **Information Rights Management (IRM)** – encrypt files, apply usage rights to keys rather than data
5. **Secure Store Service (SSS)** – map credentials for external system access

**Configuration requirements:**
- Network share must be accessible to SharePoint crawlers
- Admin permissions needed to create content sources
- User needs permissions to access shared location

**Original context:** Asked 2023-07-12 about preventing unauthorized access to crawled/indexed content from network shares.
