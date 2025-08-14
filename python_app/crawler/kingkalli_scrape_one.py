# -*- coding: utf-8 -*-
"""
Scraper für einen einzelnen KingKalli-Event-Detail-Link.

Nutzung:
    python -m crawler.kingkalli_scrape_one \
      https://kingkalli.de/event/ferien-im-freilichtmuseum-kommern-glueckspueppchen-binden-2/
"""

from __future__ import annotations

import datetime
import json
import re
import sys
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

import pytz
import requests
from dateutil import parser as dateparser
from extruct.jsonld import JsonLdExtractor
from parsel import Selector
from w3lib.html import remove_tags

HEADERS = {"User-Agent": "familysout-scraper/1.0 (+https://www.familysout.de)"}
TZ = pytz.timezone("Europe/Berlin")
DE_MONTHS = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}


# ----------------- Helpers -----------------
def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.text


def _norm_text(x: Optional[str]) -> Optional[str]:
    if not x:
        return x
    return re.sub(r"\s+", " ", str(x)).strip()


def _as_float(x) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None


def _take_first_text(sel: Selector, *css_queries: str) -> Optional[str]:
    for q in css_queries:
        v = sel.css(q).get()
        if v:
            v = re.sub(r"\s+", " ", v).strip()
            if v:
                return v
    return None


def _take_first_xpath(sel: Selector, *xpaths: str) -> Optional[str]:
    for xp in xpaths:
        v = sel.xpath(xp).get()
        if v:
            v = re.sub(r"\s+", " ", v).strip()
            if v:
                return v
    return None


def _find_main(sel: Selector) -> Selector:
    """
    Begrenze den Scope auf den Hauptinhalt, damit Sidebar/Newsletter nicht mitreinsickert.
    """
    node = sel.css("article").get()
    if node:
        return Selector(text=node)
    node = sel.css("#main, #content, .site-content, .entry-content").get()
    if node:
        return Selector(text=node)
    return sel  # Fallback


def _parse_jsonld(html: str, url: str) -> Dict[str, Any]:
    """Ziehe schema.org/Event wenn vorhanden."""
    try:
        blocks = JsonLdExtractor().extract(html, url)
        for b in blocks:
            t = b.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(str(x).lower() == "event" for x in types if x):
                return b
    except Exception:
        pass
    return {}


def _parse_datetime(x: Optional[str]):
    if not x:
        return None
    try:
        return dateparser.parse(x)
    except Exception:
        return None


def _parse_de_datetime(text: str) -> tuple[Optional[datetime.datetime], Optional[datetime.datetime]]:
    """
    Extrahiert z. B.:
      'Donnerstag, 14. August | 13:00 - 16:00 Uhr'
      'Datum: 14. August' + 'Zeit: 13:00-16:00'
    Annahme: Jahr fehlt -> aktuelles Jahr (Europe/Berlin).
    """
    if not text:
        return None, None
    t = " ".join(text.split())
    m_date = re.search(r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)", t)
    m_time = re.search(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", t)
    year = datetime.datetime.now(TZ).year

    if not m_date:
        return None, None

    day = int(m_date.group(1))
    month_name = m_date.group(2).lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    month = DE_MONTHS.get(month_name)
    if not month:
        return None, None

    if m_time:
        sh, sm = map(int, m_time.group(1).split(":"))
        eh, em = map(int, m_time.group(2).split(":"))
        start_dt = TZ.localize(datetime.datetime(year, month, day, sh, sm))
        end_dt = TZ.localize(datetime.datetime(year, month, day, eh, em))
        return start_dt, end_dt

    start_dt = TZ.localize(datetime.datetime(year, month, day, 0, 0))
    return start_dt, None


# ----------------- Main scraper -----------------
def scrape_kingkalli_detail(url: str) -> Dict[str, Any]:
    html = fetch(url)
    sel = Selector(html)
    main = _find_main(sel)
    jld = _parse_jsonld(html, url)

    # --- INIT: sichere Defaults, damit UnboundLocal unmöglich ist ---
    title = None
    description = None
    image = None
    start_dt = None
    end_dt = None
    location = None
    maps_url = None
    category = "Unbekannt"
    lat = None
    lon = None
    price = None
    is_free = None
    is_outdoor = None
    age_group = None
    # ---------------------------------------------------------------

    # Titel
    title = jld.get("name") or _take_first_text(main, "h1::text", "h2::text", "title::text")

    # Beschreibung (Klartext, nur Hauptinhalt)
    if jld.get("description"):
        description = jld.get("description")
        if "<" in description:
            description = remove_tags(description)
        description = _norm_text(description)
    else:
        # gezielt die Event-Description nehmen; Fallback: etwas breiter
        desc_html = main.css(".tribe-events-single-event-description, .tribe-events-content").get()
        if desc_html:
            description = _norm_text(remove_tags(desc_html))
        else:
            txts = main.css("article, .entry-content, .tribe-events-content, .content ::text").getall()
            description = _norm_text(" ".join(t for t in txts if t.strip()))

    # Bild
    img = jld.get("image")
    if isinstance(img, dict):
        image = img.get("url")
    elif isinstance(img, list) and img:
        image = img[0]
    elif isinstance(img, str):
        image = img
    if not image:
        image = sel.css('meta[property="og:image"]::attr(content)').get()

    # Datum/Zeit
    start_raw = jld.get("startDate")
    end_raw = jld.get("endDate")
    start_dt = _parse_datetime(start_raw)
    end_dt = _parse_datetime(end_raw)
    if not start_dt:
        header_line = _take_first_text(main, "h3::text", ".tribe-events-schedule h2::text", ".tribe-events-schedule h3::text")
        details_text = " ".join(main.xpath("//*[contains(., 'Datum') or contains(., 'Zeit')]/text()").getall())
        s2, e2 = _parse_de_datetime(" ".join(filter(None, [header_line, details_text])))
        start_dt = start_dt or s2
        end_dt = end_dt or e2

    # Veranstaltungsort
    loc = jld.get("location")
    if isinstance(loc, dict):
        location = loc.get("name") or loc.get("address")
        geo = loc.get("geo") or {}
        lat = _as_float(geo.get("latitude"))
        lon = _as_float(geo.get("longitude"))

    if not location:
        location = _take_first_xpath(
            main,
            "//section[.//h2[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', 'abcdefghijklmnopqrstuvwxyzäöü'), 'veranstaltungsort')] or "
            ".//h3[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', 'abcdefghijklmnopqrstuvwxyzäöü'), 'veranstaltungsort')]]//a[1]/text()",
            "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', 'abcdefghijklmnopqrstuvwxyzäöü'), 'veranstaltungsort')]/following::a[1]/text()",
            "//dd[contains(@class,'tribe-venue')]//a[1]/text()",
        )
        location = _norm_text(location)

    # Maps-Link + Koordinaten
    maps_url = _take_first_xpath(
        sel,
        "//a[contains(., 'Google Karte')]/@href",
        "//a[contains(@href, 'google.com/maps') or contains(@href, 'goo.gl/maps')]/@href",
    )
    if maps_url and (lat is None or lon is None):
        try:
            q = parse_qs(urlparse(maps_url).query)
            if "query" in q and q["query"]:
                coords = unquote(q["query"][0]).split(",")
                if len(coords) >= 2:
                    lat = float(coords[0].strip())
                    lon = float(coords[1].strip())
        except Exception:
            pass

    # Kategorien
    cats = main.xpath(
    "//dd[contains(@class,'tribe-events-event-categories')]//a/text()"
    "| //a[contains(@href, '/events/kategorie/')]/text()"
    ).getall()
    cats = [_norm_text(c) for c in cats if _norm_text(c)]

    # Duplikate entfernen, Reihenfolge beibehalten
    cats = list(dict.fromkeys(cats))

    category = ", ".join(cats) if cats else "Unbekannt"


    # Preis / is_free
    offers = jld.get("offers")
    if isinstance(offers, dict) and offers.get("price") not in (None, ""):
        price = _as_float(offers.get("price"))
        is_free = (price == 0.0)
    if price is None or is_free is None:
        txt = " ".join(main.css("::text").getall())
        m_price = re.search(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:€|Euro)\b", txt, re.I)
    if m_price and price is None:
        price = _as_float(m_price.group(1))
    if is_free is None:
        is_free = bool(re.search(r"\b(kostenlos|frei|spende)\b", txt, re.I))
        if price is not None:
            is_free = (price == 0.0)

    # 💡 Default: kein Preis => kostenlos
    if price is None:
        price = 0.0
        is_free = True


    # Heuristiken (sicher, weil description immer existiert – ggf. None)
    text_for_heur = f"{title or ''} {description or ''}".lower()
    is_outdoor = True if re.search(r"\b(freilicht|open\s*air|outdoor)\b", text_for_heur) else None
    m_age = re.search(r"ab\s*(\d{1,2})\s*j", text_for_heur)
    if m_age:
        age_group = f"{m_age.group(1)}+"
    elif ("familie" in text_for_heur) or ("kinder" in text_for_heur):
        age_group = "Familie/Kinder"

    return {
        "title": _norm_text(title),
        "description": _norm_text(description),
        "start_dt": start_dt.isoformat() if start_dt else None,
        "end_dt": end_dt.isoformat() if end_dt else None,
        "image_url": image,
        "location": _norm_text(location),
        "maps_url": maps_url,
        "category": category,
        "source_url": url,
        "source_name": "KingKalli",
        "lat": lat,
        "lon": lon,
        "price": price,
        "is_free": bool(is_free) if is_free is not None else None,
        "is_outdoor": is_outdoor,
        "age_group": age_group,
    }



def main():
    url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "https://kingkalli.de/event/ferien-im-freilichtmuseum-kommern-glueckspueppchen-binden-2/"
    )
    item = scrape_kingkalli_detail(url)
    print(json.dumps(item, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
