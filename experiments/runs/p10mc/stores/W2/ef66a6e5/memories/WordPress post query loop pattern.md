---
created: 2026-09-02T23:37:48.079426885Z
updated: 2026-09-02T23:37:48.079426885Z
weight: 1.0
last_accessed: 2026-09-02T23:37:48.079426885Z
access_count: 0
pinned: false
links: []
abstract: WordPress WP_Query post loop — query posts by type, display with permalink, thumbnail, categories, excerpt, author; reset postdata after loop
---

## WordPress Post Query Loop Pattern

Uses `WP_Query` class to query posts and loop through results with WordPress template tags.

```php
<ul class="post-list">
  <?php 
  $args = array(
    'post_type' => 'post',
    'posts_per_page' => -1
  );
  $query = new WP_Query( $args );
  while ( $query->have_posts() ) : $query->the_post(); 
  ?>
    <li class="post">
      <a href="<?php the_permalink(); ?>">
        <?php if ( has_post_thumbnail() ) : ?>
            <img src="<?php the_post_thumbnail_url(); ?>" alt="Post Image">
        <?php endif; ?>
        <ul class="categories">
          <?php the_category(); ?>
        </ul>
        <p class="description"><?php the_excerpt(); ?></p>
        <p class="author">Author: <?php the_author(); ?></p>
      </a>
    </li>
  <?php endwhile; 
  wp_reset_postdata();
  ?>
</ul>
```

**WP_Query arguments:**
- `'post_type' => 'post'` — query type (post, page, custom post type)
- `'posts_per_page' => -1` — retrieve all posts

**Key template tags:**
- `the_permalink()` — post URL
- `has_post_thumbnail()` / `the_post_thumbnail_url()` — check and display featured image
- `the_category()` — display post categories
- `the_excerpt()` — post excerpt/description
- `the_author()` — author name

**Critical:** Always call `wp_reset_postdata()` after loop ends to reset `$post` global. Important when multiple queries on same page.