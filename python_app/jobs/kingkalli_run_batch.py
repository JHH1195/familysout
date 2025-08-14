"""
Crawl -> Scrape -> Upsert für KingKalli.

Beispiele:
  python -m jobs.kingkalli_run_batch
  python -m jobs.kingkalli_run_batch --max-pages 1 --limit 10 --dry-run
  python -m jobs.kingkalli_run_batch --workers 1 --json
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import time
import os
from typing import List, Optional, Tuple

from crawler.source_loader import get_source
from crawler.kingkalli_list import crawl_list
from crawler.kingkalli_scrape_one import scrape_kingkalli_detail
from db import SessionLocal
import models as m
from jobs.kingkalli_upsert import upsert_event

import yaml
from datetime import datetime

ALWAYS_OPEN_PATH = os.path.join(
    os.path.dirname(__file__),  # jobs/
    "..", "crawler", "data", "always_open.yaml"
)
ALWAYS_OPEN_PATH = os.path.abspath(ALWAYS_OPEN_PATH)

def load_always_open():
    if not os.path.exists(ALWAYS_OPEN_PATH):
        raise FileNotFoundError(f"always_open.yaml nicht gefunden unter {ALWAYS_OPEN_PATH}")
    with open(ALWAYS_OPEN_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f).get("locations", [])

def match_always_open(location_name: str):
    if not location_name:
        return None
    locations = load_always_open()
    location_name_lower = location_name.lower()
    for loc in locations:
        patterns = [loc.get("name", "")] + loc.get("match", [])
        for pattern in patterns:
            if pattern.lower() in location_name_lower:
                season = loc.get("season")
                if season:
                    today = datetime.today()
                    start = datetime.strptime(f"{season['start']}-{today.year}", "%m-%d-%Y")
                    end = datetime.strptime(f"{season['end']}-{today.year}", "%m-%d-%Y")
                    if not (start <= today <= end):
                        return None
                return loc
    return None

# -------- Logging helpers (ANSI) --------
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"
BLUE = "\x1b[34m"
CYAN = "\x1b[36m"

def log_info(msg: str): print(f"{BLUE}[INFO]{RESET} {msg}")
def log_ok(msg: str):   print(f"{GREEN}[OK]{RESET}   {msg}")
def log_warn(msg: str): print(f"{YELLOW}[WARN]{RESET} {msg}")
def log_err(msg: str):  print(f"{RED}[ERR]{RESET}  {msg}")
def log_step(title: str): print(f"\n{BOLD}{title}{RESET}")

# -------- Worker: eine Detailseite verarbeiten --------
def process_one(url: str, json_out: bool = False) -> Tuple[Optional[dict], Optional[str]]:
    """
    Scraped eine Event-Detailseite.
    Rückgabe: (data, err_msg). Bei Erfolg err_msg=None.
    """
    t0 = time.time()
    try:
        data = scrape_kingkalli_detail(url)

        # Immer-offen / Öffnungszeiten anreichern
        ao = match_always_open(data.get("location"))
        if ao:
            data["is_always_open"] = True
            data["opening_hours"] = ao.get("opening_hours", {})
            data["holidays_closed"] = ao.get("holidays_closed", [])
        else:
            data["is_always_open"] = False

        if json_out:
            print(json.dumps({
                "url": url,
                "title": data.get("title"),
                "start_dt": data.get("start_dt"),
                "always_open": data.get("is_always_open"),
            }, ensure_ascii=False))

        return data, None
    except Exception as e:
        return None, f"{e.__class__.__name__}: {e}"
    finally:
        _ = (time.time() - t0) * 1000  # für spätere Messungen

# -------- Helper --------
def _find_existing_event(sess, data):
    """Heuristik: prüft, ob Event in der DB existiert (Titel + Quelle + Datum)."""
    q = sess.query(m.Event).filter(m.Event.title.ilike((data.get("title") or "").lower()))
    if hasattr(m.Event, "source_name"):
        q = q.filter(m.Event.source_name.ilike((data.get("source_name") or "").lower()))
    if hasattr(m.Event, "date"):
        q = q.filter(m.Event.date == (data.get("start_dt") or data.get("date") or ""))
    return q.first()

# -------- Runner --------
def run(source_name="kingkalli", workers=4, limit=None, throttle=0.3,
        dry_run=False, json_out=False, override_max_pages=None):

    sess = SessionLocal()
    try:
        try:
            src = get_source(source_name)
        except Exception as e:
            log_err(str(e))
            return 2

        start_url = src["start_url"]
        headers = src.get("headers", {})
        max_pages = int(override_max_pages or src.get("max_pages", 3))

        log_step(f"1) {source_name}: Liste crawlen")
        links = crawl_list(start_url, headers=headers, max_pages=max_pages)
        if not links:
            log_warn("Keine Links gefunden.")
            return 0
        if limit:
            links = links[:limit]
        log_info(f"{len(links)} Links gefunden.")

        # Stats
        n_done = n_ok = n_upd = n_new = n_err = 0
        t_start = time.time()

        if workers <= 1:
            # Seriell
            for idx, url in enumerate(links, 1):
                log_info(f"{idx}/{len(links)} – scrape: {url}")
                data, err = process_one(url, json_out=json_out)
                n_done += 1
                if err:
                    n_err += 1
                    log_err(f"scrape fail: {url} -> {err}")
                    continue

                if dry_run:
                    badge = " [Immer offen]" if data.get("is_always_open") else ""
                    log_ok(f"OK (dry-run): {data.get('title')} | {data.get('start_dt')}{badge}")
                else:
                    try:
                        existed = _find_existing_event(sess, data) is not None
                        upsert_event(sess, data)
                        sess.commit()
                        badge = " [Immer offen]" if data.get("is_always_open") else ""
                        if not existed:
                            n_new += 1
                            log_ok(f"Neu: {data.get('title')} | {data.get('start_dt')}{badge}")
                        else:
                            n_upd += 1
                            log_ok(f"Aktualisiert: {data.get('title')} | {data.get('start_dt')}{badge}")
                        n_ok += 1
                    except Exception as e:
                        sess.rollback()
                        n_err += 1
                        log_err(f"upsert fail: {url} -> {e}")

                if throttle:
                    time.sleep(throttle)
        else:
            # Parallel (I/O-bound)
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                fut_map = {ex.submit(process_one, u, json_out): u for u in links}
                for i, fut in enumerate(cf.as_completed(fut_map), 1):
                    url = fut_map[fut]
                    data, err = fut.result()
                    n_done += 1
                    if err:
                        n_err += 1
                        log_err(f"{i}/{len(links)} scrape fail: {url} -> {err}")
                        continue

                    if dry_run:
                        badge = " [Immer offen]" if data.get("is_always_open") else ""
                        log_ok(f"{i}/{len(links)} OK (dry-run): {data.get('title')} | {data.get('start_dt')}{badge}")
                    else:
                        try:
                            existed = _find_existing_event(sess, data) is not None
                            upsert_event(sess, data)
                            sess.commit()
                            badge = " [Immer offen]" if data.get("is_always_open") else ""
                            if not existed:
                                n_new += 1
                                log_ok(f"{i}/{len(links)} Neu: {data.get('title')} | {data.get('start_dt')}{badge}")
                            else:
                                n_upd += 1
                                log_ok(f"{i}/{len(links)} Aktualisiert: {data.get('title')} | {data.get('start_dt')}{badge}")
                            n_ok += 1
                        except Exception as e:
                            sess.rollback()
                            n_err += 1
                            log_err(f"{i}/{len(links)} upsert fail: {url} -> {e}")

                    if throttle:
                        time.sleep(throttle)

        dur = time.time() - t_start
        log_step("3) Zusammenfassung")
        print(
            f"{CYAN}{BOLD}"
            f"Links gesamt: {len(links)} | verarbeitet: {n_done} | OK: {n_ok} "
            f"| Neu: {n_new} | Updates: {n_upd} | Fehler: {n_err} | Dauer: {dur:.1f}s"
            f"{RESET}"
        )
        return 0 if n_err == 0 else 1

    finally:
        try:
            # bei scoped_session ist remove() korrekt
            SessionLocal.remove()
        except Exception:
            # falls kein scoped_session, wenigstens die eine Session schließen
            try:
                sess.close()
            except Exception:
                pass

# -------- CLI --------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="kingkalli")
    ap.add_argument("--max-pages", type=int, default=None, help="überschreibt YAML max_pages")
    ap.add_argument("--workers", type=int, default=4, help="Parallelität (1 = seriell)")
    ap.add_argument("--limit", type=int, default=None, help="Max. Anzahl Detail-Links verarbeiten")
    ap.add_argument("--throttle", type=float, default=0.3, help="Sleep zwischen Upserts (freundlich bleiben)")
    ap.add_argument("--dry-run", action="store_true", help="Nichts in DB schreiben (nur scrapen & loggen)")
    ap.add_argument("--json", action="store_true", help="pro Item eine kompakte JSON-Zeile loggen")
    args = ap.parse_args()

    sys.exit(run(
        source_name=args.source,
        workers=args.workers,
        limit=args.limit,
        throttle=args.throttle,
        dry_run=args.dry_run,
        json_out=args.json,
        override_max_pages=args.max_pages,
    ))

if __name__ == "__main__":
    main()
