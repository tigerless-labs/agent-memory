---
name: sharepoint-indexing-network-shares-without-full-ingestion-and-controlling-access
abstract: "SharePoint: indexing network shares without full ingestion and controlling access"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

## Creating links to network shares

In a SharePoint library or page:
1. Click New > select Link or Shortcut
2. Enter link name and URL in format: \\\\server_name\\folder_name
3. Click OK

Requires permissions to create links; network share must be accessible by users.

## Creating a content source

Via SharePoint Central Administration:
1. Manage Service Applications > Search Service Application
2. Content Sources (under Crawling) > New Content Source
3. Enter content source name
4. Select content type (SharePoint sites, Web sites, etc.)
5. Set Start Addresses as: \\\\server_name\\folder_name
6. Configure crawl settings and schedule
7. Click OK

SharePoint crawls and indexes the network share per schedule. Requires permissions to create content sources; network share must be accessible to SharePoint crawlers.

## Controlling access to indexed content

Methods to restrict access for unauthorized users:

- SharePoint permissions: Search results respect the searcher's permissions; set proper permissions to restrict content visibility
- Item-level permissions: Set permissions on individual items within libraries/lists
- Result Sources: Define filtering rules for search results based on criteria
- Information Rights Management (IRM): Encrypt data and apply usage rights to encryption keys rather than data itself
- Secure Store Service (SSS): Store and map credentials for external systems; map to specific users/groups
