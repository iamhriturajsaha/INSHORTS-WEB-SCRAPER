import requests
import json
import time
import logging
import os
import re
from datetime import datetime
from typing import Optional

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Constants
CATEGORY_API = "https://inshorts.com/api/en/news"
TRENDING_API  = "https://inshorts.com/api/en/search/trending_topics/news"
WORKING_CATEGORIES  = ["top_stories"]
PAGES_PER_CATEGORY  = 5       # 5 pages × 10 articles = up to 50 articles
BONUS_SCROLL_PAGES  = 3       # extra pages from trending/scroll endpoint
ARTICLES_PER_PAGE   = 10
POLITE_DELAY    = 1.2         # seconds between requests (ethical scraping)
IMAGE_DELAY     = 0.5         # seconds between image downloads
REQUEST_TIMEOUT = 15          # seconds
OUTPUT_FILE   = "news_data.json"
IMAGES_FOLDER = "images"      # all downloaded images saved here
HEADERS = {
    # A real User-Agent header identifies the scraper politely
    # and prevents the server from blocking it as suspicious traffic.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://inshorts.com/en/read",
    "Origin":          "https://inshorts.com",
}

# HTTP utility
def fetch_json(url: str, params: Optional[dict] = None) -> Optional[dict]:
    """GET → parsed JSON. Returns None on any error (timeout, HTTP, network, JSON)."""
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        logger.error("Timeout: %s", url)
    except requests.exceptions.HTTPError as e:
        logger.error("HTTP %s error for: %s", e.response.status_code, url)
    except requests.exceptions.RequestException as e:
        logger.error("Network error — %s", e)
    except json.JSONDecodeError as e:
        logger.error("JSON decode error — %s", e)
    return None

# Image downloader
def sanitise_filename(text: str, max_len: int = 60) -> str:
    """Turn a headline into a safe filename slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
    return slug[:max_len]
def download_image(image_url: str, article_id: str, headline: str, folder: str) -> str:
    """
    Download the image at `image_url` and save it to `folder`.
    Returns the local file path on success, or empty string on failure.
    Missing images are handled gracefully — a warning is logged but scraping continues.
    """
    if not image_url:
        return ""
    os.makedirs(folder, exist_ok=True)
    # Derive extension from URL, default to .jpg
    ext = os.path.splitext(image_url.split("?")[0])[-1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"
    slug     = sanitise_filename(headline) or article_id
    filename = f"{slug}{ext}"
    filepath = os.path.join(folder, filename)
    # Skip if already downloaded
    if os.path.exists(filepath):
        return filepath
    try:
        r = requests.get(image_url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True)
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return filepath
    except requests.exceptions.RequestException as e:
        logger.warning("Could not download image for '%s': %s", headline[:40], e)
        return ""
    except IOError as e:
        logger.warning("Could not save image for '%s': %s", headline[:40], e)
        return ""

# Article parser
def parse_news_obj(obj: dict) -> Optional[dict]:
    """
    Map one raw API object to our clean output schema.
    API fields (from DevTools inspection of live XHR responses):
      hash         → unique article ID  (dedup key)
      title        → headline
      content      → 60-word summary
      author_name  → author
      created_at   → publish time as epoch milliseconds
      source_url   → link to the original full article  ("read more at…")
      image_url    → card thumbnail URL
    """
    if not obj:
        return None
    try:
        ts_ms = obj.get("created_at")
        published_at = (
            datetime.fromtimestamp(int(ts_ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
            if ts_ms else ""
        )
        headline = obj.get("title", "").strip()
        summary  = obj.get("content", "").strip()
        if not headline and not summary:
            return None
        return {
            "id":            obj.get("hash", ""),
            "headline":      headline,
            "summary":       summary,
            "author":        obj.get("author_name", "").strip(),
            "published_at":  published_at,
            "source_link":   obj.get("source_url", ""),
            "image_url":     obj.get("image_url", ""),
            "image_local":   "",   # filled in by download_all_images()
        }
    except Exception as e:
        logger.warning("Skipping malformed article: %s", e)
        return None
def extract_news_list(data: dict) -> tuple:
    """Return (news_list, next_cursor) from an API response."""
    payload   = data.get("data", {})
    news_list = payload.get("news_list", [])
    cursor    = payload.get("min_news_id") or payload.get("news_offset")
    return news_list, cursor

# Primary scraper — paginated category feed
def scrape_category_paginated(category: str, max_pages: int) -> list:
    """
    Fetch up to `max_pages` pages for one category using cursor-based pagination.
    Each page advances via the `news_offset` value returned in the prior response.
    """
    all_articles = []
    news_offset  = ""
    for page in range(1, max_pages + 1):
        params = {
            "category":          category,
            "max_limit":         str(ARTICLES_PER_PAGE),
            "include_card_data": "true",
            "news_offset":       news_offset,
        }
        data = fetch_json(CATEGORY_API, params=params)
        if not data:
            logger.warning("Category '%s' page %d failed — stopping.", category, page)
            break
        news_list, cursor = extract_news_list(data)
        if not news_list:
            logger.info("Category '%s': no more articles after page %d.", category, page - 1)
            break
        page_articles = []
        for item in news_list:
            news_obj = item.get("news_obj") or item
            article  = parse_news_obj(news_obj)
            if article:
                article["category"] = category
                page_articles.append(article)
        logger.info("  %-22s  page %d/%d → %d articles",
                    category, page, max_pages, len(page_articles))
        all_articles.extend(page_articles)
        if not cursor:
            break
        news_offset = cursor
        time.sleep(POLITE_DELAY)
    return all_articles
def scrape_primary(categories: list, pages_per_category: int) -> list:
    """Steps 1 + 2: scrape all configured categories."""
    logger.info("── Steps 1+2: Category scrape (%d categories × up to %d pages) ──",
                len(categories), pages_per_category)
    all_articles = []
    for cat in categories:
        all_articles.extend(scrape_category_paginated(cat, pages_per_category))
    logger.info("Primary scrape complete: %d raw articles.", len(all_articles))
    return all_articles

# Bonus — trending / infinite-scroll API
def scrape_trending_paginated(max_pages: int) -> list:
    """
    Bonus: simulate infinite-scroll by paginating the trending endpoint.
    The browser fires this exact request when the user scrolls to the bottom
    of https://inshorts.com/en/read (visible in DevTools → Network → Fetch/XHR).
    """
    logger.info("── Bonus: Trending API pagination (%d pages) ───────────────", max_pages)
    all_articles = []
    news_offset  = None
    for page in range(1, max_pages + 1):
        params = {
            "category":          "top_stories",
            "max_limit":         str(ARTICLES_PER_PAGE),
            "include_card_data": "true",
        }
        if news_offset:
            params["news_offset"] = news_offset
        data = fetch_json(TRENDING_API, params=params)
        if not data:
            logger.warning("Trending page %d failed — stopping.", page)
            break
        news_list, cursor = extract_news_list(data)
        if not news_list:
            logger.info("Trending API: no more articles at page %d.", page)
            break
        page_articles = []
        for item in news_list:
            news_obj = item.get("news_obj") or item
            article  = parse_news_obj(news_obj)
            if article:
                article["category"] = "trending"
                page_articles.append(article)
        logger.info("  Trending page %d → %d articles", page, len(page_articles))
        all_articles.extend(page_articles)
        if not cursor:
            break
        news_offset = cursor
        time.sleep(POLITE_DELAY)
    logger.info("Trending scrape complete: %d articles.", len(all_articles))
    return all_articles

# Image downloading
def download_all_images(articles: list, folder: str = IMAGES_FOLDER) -> list:
    """
    Download the thumbnail image for every article and store the local path
    in the `image_local` field. Polite delay between each download.
    Articles without an image_url are skipped gracefully.
    """
    logger.info("── Downloading images → ./%s/ ──────────────────────────────", folder)
    success = 0
    for i, article in enumerate(articles, 1):
        local_path = download_image(
            article.get("image_url", ""),
            article.get("id", str(i)),
            article.get("headline", str(i)),
            folder,
        )
        article["image_local"] = local_path
        if local_path:
            success += 1
        time.sleep(IMAGE_DELAY)   # polite delay between image requests
    logger.info("Images downloaded: %d/%d", success, len(articles))
    return articles

# Deduplicate & export
def deduplicate(articles: list) -> list:
    """Deduplicate using API hash ID, falling back to normalised headline."""
    seen, unique = set(), []
    for a in articles:
        key = a.get("id") or a["headline"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(a)
    logger.info("Deduplicated: %d → %d unique articles.", len(articles), len(unique))
    return unique
def save_json(articles: list, path: str = OUTPUT_FILE) -> None:
    """Write articles to a pretty-printed UTF-8 JSON file."""
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(articles, fh, ensure_ascii=False, indent=2)
        logger.info("Saved %d articles → '%s'", len(articles), path)
    except IOError as e:
        logger.error("Could not write '%s': %s", path, e)

# Main
def main() -> None:
    logger.info("═══════════════════════════════════════════════════════")
    logger.info("  Inshorts News Scraper  —  starting")
    logger.info("═══════════════════════════════════════════════════════")
    articles = scrape_primary(WORKING_CATEGORIES, PAGES_PER_CATEGORY)
    trending = scrape_trending_paginated(BONUS_SCROLL_PAGES)
    articles.extend(trending)
    articles = deduplicate(articles)
    articles = download_all_images(articles)
    save_json(articles, OUTPUT_FILE)
    col = 50
    w   = col + 46
    print(f"\n{'─' * w}")
    print(f"  {'#':<4} {'Headline':<{col}} {'Author':<16} {'Image?'}")
    print(f"{'─' * w}")
    for i, a in enumerate(articles, 1):
        h     = (a["headline"][:col-2] + "…") if len(a["headline"]) > col else a["headline"]
        img   = "✅ " + os.path.basename(a["image_local"]) if a["image_local"] else "❌ no image"
        print(f"  {i:<4} {h:<{col}} {a['author'][:14]:<16} {img}")
    print(f"{'─' * w}")
    img_count = sum(1 for a in articles if a["image_local"])
    print(f"\n  ✅  {len(articles)} articles | {img_count} images | saved to '{OUTPUT_FILE}'\n")
    print(f"  Each article in the JSON contains:")
    print(f"      headline · summary · author · published_at · source_link · image_url · image_local\n")
if __name__ == "__main__":
    main()