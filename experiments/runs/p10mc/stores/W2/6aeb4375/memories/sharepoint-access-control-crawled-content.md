---
created: 2026-09-02T23:24:00.363261359Z
updated: 2026-09-02T23:24:00.363261359Z
weight: 1.0
last_accessed: 2026-09-02T23:24:00.363261359Z
access_count: 0
pinned: false
links: []
abstract: SharePoint search security for crawled content — restrict access via permissions, item-level permissions, Result Sources, IRM, or Secure Store Service
---

## Controlling Access to Crawled and Indexed Content in SharePoint

To prevent unauthorized users from accessing crawled/indexed content:

### 1. SharePoint Permissions
SharePoint search respects user permissions. Search results are filtered based on the user's access level. Set proper permissions to restrict content visibility.

### 2. Item-Level Permissions
Set permissions on individual items within libraries/lists for granular control. Works even when parent library has broader permissions.

### 3. Result Sources
Define rules for filtering search results. Create result sources that filter content based on criteria and can exclude content from specific users' search results.

### 4. SharePoint Information Rights Management (IRM)
Protect sensitive information with usage rights and permissions. Encrypts data and applies permissions to encryption keys. Ensures protection regardless of download/sharing.

### 5. Secure Store Service (SSS)
Stores and maps credentials (account names, passwords). Used to connect to external systems. Maps credentials to specific users or groups for controlling access to external data sources.

**Key Principle:**
SharePoint search results are automatically filtered by user permissions, so proper permission configuration is the primary security mechanism for indexed content.