---
created: 2026-09-03T01:17:31.727428191Z
updated: 2026-09-03T01:17:31.727428191Z
weight: 1.0
last_accessed: 2026-09-03T01:17:31.727428191Z
access_count: 0
pinned: false
links:
- headless-browser-web-scraping-automation
- web-scraping-rate-limiting-avoidance-techniques
abstract: May 2023 project scope - scrape real estate website daily, identify new listings matching criteria, email alerts. Architecture - inspect HTML, extract with BeautifulSoup or headless browser, store in SQLite/CSV, schedule with cron, compare data, send via SMTP. Rate limiting - use proxies, rotating IPs, delays, or headless browser.
---

## Project Brief
Scrape a real estate website once daily, filter new listings against user search criteria, send email with matches.

## Architecture
1. Inspect website HTML to identify relevant data elements
2. Write scraping script using Python with BeautifulSoup or headless browser
3. Store extracted data in SQLite database or CSV file
4. Schedule daily runs using cron (Linux) or Task Scheduler (Windows)
5. Compare today's data vs previous day; identify new listings matching search criteria
6. Send email via SMTP using Python smtplib

## Rate Limiting Mitigation
- Use proxy servers to route requests through different IPs
- Rotate through a pool of IP addresses
- Add delays between requests
- Use headless browser instead of direct server requests to appear like real user
- Respect website robots.txt and terms of use

## Tools Mentioned
- Headless browsers: Chrome headless mode, PhantomJS, HtmlUnit, Selenium WebDriver, Playwright
- Python libraries: BeautifulSoup (simple scraping), Selenium WebDriver (complex interactions, JS rendering)

## BeautifulSoup vs Headless Browser Tradeoff
- BeautifulSoup: lightweight, fast, good for static HTML scraping
- Headless browser: slower, more resource-intensive, handles JavaScript execution, form interactions, complex site logic