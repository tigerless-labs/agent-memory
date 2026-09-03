---
name: denti-ai-hygenius-chat-dialog-interface-with-sender-receiver-messages
abstract: "Denti.AI Hygenius: chat dialog interface with sender/receiver messages"
type: fact
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2022-09-24
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Built a chat interface for Denti.AI Hygenius featuring:
- Sender and receiver message bubbles with different background colors (sender: teal #02cd8f, receiver: gray #E0E0E0)
- Chat container with white background (rgb(255, 255, 255, 0.9)), padding, border-radius, and shadow
- Body background color: #e8e8e8
- Font: DM Sans
- Center-aligned layout
- Icons planned for each side of messages (via CSS pseudo-elements)
- Mobile responsive with media queries for screens < 600px

Responsive approach: width 80% (max 500px) on desktop, 100% on mobile.
