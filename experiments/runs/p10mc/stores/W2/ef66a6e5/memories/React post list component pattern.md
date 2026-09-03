---
created: 2026-09-02T23:37:35.169166861Z
updated: 2026-09-02T23:37:35.169166861Z
weight: 1.0
last_accessed: 2026-09-02T23:37:35.169166861Z
access_count: 0
pinned: false
links: []
abstract: React Post and PostList components — displays posts with image, categories, description, author, link wrapped in anchor tag
---

## React Post List Component

Two-component pattern: `Post` renders individual post item, `PostList` maps array of posts to Post components.

```javascript
import React from 'react';

const Post = ({ imageUrl, categories, description, author, link }) => {
  return (
    <li className="post">
      <a href={link}>
        <img src={imageUrl} alt="Post Image" />
        <ul className="categories">
          {categories.map((category, index) => (
            <li key={index}>{category}</li>
          ))}
        </ul>
        <p className="description">{description}</p>
        <p className="author">Author: {author}</p>
      </a>
    </li>
  );
};

const PostList = ({ posts }) => {
  return (
    <ul className="post-list">
      {posts.map((post, index) => (
        <Post key={index} {...post} />
      ))}
    </ul>
  );
};

export default PostList;
```

**Props:** `Post` takes `imageUrl`, `categories` (array), `description`, `author`, `link`. `PostList` takes `posts` (array of post objects).

**Key points:**
- className instead of class (React)
- Entire post wrapped in anchor tag (no separate "Read More" link)
- Categories rendered as array map
- Use spread operator (`{...post}`) to pass props to Post component