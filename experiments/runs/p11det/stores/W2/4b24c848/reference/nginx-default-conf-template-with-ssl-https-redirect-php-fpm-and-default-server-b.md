---
name: nginx-default-conf-template-with-ssl-https-redirect-php-fpm-and-default-server-b
abstract: "Nginx default.conf.template with SSL, HTTPS redirect, PHP-FPM, and default server block"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-08-13
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

## default.conf.template

Nginx configuration template for virtual host with Let's Encrypt SSL, HTTPS redirect, PHP-FPM, and default server block.

### Default server block
Catches all requests not matching the virtual host and returns 444 (connection closed without response):
```
server {
  listen 80 default_server;
  listen [::]:80 default_server;
  server_name _;
  return 444;
}
```

### HTTP redirect to HTTPS
```
server {
  listen 80;
  listen [::]:80;
  server_name ${NGINX_HOST};
  return 301 https://${NGINX_HOST}$request_uri;
}
```

### HTTPS with PHP-FPM
```
server {
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  server_name ${NGINX_HOST};
  root /app;

  ssl_certificate /etc/nginx/ssl/example.com.crt;
  ssl_certificate_key /etc/nginx/ssl/example.com.key;
  include /etc/nginx/ssl/letsencrypt/options-ssl-nginx.conf;
  ssl_dhparam /etc/nginx/ssl/letsencrypt/ssl-dhparams.pem;

  location / {
    try_files $uri $uri/ /index.php$is_args$args;
  }

  location ~ \.php$ {
    try_files $uri =404;
    fastcgi_pass php:9000;
    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    include fastcgi_params;
  }
}
```

The `${NGINX_HOST}` variable is replaced at runtime via envsubst from the NGINX_HOST environment variable in docker-compose.yml.
