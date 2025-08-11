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
from datetime import datetime, date
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv()

# Flask & Erweiterungen
from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify,
    send_from_directory, send_file, abort, g
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

# Datenbank & Models
from sqlalchemy import cast, String
from db import engine, SessionLocal
from models import Event, User

# OCR & Bildverarbeitung
from PIL import Image
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
UPLOAD_FOLDER = os.getenv("UPLOAD_DIR", "static/uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

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

# =========================================================
# 🛠 Hilfsfunktionen
# =========================================================
def format_event_datetime(date_raw):
    """Formatiert ein Datum für die Anzeige."""
    try:
        if isinstance(date_raw, datetime):
            dt = date_raw
        elif isinstance(date_raw, str):
            try:
                dt = datetime.strptime(date_raw, "%Y-%m-%d %H:%M")
            except ValueError:
                dt = datetime.strptime(date_raw, "%Y-%m-%d")
        else:
            return "Datum unbekannt"

        weekday = dt.strftime("%A")
        time_str = dt.strftime("%H:%M").replace(":00", " Uhr") if dt.hour else ""
        date_str = dt.strftime("%d.%m.%Y")
        return f"{weekday}, {time_str} ({date_str})".strip().replace(" ,", ",")
    except Exception:
        return "Datum unbekannt"

def _guess_year(month: int) -> int:
    today = date.today()
    return today.year + (1 if month < today.month else 0)

def _norm_time(s: str) -> str:
    s = s.replace("Uhr", "").strip().replace(".", ":")
    m = re.match(r"(\d{1,2})[:h\.]?(\d{2})?", s)
    return f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}" if m else ""

# =========================================================
# 📄 OCR-Funktionen
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
        for d in filter(None, [d1, d2]):
            try:
                dates.append(date(year, month, int(d)).isoformat())
            except ValueError:
                pass

    singles = re.findall(r"\b(\d{1,2})\.(\d{1,2})\b", text)
    for d, m in singles:
        month = int(m)
        year = _guess_year(month)
        iso = date(year, month, int(d)).isoformat()
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
# 📍 Event-Routen
# =========================================================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/results")
def suchergebnisse():
    s = Session()
    query = request.args.get("q", "").lower()
    location_filter = request.args.get("location", "").lower()
    category_filter = request.args.get("category", "").lower()
    date_filter = request.args.get("date", "").strip()

    categories = sorted({event.category for event in s.query(Event).all() if event.category})
    events_query = s.query(Event)

    if query:
        events_query = events_query.filter(
            Event.title.ilike(f"%{query}%") |
            Event.description.ilike(f"%{query}%") |
            Event.location.ilike(f"%{query}%")
        )
    if location_filter:
        events_query = events_query.filter(Event.location.ilike(f"%{location_filter}%"))
    if category_filter:
        events_query = events_query.filter(Event.category.ilike(f"%{category_filter}%"))
    if date_filter:
        events_query = events_query.filter(cast(Event.date, String).ilike(f"%{date_filter}%"))

    events = events_query.order_by(Event.date.asc()).all()
    s.close()
    return render_template("results.html", events=events,
                           query=query, location_filter=location_filter,
                           category_filter=category_filter,
                           date_filter=date_filter, categories=categories)

@app.route("/event/<int:event_id>")
def event_detail(event_id):
    s = Session()
    event = s.query(Event).get(event_id)
    readable_date = format_event_datetime(event.date)
    s.close()

    google_calendar_url = (
        "https://www.google.com/calendar/render"
        f"?action=TEMPLATE"
        f"&text={quote(event.title)}"
        f"&dates={event.date.strftime('%Y%m%d')}T090000Z/{event.date.strftime('%Y%m%d')}T100000Z"
        f"&details={quote(event.description or '')}"
        f"&location={quote(event.location or '')}"
    )

    return render_template("event.html", event=event, readable_date=readable_date,
                           google_calendar_url=google_calendar_url)

@app.route("/event/<int:event_id>/download.ics")
def download_ics(event_id):
    s = Session()
    event = s.query(Event).get(event_id)
    cal = Calendar()
    e = ICS_Event()
    e.name = event.title
    e.begin = event.date
    e.description = event.description or ""
    e.location = event.location or ""
    cal.events.add(e)
    s.close()

    file = io.StringIO(str(cal))
    return send_file(io.BytesIO(file.getvalue().encode("utf-8")),
                     mimetype="text/calendar",
                     as_attachment=True,
                     download_name=f"{event.title}.ics")

@app.route("/event-erstellen", methods=["GET", "POST"])
def event_erstellen():
    s = Session()
    if request.method == "POST":
        try:
            image_file = request.files.get("summary_file")
            image_url, extracted = "", {}
            if image_file and image_file.filename:
                filename = secure_filename(image_file.filename)
                path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                image_file.save(path)
                image_url = f"/static/uploads/{filename}"
                text = extract_text_from_file(path)
                extracted = extract_multiple_events(text)[0]

            title = request.form.get("title") or extracted.get("title")
            date_val = request.form.get("date") or extracted.get("date")
            location = request.form.get("location") or extracted.get("location")
            description = request.form.get("description") or extracted.get("description")

            if not title or not date_val:
                flash("Titel oder Datum fehlt.", "error")
                return redirect(url_for("event_erstellen"))

            event = Event(
                title=title, description=description, date=date_val,
                location=location, image_url=image_url,
                source_name="OCR/Manuell", category="Manuell"
            )
            s.add(event)
            s.commit()
            flash("🎉 Event erstellt!", "success")
            return redirect(url_for("event_detail", event_id=event.id))
        except Exception as e:
            s.rollback()
            flash(f"Fehler: {e}", "error")
        finally:
            s.close()
    return render_template("event-erstellen.html")

@app.route("/ocr-upload", methods=["POST"])
def ocr_upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Keine Datei erhalten."}), 400
    filename = secure_filename(file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)
    try:
        text = extract_text_from_file(path)
        events = extract_multiple_events(text)
        if not events:
            return jsonify({"error": "Kein Text erkannt"}), 422
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
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        s = Session()
        user = s.query(User).filter_by(email=request.form["email"]).first()
        if user and user.check_password(request.form["password"]):
            login_user(user)
            flash("Erfolgreich eingeloggt", "success")
            return redirect(url_for("profil"))
        flash("Falsche E-Mail oder Passwort", "danger")
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
    if not current_user.stripe_customer_id:
        customer = stripe.Customer.create(email=current_user.email)
        current_user.stripe_customer_id = customer.id
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

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception:
        return "Invalid payload", 400

    if event["type"] == "checkout.session.completed":
        data = event["data"]["object"]
        s = Session()
        user = s.query(User).filter_by(stripe_customer_id=data["customer"]).first()
        if user:
            user.stripe_subscription_id = data["subscription"]
            user.is_premium = True
            s.commit()
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

# =========================================================
# 🛠 Admin-Tools & Crawler
# =========================================================
@app.post("/ingest/batch")
def ingest_batch():
    token = request.headers.get("X-Task-Token")
    if token != os.getenv("CRAWLER_TOKEN"):
        abort(401)
    payload = request.get_json(force=True)
    if not isinstance(payload, list):
        return jsonify({"error": "Body muss eine JSON-Liste sein"}), 400

    s = Session()
    saved = 0
    for e in payload:
        if not e.get("title") or not e.get("date"):
            continue
        evt = Event(
            title=e["title"], description=(e.get("description") or "")[:1000],
            date=e["date"], location=e.get("location") or "",
            image_url=e.get("image_url") or "", source_name=e.get("source_name") or "crawler",
            source_url=e.get("source_url") or "", category=e.get("category") or "Crawler"
        )
        s.add(evt)
        saved += 1
    s.commit()
    s.close()
    return jsonify({"status": "ok", "saved": saved}), 200

@app.get("/admin/diag")
@login_required
def admin_diag():
    if not getattr(current_user, "is_admin", False):
        abort(403)
    def cmd_version(bin):
        p = shutil.which(bin)
        if not p: return f"{bin}: not found"
        try:
            return subprocess.check_output([p, "--version"], text=True).splitlines()[0]
        except Exception as e:
            return f"{bin}: {e}"
    return {
        "tesseract": cmd_version("tesseract"),
        "poppler(pdftoppm)": cmd_version("pdftoppm"),
        "upload_dir": app.config["UPLOAD_FOLDER"],
        "db_driver": str(engine.url.drivername)
    }

# =========================================================
# 🏁 Start
# =========================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
