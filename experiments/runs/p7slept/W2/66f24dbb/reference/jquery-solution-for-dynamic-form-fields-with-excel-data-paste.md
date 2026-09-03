---
name: jquery-solution-for-dynamic-form-fields-with-excel-data-paste
abstract: jQuery solution for dynamic form fields with Excel data paste
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-22
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

jQuery implementation for side-by-side input fields (MID, Descriptor) with cloning and Excel paste support. Features: Add Row button clones field pairs. Paste tab-separated, newline-delimited Excel data auto-populates multiple rows. Uses jQuery .clone(true), .find(), .eq(), .insertAfter(). Parses clipboard with event.originalEvent.clipboardData.getData('text'), splits by tab and newline. Attach paste listener to .MID class, call preventDefault, loop rows, create cloned containers with values from parsed cells. Pattern: wrap in document.ready, include jQuery 3.6.0+ from CDN.
