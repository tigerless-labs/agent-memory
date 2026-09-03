---
name: web-scraping-techniques-rate-limiting-bypass-headless-browsers-vs-beautifulsoup
abstract: "Web scraping techniques: rate limiting bypass, headless browsers vs BeautifulSoup, tools and Python examples"
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-20
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Rate limiting avoidance: use proxy servers (different IPs), rotate IP pools, add request delays, use headless browsers.

Headless browsers (Chrome headless, PhantomJS, Selenium, Playwright): simulate real users, execute JavaScript, handle complex interactions, better debugging. Slower/more resource-intensive than BeautifulSoup.

Beautiful Soup: simple/quick scraping, lightweight, no JavaScript execution.

Python Selenium example with headless Chrome:
from selenium import webdriver
options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
driver = webdriver.Chrome(options=options)
driver.get('https://example.com')
content = driver.page_source
driver.quit()

Full pipeline: inspect HTML, write scraper (BeautifulSoup/Scrapy for static, Selenium/Playwright for dynamic), store in SQLite/CSV, schedule with cron/Task Scheduler, compare data for matches, email results.
