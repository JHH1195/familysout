import argparse, json, os, sys, time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import yaml
import dateparser

# Optional Playwright für JS-Seiten
USE_PLAYWRIGHT = True
try:
    from playwright.sync_api import sync_playwright
except Exception:
    USE_PLAYWRIGHT = False

def fetch_html(url: str, use_js: bool = False, timeout=20) -> str:
    if use_js and USE_PLAYWRIGHT:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
            html = page.content()
            browser.close()
            return html
    # Fallback: requests
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "familysout-bot/1.0"})
    r.raise_for_status()
    return r.text

def extract_text(el, selector: str):
    node = el.select_one(selector) if selector else None
    if not node:
        return ""
    return " ".join(node.get_text(strip=True).split())

def parse_date(s: str, fmt: str | None):
    s = (s or "").strip()
    if not s:
        return ""
    if fmt:
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    dt = dateparser.parse(s, languages=["de"])
    return dt.strftime("%Y-%m-%d") if dt else ""

def crawl_one(seed: dict) -> list[dict]:
    html = fetch_html(seed["url"], use_js=seed.get("use_js", False))
    soup = BeautifulSoup(html, "lxml")

    events = []
    items = soup.select(seed.get("list_selector") or "body")
    for el in items:
        fields = seed.get("fields", {})
        title = extract_text(el, fields.get("title"))
        date_s = extract_text(el, fields.get("date"))
        location = extract_text(el, fields.get("location"))
        description = extract_text(el, fields.get("description"))

        date_iso = parse_date(date_s, seed.get("date_format"))

        if not title or not date_iso:
            # Minimalanforderungen
            continue

        events.append({
            "title": title,
            "date": date_iso,
            "location": location,
            "description": description[:1000],
            "image_url": "",                # optional: leer lassen oder später scrapen
            "source_name": seed["slug"],
            "source_url": seed["url"],
            "category": "Crawler"
        })
    return events

def load_seeds(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def push_batch(push_url: str, token: str, batch: list[dict]):
    resp = requests.post(
        push_url,
        headers={"Content-Type": "application/json", "X-Task-Token": token},
        data=json.dumps(batch),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"status": resp.text}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="python_app/seed_ki_quellen.yaml", help="Pfad zur Seeds-Datei (YAML)")
    ap.add_argument("--only", help="Nur eine Quelle (slug) ausführen")
    ap.add_argument("--push", help="Ingest-Endpoint, z.B. https://app.familysout.de/ingest/batch")
    ap.add_argument("--token", help="CRAWLER_TOKEN für Push (Header X-Task-Token)")
    ap.add_argument("--dry", action="store_true", help="Nur anzeigen, nicht pushen")
    args = ap.parse_args()

    seeds = load_seeds(args.seed)
    if args.only:
        seeds = [s for s in seeds if s.get("slug") == args.only]
        if not seeds:
            print(f"⚠️  Keine Quelle mit slug={args.only} gefunden.")
            sys.exit(1)

    all_events = []
    for seed in seeds:
        print(f"🔎 Crawle {seed['slug']} → {seed['url']}")
        try:
            items = crawl_one(seed)
            print(f"   → {len(items)} Events")
            all_events.extend(items)
        except Exception as e:
            print(f"❌ Fehler bei {seed['slug']}: {e}")

    if args.dry or not args.push:
        print(json.dumps(all_events, ensure_ascii=False, indent=2))
        print(f"🧾 Total: {len(all_events)} Events (DRY)")
        return

    if not args.token:
        print("❌ --token fehlt für Push")
        sys.exit(1)

    # In sinnvollen Batches pushen
    BATCH = 50
    pushed = 0
    for i in range(0, len(all_events), BATCH):
        batch = all_events[i:i+BATCH]
        res = push_batch(args.push, args.token, batch)
        pushed += len(batch)
        print(f"📦 Batch {i//BATCH+1}: {len(batch)} → {res}")
        time.sleep(0.5)
    print(f"✅ Fertig. {pushed} Events gepusht.")

if __name__ == "__main__":
    main()
