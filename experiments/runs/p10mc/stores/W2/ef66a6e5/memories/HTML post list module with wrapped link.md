---
created: 2026-09-02T23:37:59.458630580Z
updated: 2026-09-02T23:37:59.458630580Z
weight: 1.0
last_accessed: 2026-09-02T23:37:59.458630580Z
access_count: 0
pinned: false
links: []
abstract: Basic HTML post list structure — ul.post-list containing li.post items with anchor wrapping image, categories, description, author
---

## HTML Post List Module

Foundational HTML structure for a list of posts where entire post content is wrapped in an anchor link.

```html
<ul class="post-list">
  <li class="post">
    <a href="link-url">
      <img src="image-url" alt="Post Image">
      <ul class="categories">
        <li>Category 1</li>
        <li>Category 2</li>
        <li>Category 3</li>
      </ul>
      <p class="description">Post description text here...</p>
      <p class="author">Author: John Doe</p>
    </a>
  </li>
  <li class="post">
    <a href="link-url">
      <img src="image-url" alt="Post Image">
      <ul class="categories">
        <li>Category 1</li>
        <li>Category 2</li>
        <li>Category 3</li>
      </ul>
      <p class="description">Post description text here...</p>
      <p class="author">Author: Jane Doe</p>
    </a>
  </li>
</ul>
```

**Structure:**
- `ul.post-list` — container for all posts
- `li.post` — individual post item
- `a` wraps entire post content (no separate "Read More" link)
- `img` — post image
- `ul.categories` — nested list of categories
- `p.description` — post excerpt/summary
- `p.author` — author name

This serves as the base pattern for React and WordPress implementations.