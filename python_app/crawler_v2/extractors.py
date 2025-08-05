# crawler_v2/extractor.py

from bs4 import BeautifulSoup

# 🌍 Standard-Parser
from crawler_v2.parsers.standard import DefaultParser, FallbackParser

# 🧱 Strukturähnliche Seiten
from crawler_v2.parsers.familienbildung import (
    AachenParser,
    KoelnParser,
    MuenchenParser
)

# 🔍 Schema.org / JSON-LD
from crawler_v2.parsers.schemaorg import JsonLDParser

# ⚙️ Sonderfälle
from crawler_v2.parsers.special_cases import (
    KingKalliParser,
    PdfLinkParser,
    StaticPageParser
)

# 🗺️ Parser-Registry
parser_registry = {
    # Standard
    "default": DefaultParser(),
    "fallback": FallbackParser(),

    # Familienbildung
    "familienbildung_aachen": AachenParser(),
    "familienbildung_koeln": KoelnParser(),
    "familienbildung_muenchen": MuenchenParser(),

    # Schema.org
    "jsonld": JsonLDParser(),

    # Special Cases
    "kingkalli": KingKalliParser(),
    "pdf_link": PdfLinkParser(),
    "static_page": StaticPageParser(),
}


def extract_event(soup: BeautifulSoup, parser_key: str) -> dict | None:
    """
    Holt den passenden Parser aus der Registry und ruft extract() auf.

    :param soup: BeautifulSoup-Objekt der Event-Detailseite
    :param parser_key: Schlüsselname aus sources.json oder Datenbank
    :return: Dictionary mit Event-Daten oder None
    """
    parser = parser_registry.get(parser_key)

    if not parser:
        print(f"[Extractor] ⚠️ Kein Parser gefunden für '{parser_key}', fallback wird verwendet.")
        parser = DefaultParser()

    return parser.extract(soup)

from crawler_v2.parsers.special_cases import AachenTourismusParser

parser_registry["aachen_tourismus"] = AachenTourismusParser()
