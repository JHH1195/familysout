# crawler_v2/parsers/schemaorg.py

import json
from .base import BaseParser

class JsonLDParser(BaseParser):
    def __init__(self):
        super().__init__(name="JsonLDParser")

    def extract(self, soup):
        try:
            scripts = soup.find_all("script", type="application/ld+json")
            if not scripts:
                self.log("Kein JSON-LD gefunden", level="warn")
                return None

            for script in scripts:
                try:
                    raw = script.string
                    if not raw:
                        continue
                    data = json.loads(raw)

                    # direktes Event-Objekt
                    if isinstance(data, dict) and data.get("@type") == "Event":
                        return self._extract_event_data(data)

                    # @graph mit mehreren Objekten
                    if isinstance(data, dict) and "@graph" in data:
                        events = [e for e in data["@graph"] if e.get("@type") == "Event"]
                        if events:
                            return self._extract_event_data(events[0])

                except Exception as e:
                    self.log(f"Fehler beim Parsen eines Scripts: {e}", level="warn")
                    continue

            self.log("Kein Event in JSON-LD gefunden", level="warn")
            return None

        except Exception as e:
            self.log(f"JSON-LD Parsing fehlgeschlagen: {e}", level="error")
            return None

    def _extract_event_data(self, data):
        title = self.clean_text(data.get("name", "ohne Titel"))
        date = self.clean_text(data.get("startDate", "unbekannt"))[:10]
        description = self.clean_text(data.get("description", ""))
        location = self._extract_location(data.get("location"))

        self.log(f"🎉 Event erkannt via JSON-LD: {title}")
        return {
            "title": title,
            "date": date,
            "description": description,
            "location": location,
            "age_group": ""
        }

    def _extract_location(self, loc_data):
        if not loc_data:
            return "unbekannt"
        if isinstance(loc_data, dict):
            return self.clean_text(loc_data.get("name") or
                                   loc_data.get("address", {}).get("addressLocality", ""))
        return self.clean_text(str(loc_data))
