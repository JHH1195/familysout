# run.py – Starte den HTML-Crawler für alle Quellen

import json
import os
from html_crawler import crawl_source

# 📁 Dateipfad zu sources.json
SOURCES_PATH = os.path.join(os.path.dirname(__file__), "sources.json")

def load_sources(path=SOURCES_PATH):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Fehler beim Laden der sources.json: {e}")
        return []

def main():
    sources = load_sources()
    print(f"🔍 Starte Crawl für {len(sources)} Quellen...\n")

    for source in sources:
        print(f"\n🌐 Quelle: {source['name']}")
        try:
            crawl_source(source)
        except Exception as e:
            print(f"⚠️ Fehler bei Quelle '{source['name']}': {e}")

if __name__ == "__main__":
    main()
