---
created: 2026-09-02T23:23:50.671559885Z
updated: 2026-09-02T23:23:50.671559885Z
weight: 1.0
last_accessed: 2026-09-02T23:23:50.671559885Z
access_count: 0
pinned: false
links: []
abstract: SharePoint content sources for network share crawling — steps in Central Administration, Start Addresses format \\server_name\folder_name, requires crawler permissions to network share
---

## Creating Content Sources in SharePoint

To create a content source in SharePoint for indexing network shares:

1. Open SharePoint Central Administration website
2. Click "Manage service applications" (Application Management section)
3. Click "Search Service Application"
4. Click "Content Sources" (under Crawling section)
5. Click "New Content Source" button
6. Enter a name for the content source
7. Select content type (e.g., "SharePoint sites" or "Web sites")
8. Enter Start Addresses: `\\server_name\folder_name`
9. Configure Crawl settings and Crawl schedule as needed
10. Click OK

**Key Requirements:**
- SharePoint crawler must have permissions to access the network share
- Network share location must be accessible by SharePoint crawlers
- Content will be indexed and searchable in SharePoint search functionality
- Content remains on network share (not ingested)

**Result:**
SharePoint will crawl the network share according to the schedule and make content searchable while maintaining original access control.