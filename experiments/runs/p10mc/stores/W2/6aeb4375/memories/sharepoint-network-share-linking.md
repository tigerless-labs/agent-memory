---
created: 2026-09-02T23:23:45.889366162Z
updated: 2026-09-02T23:23:45.889366162Z
weight: 1.0
last_accessed: 2026-09-02T23:23:45.889366162Z
access_count: 0
pinned: false
links: []
abstract: SharePoint linking network shares — create shortcuts/links in libraries, URL format \\server_name\folder_name, requires permissions and network accessibility
---

## Creating Links to Network Shares in SharePoint

To link a network share location in a SharePoint library or page:

1. Navigate to the target library or page
2. Click "New" → select "Link" or "Shortcut"
3. Enter a name for the link
4. Enter the network share URL in format: `\\server_name\folder_name`
5. Click "OK" to save

**Requirements:**
- User must have permissions to create links/shortcuts on the library/page
- Network share location must be accessible to the user
- Content remains stored on the network share, not ingested into SharePoint
- Can be indexed by SharePoint Search without ingesting content