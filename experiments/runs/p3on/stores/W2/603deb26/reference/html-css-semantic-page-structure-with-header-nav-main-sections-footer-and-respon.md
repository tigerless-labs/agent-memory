---
name: html-css-semantic-page-structure-with-header-nav-main-sections-footer-and-respon
abstract: "HTML/CSS: semantic page structure with header nav, main sections, footer, and responsive styling"
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

Example of a well-structured HTML page with semantic elements and corresponding CSS styling.

HTML structure:
```html
<!DOCTYPE html>
<html>
<head>
  <title>My Web Page</title>
  <link rel="stylesheet" type="text/css" href="styles.css">
</head>
<body>
  <header>
    <h1>Welcome to My Web Page</h1>
    <nav>
      <ul>
        <li><a href="#">Home</a></li>
        <li><a href="#">About</a></li>
        <li><a href="#">Contact</a></li>
      </ul>
    </nav>
  </header>
  <main>
    <section>
      <h2>About Me</h2>
      <p>Lorem ipsum dolor sit amet...</p>
    </section>
    <section>
      <h2>My Hobbies</h2>
      <ul>
        <li>Reading</li>
        <li>Hiking</li>
        <li>Playing video games</li>
      </ul>
    </section>
  </main>
  <footer>
    <p>&copy; 2023 My Web Page</p>
  </footer>
</body>
</html>
```

Key CSS styling patterns:
- Font family and base background color on body
- Dark header (#333) with white text
- Navigation list displayed inline-block with spacing
- Main content container with max-width of 800px, centered with margin: 0 auto
- Sections separated with border-bottom and padding
- Footer matching header style with text-align center
- Semantic HTML elements (header, nav, main, section, footer) for accessibility and SEO
