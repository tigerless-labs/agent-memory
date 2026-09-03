---
created: 2026-09-02T21:25:41.784114233Z
updated: 2026-09-02T21:25:41.784114233Z
weight: 1.0
last_accessed: 2026-09-02T21:25:41.784114233Z
access_count: 0
pinned: false
links: []
abstract: Basic HTML5 webpage structure with semantic elements (header, nav, main, section, footer) and corresponding CSS styling — includes typography, colors (#333,
---

## HTML/CSS Basic Page Structure

**Semantic HTML5 Structure**

```html
<header>               <!-- top section with title/navigation -->
  <h1>Title</h1>
  <nav>                <!-- navigation menu -->
    <ul>
      <li><a href="#">Home</a></li>
      <li><a href="#">About</a></li>
      <li><a href="#">Contact</a></li>
    </ul>
  </nav>
</header>

<main>                 <!-- main content container -->
  <section>            <!-- content section -->
    <h2>Section Title</h2>
    <p>Content text</p>
  </section>
</main>

<footer>                <!-- bottom section -->
  <p>&copy; 2023 Site Name</p>
</footer>
```

**Corresponding CSS Styling**

```css
body {
  font-family: Arial, sans-serif;
  background-color: #f0f0f0;  /* light gray background */
}

header {
  background-color: #333;      /* dark gray header */
  color: #fff;                 /* white text */
  padding: 20px;
}

nav ul {
  list-style-type: none;
  margin: 0;
  padding: 0;
}

nav li {
  display: inline-block;
  margin-right: 20px;
}

nav a {
  color: #fff;
  text-decoration: none;
}

main {
  max-width: 800px;           /* limit content width */
  margin: 0 auto;             /* center horizontally */
  padding: 20px;
}

section {
  margin-bottom: 30px;
  border-bottom: 1px solid #ccc;  /* divider */
  padding-bottom: 20px;
}

footer {
  background-color: #333;
  color: #fff;
  padding: 10px;
  text-align: center;
}
```

**Key Styling Patterns**
- Dark header/footer (#333) with white text for contrast
- Light page background (#f0f0f0)
- Main content constrained to 800px max-width and centered
- Inline-block nav items for horizontal menu
- Border dividers between sections