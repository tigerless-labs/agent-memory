---
created: 2026-09-02T23:37:53.917763618Z
updated: 2026-09-02T23:37:53.917763618Z
weight: 1.0
last_accessed: 2026-09-02T23:37:53.917763618Z
access_count: 0
pinned: false
links: []
abstract: ACF (Advanced Custom Fields) repeater pattern — have_rows, the_row, the_sub_field to loop and display post data from ACF repeater field
---

## WordPress ACF Repeater Post Pattern

Uses Advanced Custom Fields plugin functions to loop through a repeater field and display post data.

```php
<ul class="post-list">
  <?php while ( have_rows('posts') ) : the_row(); ?>
    <li class="post">
      <a href="<?php the_sub_field('link'); ?>">
        <img src="<?php the_sub_field('image'); ?>" alt="Post Image">
        <ul class="categories">
          <?php while ( have_rows('categories') ) : the_row(); ?>
            <li><?php the_sub_field('category'); ?></li>
          <?php endwhile; ?>
        </ul>
        <p class="description"><?php the_sub_field('description'); ?></p>
        <p class="author">Author: <?php the_sub_field('author'); ?></p>
      </a>
    </li>
  <?php endwhile; ?>
</ul>
```

**ACF Functions:**
- `have_rows('field_name')` — check if repeater field has rows
- `the_row()` — move to next row in repeater
- `the_sub_field('subfield_name')` — output value of subfield in current row

**Pattern:** Can nest repeaters (e.g., posts repeater containing categories repeater). Each `have_rows` creates its own loop context.

**Setup:** Create ACF repeater field named "posts" with subfields: link, image, description, author. For nested categories, add "categories" repeater subfield with "category" text subfield.