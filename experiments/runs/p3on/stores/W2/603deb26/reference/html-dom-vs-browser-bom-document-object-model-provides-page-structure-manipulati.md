---
name: html-dom-vs-browser-bom-document-object-model-provides-page-structure-manipulati
abstract: "HTML DOM vs Browser BOM: Document Object Model provides page structure manipulation, Browser Object Model provides browser feature access"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-08-11
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Two distinct but complementary programming interfaces in web development:

**HTML DOM (Document Object Model)**
- Programming interface for manipulating page content and structure
- Represents web page as hierarchical tree of objects
- Each object corresponds to HTML element, attribute, or text node
- Allows dynamic modification of page contents
- Enables response to user interactions
- Creates dynamic effects and animations
- Examples: adding/removing elements, modifying content

**Browser BOM (Browser Object Model)**
- Programming interface for manipulating browser behavior and appearance
- Provides access to browser-specific features
- Includes: history, location, navigation properties
- Enables: creating pop-up windows, displaying dialogs, manipulating status bar
- Examples: navigating to different URL, displaying pop-ups on click

**Key Difference**
- DOM = page content/structure
- BOM = browser itself and its features

**Common Use Case**
Both work together to create interactive applications. Example: custom login form that uses DOM to validate input and display error messages, uses BOM to navigate to new page on successful submission.
