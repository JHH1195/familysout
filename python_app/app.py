"""
Familysout – Hauptanwendung
---------------------------
Flask-Web-App für Event-Suche, -Erstellung (manuell + OCR),
User-Verwaltung, Stripe-Abo, Admin-Tools und Crawler-Import.
"""

# =========================================================
# 📦 Imports & Konfiguration
# =========================================================
import os
import re
import io
import shutil
import subprocess
import uuid
from datetime import datetime, date
from urllib.parse import quote, urlparse

from dotenv import load_dotenv
load_dotenv()
load_dotenv(".env")
if os.getenv("FLASK_ENV") == "development":
    load_dotenv(".env.dev", override=True)

# Flask & Erweiterungen
from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify,
    send_file, abort, g
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from decimal import Decimal, InvalidOperation
# Datenbank & Models
from sqlalchemy import cast, String, or_
from sqlalchemy.exc import SQLAlchemyError
from db import engine, SessionLocal
from models import Event, User

# OCR & Bildverarbeitung
from PIL import Image
from ocr_utils import extract_event_fields_from_path
import pytesseract
try:
    from pdf2image import convert_from_path
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False

# Stripe & Kalender
import stripe
from ics import Calendar, Event as ICS_Event

# =========================================================
# 🏗 App-Setup
# =========================================================
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "flottikarotti")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Upload-Ordner (einheitlich)
UPLOAD_FOLDER = os.getenv("UPLOAD_DIR", os.path.join("static", "uploads"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".pdf", ".webp"}

# Stripe-Konfig
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "price_ABC123")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Session-Alias
Session = SessionLocal

# =========================================================
# 🔐 Login-Manager
# =========================================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    s = Session()
    try:
        return s.get(User, int(user_id))
    finally:
        s.close()

# =========================================================
# 🌐 Sprache & Übersetzungen
# =========================================================
translations = {
    "de": {
        "title": "Was wollen wir heute unternehmen?",
        "find": "Finden",
        "location": "Ort",
        "radius": "Umkreis (km)",
        "date": "Datum",
        "age": "Alter",
    },
    "en": {
        "title": "What would you like to do today?",
        "find": "Search",
        "location": "Location",
        "radius": "Radius (km)",
        "date": "Date",
        "age": "Age",
    }
}

@app.before_request
def detect_lang():
    g.lang = request.args.get("lang") or "de"

@app.context_processor
def inject_lang_and_translations():
    return {"lang": g.lang, "t": translations.get(g.lang, translations["de"])}

@app.template_filter('datetimeformat')
def datetimeformat(value, fmt="%d.%m.%Y %H:%M"):
    if not value:
        return ""
    from datetime import datetime
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except Exception:
            return value  # schon formatiert o. ä.
    # (Optional: in Europe/Berlin normalisieren, wenn naiv)
    if value.tzinfo is None:
        return value.strftime(fmt)
    return value.astimezone().strftime(fmt)  # lokale TZ

# =========================================================
# 🛠 Hilfsfunktionen
# =========================================================
WEEKDAY_DE = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]

def format_event_datetime(date_raw):
    try:
        dt = parse_event_datetime(date_raw)
        if not dt:
            return "Datum unbekannt"
        weekday = WEEKDAY_DE[dt.weekday()]
        time_str = dt.strftime("%H:%M").replace(":00", " Uhr") if (dt.hour or dt.minute) else ""
        date_str = dt.strftime("%d.%m.%Y")
        out = f"{weekday}, {time_str} ({date_str})".strip().replace(" ,", ",")
        return out
    except Exception:
        return "Datum unbekannt"


def parse_event_datetime(date_raw):
    if isinstance(date_raw, datetime):
        return date_raw
    if isinstance(date_raw, str):
        s = date_raw.strip()
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
            try:
                dt = datetime.strptime(s.replace(" Uhr", ""), fmt)
                # Falls nur Datum ohne Zeit → 09:00 annehmen
                if fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                    dt = dt.replace(hour=9, minute=0)
                return dt
            except ValueError:
                continue
        # Fallback: Zahlen aus String ziehen (yyyy-mm-dd)
        m = re.findall(r"\d+", s)
        if len(m) >= 3:
            if "-" in s:  # ISO-ähnlich
                y, mo, d = m[:3]
                try:
                    return datetime(int(y), int(mo), int(d), 9, 0)
                except Exception:
                    pass
            else:  # dd.mm.yyyy
                d, mo, y = m[:3]
                try:
                    if len(y) == 2:
                        y = "20" + y
                    return datetime(int(y), int(mo), int(d), 9, 0)
                except Exception:
                    pass
    return None

def _guess_year(month: int) -> int:
    today = date.today()
    return today.year + (1 if month < today.month else 0)

def _norm_time(s: str) -> str:
    s = s.replace("Uhr", "").strip().replace(".", ":")
    m = re.match(r"(\d{1,2})[:h\.]?(\d{2})?", s)
    return f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}" if m else ""

def _to_float(val):
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return None

def _to_bool(val):
    if isinstance(val, bool):
        return val
    if val is None:
        return None
    v = str(val).strip().lower()
    if v in ("1", "true", "wahr", "ja", "yes", "on"):
        return True
    if v in ("0", "false", "falsch", "nein", "no", "off"):
        return False
    return None

@app.template_filter('priceformat')
def priceformat(value):
    x = _to_number(value)
    if x is None:
        return ''
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _to_number(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, Decimal):
        return float(val)
    # Strings robuster parsen: "2,5 €" -> 2.5
    s = str(val).strip().replace("€", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, InvalidOperation):
        return None

@app.template_filter("euro")
def euro(val):
    x = _to_number(val)
    if x is None:
        return ""
    # deutsche Darstellung: 1.234,56
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =========================================================
# 📄 Legacy-OCR (nur Fallback)
# =========================================================
def extract_text_from_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"]:
        img = Image.open(path).convert("L")
        return pytesseract.image_to_string(img, lang="deu+eng")
    elif ext == ".pdf" and PDF_ENABLED:
        pages = convert_from_path(path, dpi=200, fmt="png")
        return "\n".join(pytesseract.image_to_string(p, lang="deu+eng") for p in pages[:3])
    else:
        raise ValueError("Nur Bilder oder PDFs unterstützt.")

def extract_multiple_events(text: str):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = lines[0] if lines else "ohne Titel"

    m_age = re.search(r"ab\s*(\d{1,2})\s*(Jahre|Jahr)", text, re.I)
    age_group = f"ab {m_age.group(1)} Jahre" if m_age else ""

    m_time = re.search(r"(\d{1,2}[:\.]\d{2})\s*Uhr", text, re.I)
    time_str = _norm_time(m_time.group(1)) if m_time else ""

    price = None
    m_price = re.search(r"(\d{1,2},\d{2})\s*€", text)
    if m_price:
        price = float(m_price.group(1).replace(",", "."))

    location = "Theater Brand, Aachen" if re.search(r"Theater\s*Brand", text, re.I) else ""

    raw_dates = re.findall(r"(\d{1,2})\.\s*(?:und\s*(\d{1,2})\.)?\s*(\d{1,2})", text)
    dates = []
    for d1, d2, mon in raw_dates:
        month = int(mon)
        year = _guess_year(month)
        for d_ in filter(None, [d1, d2]):
            try:
                dates.append(date(year, month, int(d_)).isoformat())
            except ValueError:
                pass

    singles = re.findall(r"\b(\d{1,2})\.(\d{1,2})\b", text)
    for d_, m_ in singles:
        month = int(m_)
        year = _guess_year(month)
        iso = date(year, month, int(d_)).isoformat()
        if iso not in dates:
            dates.append(iso)

    return [{
        "title": title,
        "date": f"{d} {time_str}" if time_str else d,
        "location": location or "unbekannt",
        "age_group": age_group,
        "price": price,
        "description": text[:1000],
        "category": "OCR",
        "is_free": False
    } for d in sorted(set(dates))]

# =========================================================
# 🧠 DB-Init (falls App-Factory genutzt wird)
# =========================================================


# =========================================================
# 📍 Event-Routen
# =========================================================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/results")
def suchergebnisse():
    s = Session()  # <- bei dir Alias auf SessionLocal
    try:
        # --- alte Parameter (kompatibel halten) ---
        query_legacy     = (request.args.get("q", "") or request.args.get("query", "")).strip()
        location_filter  = request.args.get("location", "").strip()
        category_filter  = request.args.get("category", "").strip()
        date_filter      = request.args.get("date", "").strip()

        # --- neue Parameter ---
        q       = query_legacy
        cats    = request.args.getlist("cats[]")      # Mehrfachkategorien
        free    = request.args.get("free") == "1"
        outdoor = request.args.get("outdoor") == "1"
        always  = request.args.get("always") == "1"

        # --- Kategorienliste für die Sidebar (aus DB, kommagetrennt auflösen) ---
        all_events = s.query(Event).all()
        cat_set = set()
        for ev in all_events:
            if ev.category:
                for c in str(ev.category).split(","):
                    c = c.strip()
                    if c:
                        cat_set.add(c)
        categories = sorted(cat_set)

        # --- Query aufbauen ---
        qset = s.query(Event)

        if q:
            like = f"%{q}%"
            qset = qset.filter(
                (Event.title.ilike(like)) |
                (Event.description.ilike(like)) |
                (Event.location.ilike(like))
            )

        # kompatibel zu alten Einzel-Filtern
        if location_filter:
            qset = qset.filter(Event.location.ilike(f"%{location_filter}%"))

        # einzelner Kategorienfilter (alt)
        if category_filter:
            qset = qset.filter(Event.category.ilike(f"%{category_filter}%"))

        # mehrere Kategorien (neu)
        if cats:
            cat_filters = [Event.category.ilike(f"%{c.strip()}%") for c in cats if c.strip()]
            qset = qset.filter(or_(*cat_filters))

        # Datum: prefix-match auf ISO/String
        if date_filter:
            # Event.date ist bei dir String – auf Nummer sicher casten
            qset = qset.filter(cast(Event.date, String).like(f"{date_filter}%"))

        # Flags
        if free:
            qset = qset.filter((Event.is_free == True) | (Event.price == 0))
        if outdoor and hasattr(Event, "is_outdoor"):
            qset = qset.filter(Event.is_outdoor == True)
        if always and hasattr(Event, "is_always_open"):
            qset = qset.filter(Event.is_always_open == True)

        events = qset.order_by(Event.date.asc()).all()
        
        coords = [
    {
        "lat": e.lat,
        "lon": e.lon,
        "title": e.title,
        "date": e.date.isoformat() if hasattr(e.date, "isoformat") else str(e.date),
        "id": e.id
    }
    for e in events if e.lat and e.lon
]

        return render_template("results.html", events=events, coords=coords,
            query=q,
            location_filter=location_filter,
            category_filter=category_filter,
            date_filter=date_filter,
            # Für die Sidebar:
            categories=categories,
        )
    finally:
        s.close()


@app.route("/event/<int:event_id>")
def event_detail(event_id):
    s = Session()
    try:
        event = s.query(Event).get(event_id)
        if not event:
            abort(404)
        readable_date = format_event_datetime(event.date)

        # Google Calendar (Bei String-Datum: 1h Event ab 09:00)
        dt = parse_event_datetime(event.date)
        if dt:
            start = dt.strftime("%Y%m%dT%H%M%SZ")
            end = (dt.replace(hour=dt.hour + 1 if dt.hour < 23 else dt.hour, minute=dt.minute)).strftime("%Y%m%dT%H%M%SZ")
        else:
            today = datetime.utcnow()
            start = today.strftime("%Y%m%dT090000Z")
            end = today.strftime("%Y%m%dT100000Z")

        google_calendar_url = (
            "https://www.google.com/calendar/render"
            f"?action=TEMPLATE"
            f"&text={quote(event.title or '')}"
            f"&dates={start}/{end}"
            f"&details={quote((event.description or '')[:1800])}"
            f"&location={quote(event.location or '')}"
        )

        return render_template("event.html", event=event, readable_date=readable_date,
                               google_calendar_url=google_calendar_url)
    finally:
        s.close()

@app.route("/event/<int:event_id>/download.ics")
def download_ics(event_id):
    s = Session()
    try:
        event = s.query(Event).get(event_id)
        if not event:
            abort(404)
        cal = Calendar()
        e = ICS_Event()
        e.name = event.title
        dt = parse_event_datetime(event.date) or datetime.utcnow()
        e.begin = dt
        e.duration = {"hours": 1}
        e.description = (event.description or "")[:1800]
        e.location = event.location or ""
        cal.events.add(e)

        file = io.StringIO(str(cal))
        return send_file(io.BytesIO(file.getvalue().encode("utf-8")),
                         mimetype="text/calendar",
                         as_attachment=True,
                         download_name=f"{(event.title or 'event').strip().replace(' ','_')}.ics")
    finally:
        s.close()

# =========================================================
# 🧾 Event erstellen (Form)
# =========================================================
@app.route("/event-erstellen", methods=["GET", "POST"])
def event_erstellen():
    if request.method == "GET":
        return render_template("event-erstellen.html")

    # POST → Speichern in DB (manuell oder via OCR-prefilled)
    data = request.form.to_dict()

    date_str = (data.get('date') or '').strip()
    time_str = (data.get('time') or '').strip()
    if time_str and 'Uhr' not in time_str:
        time_str = time_str + ' Uhr'
    date_combined = f"{date_str} {time_str}".strip() if (date_str or time_str) else None

    source_url = (data.get('source_url') or '').strip() or None
    source_name = (data.get('source_name') or '').strip() or None
    if not source_name and source_url:
        try:
            host = urlparse(source_url).netloc
            source_name = host.replace('www.', '') if host else None
        except Exception:
            pass

    s = Session()
    try:
        event = Event(
            title=data.get('title'),
            description=data.get('description'),
            date=date_combined,
            image_url=data.get('image_url'),   # vom OCR-Upload (static/uploads/uuid.ext)
            location=data.get('location'),
            maps_url=data.get('maps_url'),
            category=data.get('category') or "Unbekannt",
            source_url=source_url,
            source_name=source_name,
            lat=_to_float(data.get('lat')),
            lon=_to_float(data.get('lon')),
            price=_to_float(data.get('price')),
            is_free=_to_bool(data.get('is_free')),
            is_outdoor=_to_bool(data.get('is_outdoor')),
            age_group=data.get('age_group')
        )
        s.add(event)
        s.commit()
        flash("🎉 Event gespeichert", "success")
        return redirect(url_for("event_detail", event_id=event.id))
    except SQLAlchemyError as e:
        s.rollback()
        flash(f"DB-Fehler: {str(e)}", "danger")
        return redirect(url_for("event_erstellen"))
    finally:
        s.close()

# =========================================================
# 🖼️ OCR Upload (neuer Endpoint) + Legacy-Fallback
# =========================================================
def _save_upload_return_path(file_storage):
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return None, "Nur JPG/PNG/PDF erlaubt"
    fname = f"{uuid.uuid4().hex}{ext}"
    safe = secure_filename(fname)
    dest_path = os.path.join(app.config["UPLOAD_FOLDER"], safe)
    file_storage.save(dest_path)
    public_url = url_for("static", filename=f"uploads/{safe}", _external=False)
    return (dest_path, public_url), None

@app.route("/ocr/upload", methods=["POST"])
def ocr_upload_new():
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "Keine Datei übermittelt"}), 400

    (dest_path, public_url), err = _save_upload_return_path(file)
    if err:
        return jsonify({"error": err}), 400

    try:
        ocr = extract_event_fields_from_path(dest_path)
    except Exception as e:
        return jsonify({"error": f"OCR fehlgeschlagen: {str(e)}"}), 500

    ocr.fields["image_url"] = public_url

    return jsonify({
        "ok": True,
        "image_url": public_url,
        "fields": ocr.fields,
        "found": ocr.found,
        "missing": ocr.missing,
        "confidence": ocr.confidence
    })

@app.route("/ocr-upload", methods=["POST"])
def ocr_upload_legacy():
    # kompatibel zum alten Frontend (liefert einfache Felder zurück)
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "Keine Datei erhalten."}), 400

    (dest_path, public_url), err = _save_upload_return_path(file)
    if err:
        return jsonify({"error": err}), 400

    # Erst neuer OCR-Versuch (feldernormiert). Falls etwas schiefgeht, Legacy-Text-Parsing.
    try:
        ocr = extract_event_fields_from_path(dest_path)
        f = ocr.fields
        f["image_url"] = public_url
        # Flatten für Alt-Client
        resp = {
            "title": f.get("title"),
            "description": f.get("description"),
            "date": f.get("date"),
            "time": f.get("time"),
            "location": f.get("location"),
            "category": f.get("category"),
            "maps_url": f.get("maps_url"),
            "source_url": f.get("source_url"),
            "lat": f.get("lat"),
            "lon": f.get("lon"),
            "price": f.get("price"),
            "is_free": f.get("is_free"),
            "is_outdoor": f.get("is_outdoor"),
            "age_group": f.get("age_group"),
            "image_url": public_url
        }
        return jsonify(resp)
    except Exception:
        # Legacy: Nur Text/OCR und simple Heuristiken
        try:
            text = extract_text_from_file(dest_path)
            events = extract_multiple_events(text)
            if not events:
                return jsonify({"error": "Kein Text erkannt"}), 422
            events[0]["image_url"] = public_url
            return jsonify(events[0])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

# =========================================================
# 👤 User-Routen
# =========================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        s = Session()
        try:
            email = request.form["email"]
            if s.query(User).filter_by(email=email).first():
                flash("Diese E-Mail ist bereits registriert.", "danger")
                return redirect(url_for("register"))
            if request.form["password"] != request.form["password_repeat"]:
                flash("Passwörter stimmen nicht überein.", "danger")
                return redirect(url_for("register"))

            user = User(email=email,
                        firstname=request.form["firstname"],
                        lastname=request.form["lastname"],
                        city=request.form.get("city"))
            user.set_password(request.form["password"])
            s.add(user)
            s.commit()
            login_user(user)
            flash("Willkommen bei Familysout!", "success")
            return redirect(url_for("profil"))
        finally:
            s.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        s = Session()
        try:
            user = s.query(User).filter_by(email=request.form["email"]).first()
            if user and user.check_password(request.form["password"]):
                login_user(user)
                flash("Erfolgreich eingeloggt", "success")
                return redirect(url_for("profil"))
            flash("Falsche E-Mail oder Passwort", "danger")
        finally:
            s.close()
    return render_template("login.html")

@app.route("/profil")
@login_required
def profil():
    return render_template("profil.html", user=current_user)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

# =========================================================
# 💳 Stripe-Routen
# =========================================================
@app.route("/preise")
def preise():
    return render_template("preise.html")

@app.route("/checkout")
@login_required
def checkout():
    s = Session()
    try:
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(email=current_user.email)
            current_user.stripe_customer_id = customer.id
            s.merge(current_user)
            s.commit()
        checkout_session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=url_for("profil", _external=True),
            cancel_url=url_for("preise", _external=True),
        )
        return redirect(checkout_session.url, code=303)
    finally:
        s.close()

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception:
        return "Invalid payload", 400

    if event.get("type") == "checkout.session.completed":
        data = event["data"]["object"]
        s = Session()
        try:
            user = s.query(User).filter_by(stripe_customer_id=data.get("customer")).first()
            if user:
                user.stripe_subscription_id = data.get("subscription")
                user.is_premium = True
                s.commit()
        finally:
            s.close()
    return "", 200

# =========================================================
# 📄 Statische Seiten
# =========================================================
@app.route("/impressum")
def impressum():
    return render_template("impressum.html")

@app.route("/datenschutz")
def datenschutz():
    return render_template("datenschutz.html")

@app.route("/nutzungsbedingungen")
def nutzungsbedingungen():
    return render_template("nutzungsbedingungen.html")

@app.route("/ueber-uns")
def ueber_uns():
    return render_template("ueber_uns.html")

@app.route("/so-funktionierts")
def so_funktionierts():
    return render_template("so_funktionierts.html")

@app.route("/vorgaben")
def vorgaben():
    return render_template("vorgaben.html")


@app.get("/admin/diag")
@login_required
def admin_diag():
    if not getattr(current_user, "is_admin", False):
        abort(403)
    def cmd_version(bin_name):
        p = shutil.which(bin_name)
        if not p: return f"{bin_name}: not found"
        try:
            return subprocess.check_output([p, "--version"], text=True).splitlines()[0]
        except Exception as e:
            return f"{bin_name}: {e}"
    return {
        "tesseract": cmd_version("tesseract"),
        "poppler(pdftoppm)": cmd_version("pdftoppm"),
        "upload_dir": app.config["UPLOAD_FOLDER"],
        "db_driver": str(engine.url.drivername)
    }

# Profilbild-Upload
@app.post("/profilbild-upload")
@login_required
def profilbild_upload():
    # akzeptiere mehrere mögliche Feldnamen
    file = next((request.files.get(k) for k in ("avatar", "image", "profile_image", "file", "picture", "photo") if request.files.get(k)), None)
    if not file or file.filename == "":
        flash("Keine Datei ausgewählt.", "danger")
        return redirect(url_for("profil"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        flash("Nur JPG/PNG/WEBP/GIF erlaubt.", "danger")
        return redirect(url_for("profil"))

    # Zielpfad
    dest_dir = os.path.join(app.config["UPLOAD_FOLDER"], "profiles")
    os.makedirs(dest_dir, exist_ok=True)
    fname = f"{current_user.id}_{uuid.uuid4().hex}{ext}"
    path = os.path.join(dest_dir, secure_filename(fname))
    file.save(path)

    public_url = url_for("static", filename=f"uploads/profiles/{os.path.basename(path)}", _external=False)

    # User-Feld setzen (nimmt das erste vorhandene)
    s = Session()
    try:
        u = s.get(User, current_user.id)
        updated = False
        for attr in ("avatar_url", "image_url", "profile_image_url", "profile_url", "photo_url", "avatar"):
            if hasattr(u, attr):
                setattr(u, attr, public_url)
                updated = True
                break
        if not updated:
            # falls kein Feld existiert, wenigstens Source-Name setzen, damit nix crasht
            # (optional – entfernen, wenn du ein festes Feld hast)
            pass
        s.commit()
        flash("Profilbild aktualisiert.", "success")
    except Exception as e:
        s.rollback()
        flash(f"Upload fehlgeschlagen: {e}", "danger")
    finally:
        s.close()

    return redirect(url_for("profil"))


@app.get("/healthz")
def healthz():
    return "ok", 200

# =========================================================
# 🏁 Start
# =========================================================
if __name__ == "__main__":
    # Wichtig: DB init nur einmal; hier optional create_all(), falls gebraucht:
    # with app.app_context():
    #     db.create_all()
    app.run(host="0.0.0.0", port=5002, debug=True)
