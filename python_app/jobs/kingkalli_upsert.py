# -*- coding: utf-8 -*-
"""
Liest einen KingKalli-Event (Detail-URL) und upsertet ihn in die DB.
Nutzung:
    python -m jobs.kingkalli_upsert https://kingkalli.de/event/...
Oder ohne URL (nimmt das Beispiel aus dem Scraper):
    python -m jobs.kingkalli_upsert
"""

from __future__ import annotations
import sys
from datetime import datetime
from dateutil import parser as dtp

from crawler.kingkalli_scrape_one import scrape_kingkalli_detail
from db import SessionLocal  # deine Session aus db.py
import models as m           # dein Event-Model

def _to_iso_datetime_str(x):
    if not x:
        return None
    if isinstance(x, datetime):
        return x.isoformat()
    try:
        return dtp.parse(str(x)).isoformat()
    except Exception:
        return None

def _norm_key(s: str | None) -> str:
    return (s or "").strip().lower()

def upsert_event(sess, data: dict) -> m.Event:
    """
    Dupe-Heuristik: title + (start_dt/date) + source_name.
    Achtung: Dein Model hat 'date' als String – wir schreiben dort ISO rein.
    """
    title_key = _norm_key(data.get("title"))
    start_iso = _to_iso_datetime_str(data.get("start_dt") or data.get("date"))
    source_key = _norm_key(data.get("source_name"))

    # Bestehendes Event finden (title + source_name + date)
    q = sess.query(m.Event).filter(m.Event.title.ilike(title_key))
    if hasattr(m.Event, "source_name"):
        q = q.filter(m.Event.source_name.ilike(source_key))
    if hasattr(m.Event, "date"):
        q = q.filter(m.Event.date == (start_iso or ""))

    obj = q.first()
    if not obj:
        obj = m.Event()
        sess.add(obj)

    # Zuweisungen (nur Felder, die es bei dir gibt)
    obj.title = data.get("title")
    obj.description = data.get("description")
    obj.date = start_iso  # <- dein Schema: String
    obj.image_url = data.get("image_url")
    obj.location = data.get("location")
    obj.maps_url = data.get("maps_url")
    obj.category = data.get("category") or "Unbekannt"
    obj.source_url = data.get("source_url")
    obj.source_name = data.get("source_name")
    obj.lat = data.get("lat")
    obj.lon = data.get("lon")
    obj.price = data.get("price")
    obj.is_free = data.get("is_free")
    obj.is_outdoor = data.get("is_outdoor")
    obj.age_group = data.get("age_group")

    return obj

def main():
    url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "https://kingkalli.de/event/ferien-im-freilichtmuseum-kommern-glueckspueppchen-binden-2/"
    )
    payload = scrape_kingkalli_detail(url)
    sess = SessionLocal()
    try:
        evt = upsert_event(sess, payload)
        sess.commit()
        print(f"OK: upserted event id={getattr(evt, 'id', None)} title={evt.title!r} date={evt.date!r}")
    except Exception:
        sess.rollback()
        raise
    finally:
        SessionLocal.remove()


if __name__ == "__main__":
    main()
