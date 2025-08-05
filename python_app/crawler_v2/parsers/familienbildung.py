# crawler_v2/parsers/familienbildung.py

from .base import BaseParser

class FamilienbildungsParserBase(BaseParser):
    """
    Basisklasse für strukturähnliche Familienbildungsseiten.
    Leitet Methoden zur Extraktion von Titel, Beschreibung, Datum, Ort weiter.
    """

    def extract(self, soup):
        try:
            title = self.extract_title(soup)
            description = self.extract_description(soup)
            date = self.extract_date(soup)
            location = self.extract_location(soup)

            self.log(f"👨‍👩‍👧‍👦 Event erkannt: {title}")
            return {
                "title": title,
                "date": date,
                "description": description,
                "location": location,
                "age_group": ""
            }

        except Exception as e:
            self.log(f"Fehler beim Familienbildungs-Parser: {e}", level="error")
            return None

    def extract_title(self, soup):
        h1 = soup.find("h1")
        return self.clean_text(h1.get_text()) if h1 else "ohne Titel"

    def extract_description(self, soup):
        desc_div = soup.select_one("div.text, .event-description, .description")
        if desc_div:
            return self.clean_text(desc_div.get_text(separator="\n"))
        paragraphs = soup.find_all("p")
        return "\n".join([self.clean_text(p.get_text()) for p in paragraphs[:5]])

    def extract_date(self, soup):
        time_tag = soup.find("time")
        if time_tag and time_tag.has_attr("datetime"):
            return time_tag["datetime"][:10]
        date_text = soup.find(string=lambda s: "Termin" in s or "Datum" in s)
        return "unbekannt" if not date_text else self.clean_text(date_text)

    def extract_location(self, soup):
        loc_tag = soup.select_one(".veranstaltungsort, .location, .ort")
        return self.clean_text(loc_tag.get_text()) if loc_tag else "unbekannt"

class AachenParser(FamilienbildungsParserBase):
    def __init__(self):
        super().__init__(name="AachenParser")

class KoelnParser(FamilienbildungsParserBase):
    def __init__(self):
        super().__init__(name="KoelnParser")

class MuenchenParser(FamilienbildungsParserBase):
    def __init__(self):
        super().__init__(name="MuenchenParser")


class AachenTourismusParser(BaseParser):
    def __init__(self):
        super().__init__(name="AachenTourismusParser")

    def extract(self, soup):
        try:
            # Titel aus h5
            h5 = soup.select_one(".destination1-slider__item__meta--title")
            title = self.clean_text(h5.get_text()) if h5 else "ohne Titel"

            # Beschreibung aus erstem <p>
            desc_tag = soup.find("p")
            description = self.clean_text(desc_tag.get_text()) if desc_tag else ""

            # Datum aus Aufzählung (falls vorhanden)
            date_tag = soup.find(string=lambda s: "Termin" in s or "Datum" in s)
            date = "unbekannt"
            if date_tag and date_tag.parent.name == "li":
                date = self.clean_text(date_tag.parent.get_text())[:10]

            # Ort oder Info
            location = "Aachen Tourismus"

            self.log(f"🎯 Event erkannt: {title}")
            return {
                "title": title,
                "date": date,
                "description": description,
                "location": location,
                "age_group": ""
            }

        except Exception as e:
            self.log(f"Fehler beim Parsen von Aachen Tourismus: {e}", level="error")
            return None

