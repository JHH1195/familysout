# test_crawler.py – CLI-Tool zum Testen einzelner Quellen

import json
import os
import argparse
from crawler_v2.html_crawler import crawl_source

SOURCES_PATH = os.path.join(os.path.dirname(__file__), "crawler_v2", "sources.json")

def load_sources(path=SOURCES_PATH):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Fehler beim Laden der sources.json: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(
        description="Starte Crawler für eine bestimmte Quelle oder alle."
    )
    parser.add_argument("--name", help="Name oder Teilname der Quelle", type=str)
    parser.add_argument("--max", help="Maximale Seitenanzahl (default: 1)", type=int, default=1)

    args = parser.parse_args()
    sources = load_sources()

    # Filter: Nur Quelle mit passendem Namen
    if args.name:
        filtered = [
            s for s in sources
            if args.name.lower() in s["name"].lower()
        ]
        if not filtered:
            print(f"⚠️ Keine Quelle gefunden mit '{args.name}'")
            return
    else:
        filtered = sources

    print(f"🔍 Starte Crawl für {len(filtered)} Quelle(n)...\n")

    for source in filtered:
        print(f"\n🌐 Quelle: {source['name']}")
        try:
            crawl_source(source, max_pages=args.max)
        except Exception as e:
            print(f"❌ Fehler bei '{source['name']}': {e}")

if __name__ == "__main__":
    main()
