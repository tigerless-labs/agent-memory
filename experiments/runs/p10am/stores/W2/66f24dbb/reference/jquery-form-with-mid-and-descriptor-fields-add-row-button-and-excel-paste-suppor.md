---
name: jquery-form-with-mid-and-descriptor-fields-add-row-button-and-excel-paste-suppor
abstract: "jQuery form with MID and Descriptor fields, add row button, and Excel paste support"
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

Dynamic row form with jQuery.

User built an HTML form that allows:
- Two side-by-side input fields (MID and Descriptor)  
- Add Row button to clone input pairs
- Paste Excel data (tab-separated columns) to auto-populate and create rows

Implementation uses jQuery with:
- Input containers with class selectors (.MID, .Descriptor)
- Clone the last input container for new rows
- Paste event handler that splits on newline for rows, tab for columns
- Creates new input container for each 2-column pasted row

Common use: bulk data entry from Excel, inventory forms
