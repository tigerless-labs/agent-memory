---
name: sharepoint-network-share-linking-and-indexed-content-access-control-techniques
abstract: SharePoint network share linking and indexed content access control techniques
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

## Creating links to network shares

Use format: `\\server_name\folder_name`

## Indexing network shares

Create content source in SharePoint Search service:
- Central Administration → Manage service applications → Search Service Application  
- Click Content Sources → New Content Source
- Set Start Addresses to network share path
- Configure crawl settings and schedule

## Controlling access to indexed content

Several methods:
1. **SharePoint permissions** - search results respect user permissions
2. **Item-level permissions** - control access to specific items
3. **Result Sources** - filter search results based on criteria
4. **Information Rights Management (IRM)** - encrypt data, apply usage rights to encryption keys
5. **Secure Store Service (SSS)** - store and map credentials for external systems

Default approach: SharePoint search results respect the user's permission level.
