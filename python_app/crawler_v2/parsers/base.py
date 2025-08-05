# crawler_v2/parsers/base.py

from bs4 import BeautifulSoup

class BaseParser:
    """
    Basisklasse für alle Event-Parser.
    Alle konkreten Parser müssen die Methode `extract()` überschreiben.
    """

    def __init__(self, name="BaseParser"):
        self.name = name

    def extract(self, soup: BeautifulSoup) -> dict | None:
        """
        Hauptfunktion zur Extraktion eines Events.
        Muss von Subklassen implementiert werden.

        :param soup: BeautifulSoup-Objekt der Detailseite
        :return: Dictionary mit Event-Daten oder None bei Fehler
        """
        raise NotImplementedError("Parser muss extract() implementieren")

    def clean_text(self, text: str) -> str:
        """
        Bereinigt Text (Trimmen, Unicode-Bereinigung etc.)

        :param text: Rohtext
        :return: Bereinigter Text
        """
        return text.strip().replace("\xa0", " ") if text else ""

    def log(self, message: str, level: str = "info"):
        """
        Standardisiertes Logging für Parserprozesse.

        :param message: Textnachricht
        :param level: "info", "warn", "error"
        """
        tag = {
            "info": "ℹ️",
            "warn": "⚠️",
            "error": "❌"
        }.get(level, "🔍")
        print(f"[{self.name}] {tag} {message}")
