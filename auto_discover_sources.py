from googlesearch import search
from bs4 import BeautifulSoup
import requests

# 🔍 Deine Suchbegriffe
search_terms = [
    "Veranstaltungskalender Aachen",
    "Events Köln site:.de",
    "Familienprogramm Bonn",
    "Freizeitangebote Eschweiler"
]

found_sources = []

for term in search_terms:
    print(f"🔎 Suche: {term}")
    try:
        results = search(term, num_results=10, lang="de")
        for url in results:
            try:
                print(f"👉 Prüfe {url}")
                response = requests.get(url, timeout=5)
                if any(word in response.text.lower() for word in ["veranstaltung", "termine", "event"]):
                    print(f"✅ Mögliche Quelle: {url}")
                    found_sources.append(url)
            except Exception as e:
                print(f"⚠️ Fehler bei {url}: {e}")
    except Exception as e:
        print(f"❌ Fehler bei Suche {term}: {e}")

# 💾 Ausgabe speichern
with open("gefundene_quellen.txt", "w", encoding="utf-8") as f:
    for url in found_sources:
        f.write(url + "\n")

print(f"\n🎯 {len(found_sources)} mögliche Quellen gefunden.")
