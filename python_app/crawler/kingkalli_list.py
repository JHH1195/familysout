# -*- coding: utf-8 -*-
from __future__ import annotations
import re, time, urllib.parse
from typing import List, Set
import requests
from parsel import Selector
from .source_loader import get_source

EXCLUDE_PATTERNS = (
    "/events/kategorie/",
    "/veranstaltungsort/",
    "/category/",
    "/events/kalender/",
    "?ical=1",
    "/feed/",
)
DETAIL_ALLOW_FRAGMENT = "/event/"

def fetch(url: str, headers: dict, sleep: float = 0.8) -> str:
    r = requests.get(url, headers=headers or {}, timeout=25)
    r.raise_for_status()
    if sleep: time.sleep(sleep)
    return r.text

def norm_url(url: str, base: str) -> str:
    u = urllib.parse.urljoin(base, url)
    parts = urllib.parse.urlsplit(u)
    query = [(k, v) for (k, v) in urllib.parse.parse_qsl(parts.query) if not k.lower().startswith("utm")]
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), urllib.parse.urlencode(query), ""))

def looks_like_detail(u: str) -> bool:
    if DETAIL_ALLOW_FRAGMENT not in u: return False
    if any(bad in u for bad in EXCLUDE_PATTERNS): return False
    if "/event/" in u and "/?" in u: return False
    return True

def extract_detail_links(html: str, page_url: str) -> List[str]:
    sel = Selector(html)
    hrefs = sel.css("a::attr(href)").getall()
    out = []
    for h in hrefs:
        try:
            u = norm_url(h, page_url)
        except Exception:
            continue
        if looks_like_detail(u):
            out.append(u)
    seen: Set[str] = set()
    deduped = []
    for u in out:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped

def find_next_page(html: str, page_url: str) -> str | None:
    sel = Selector(html)
    nxt = sel.css("a[rel='next']::attr(href)").get()
    if nxt: return norm_url(nxt, page_url)
    candidates = sel.css(".pagination a::attr(href), .nav-links a::attr(href), .tribe-events-nav-next a::attr(href)").getall()
    for c in candidates:
        u = norm_url(c, page_url)
        if re.search(r"/page/\d+/?$", u) or "page=" in u.lower():
            return u
    return None

def crawl_list(start_url: str, headers: dict, max_pages: int = 3) -> List[str]:
    urls: List[str] = []
    seen: Set[str] = set()
    url = start_url
    page = 1
    while url and page <= max_pages:
        html = fetch(url, headers=headers)
        details = extract_detail_links(html, url)
        for d in details:
            if d not in seen:
                seen.add(d)
                urls.append(d)
        nxt = find_next_page(html, url)
        if nxt and nxt != url:
            url = nxt
            page += 1
        else:
            break
    return urls

def main():
    src = get_source("kingkalli") or {}
    base = src.get("base", "https://kingkalli.de")
    start = src.get("start_url", f"{base}/events/")
    headers = src.get("headers", {})
    max_pages = int(src.get("max_pages", 3))

    links = crawl_list(start, headers=headers, max_pages=max_pages)
    print(f"[LIST] {len(links)} Links gefunden (Start: {start})")
    print("\n".join(links))

if __name__ == "__main__":
    main()
