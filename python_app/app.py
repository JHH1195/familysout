# 📦 Imports & Konfiguration
from dotenv import load_dotenv
load_dotenv()
import os
import re
import pytesseract
import stripe
import locale
import urllib.parse
import io
from datetime import datetime
from PIL import Image
from flask import Flask, render_template, request, g, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.orm import sessionmaker
from sqlalchemy import or_, cast, String, create_engine
from models import Event, Session, User
from flask import g
from ics import Calendar, Event as ICS_Event
from urllib.parse import quote

# 📁 Setup: Datenbank & Session
engine = create_engine("sqlite:///events.db")
Session = sessionmaker(bind=engine)
session = Session()

# ✅ Admin-User automatisch anlegen
existing_user = session.query(User).filter_by(email="admin@flotti.de").first()
admin = session.query(User).filter_by(email="admin@flotti.de").first()
if admin and not admin.is_premium:
    admin.is_premium = True
    session.commit()
    print("✅ Admin hat jetzt Flotti+")
if not existing_user:
    user = User(email="admin@flotti.de", firstname="Flotti", lastname="Admin", city="Flottistadt")
    user.set_password("flottipass")
    session.add(user)
    session.commit()
    print("✅ Admin-Nutzer wurde neu angelegt.")
else:
    print(f"ℹ️ Admin-Nutzer existiert bereits: {existing_user.email}")

# 🚀 Flask-App initialisieren
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "flottikarotti")

# 🔐 Login-Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    session = Session()
    return session.query(User).get(int(user_id))

# 📂 Upload-Ordner
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# 🌍 Lokale Zeit- und Sprachformate
try:
    locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")
except locale.Error:
    locale.setlocale(locale.LC_TIME, "C")  # Fallback


# 🇩🇪/🇬🇧Globale Sprache
@app.before_request
def detect_lang():
    g.lang = request.args.get("lang") or "de"

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

@app.context_processor
def inject_lang_and_translations():
    return {
        "lang": g.lang,
        "t": translations.get(g.lang, translations["de"])
    }


# 📅 Hilfsfunktion: Datum formatieren
def format_event_datetime(date_raw):
    try:
        if isinstance(date_raw, datetime):
            dt = date_raw
        elif isinstance(date_raw, str):
            try:
                dt = datetime.strptime(date_raw, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    dt = datetime.strptime(date_raw, "%Y-%m-%d")
                except ValueError:
                    return "Datum unbekannt"
        else:
            return "Datum unbekannt"

        weekday = dt.strftime("%A")
        time_str = dt.strftime("%H:%M").replace(":00", " Uhr") if dt.hour else ""
        date_str = dt.strftime("%d.%m.%Y")
        return f"{weekday}, {time_str} ({date_str})".strip().replace(" ,", ",")
    except Exception:
        return "Datum unbekannt"
    # 🔧 OCR-Unterstützung
try:
    from pdf2image import convert_from_path
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False

def extract_text_from_file(path):
    ext = os.path.splitext(path)[-1].lower()
    if ext in [".jpg", ".jpeg", ".png"]:
        return pytesseract.image_to_string(Image.open(path), lang="deu")
    elif ext == ".pdf" and PDF_ENABLED:
        images = convert_from_path(path, dpi=300, first_page=1, last_page=1)
        if images:
            return pytesseract.image_to_string(images[0], lang="deu")
    raise ValueError("Nur Bilder (.jpg, .png) oder PDFs unterstützt.")

def extract_multiple_events(text):
    blocks = re.split(r"\b(?:\d{1,2}\.\s?[–-]?\s?\d{1,2}\.\s?\w+|\d{1,2}\.\s?\w+)", text)
    blocks = [b.strip() for b in blocks if b.strip()]
    results = []
    for block in blocks:
        title = re.search(r"(Festival|Turnier|Kaltblutrennen|Show|Konzert|Fest)", block, re.IGNORECASE)
        date = re.search(r"\d{1,2}\.\s?[–-]?\s?\d{1,2}\.\s?\w+\s?[’']?\d{2,4}|\d{1,2}\.\s?\w+\s?[’']?\d{2,4}", block)
        time = re.search(r"(ab\s?\d{1,2}\s?Uhr|ca\.\s?\d{1,2}[:.]?\d{2}\s?Uhr)", block)
        location = re.search(r"\d{5}\s[A-ZÄÖÜ][a-zäöüß]+", text)
        results.append({
            "title": title.group(0) if title else "ohne Titel",
            "date": date.group(0) if date else "",
            "time": time.group(0) if time else "",
            "location": location.group(0) if location else "Ort unbekannt",
            "description": block[:300]
        })
    return results

# 📍 Startseite
@app.route("/")
def index():
    return render_template("index.html")

# 🔎 Suchergebnisse anzeigen
@app.route("/results")
def suchergebnisse():
    session = Session()
    query = request.args.get("q", "").lower()
    location_filter = request.args.get("location", "").lower()
    category_filter = request.args.get("category", "").lower()
    date_filter = request.args.get("date", "").strip()

    categories = sorted({event.category for event in session.query(Event).all() if event.category})
    events_query = session.query(Event)

    # Filter anwenden
    if query.strip():
        events_query = events_query.filter(
            Event.title.ilike(f"%{query}%") |
            Event.description.ilike(f"%{query}%") |
            Event.location.ilike(f"%{query}%")
        )
    if location_filter.strip():
        events_query = events_query.filter(Event.location.ilike(f"%{location_filter}%"))
    if category_filter.strip():
        events_query = events_query.filter(Event.category.ilike(f"%{category_filter}%"))
    if date_filter.strip():
        events_query = events_query.filter(cast(Event.date, String).ilike(f"%{date_filter}%"))

    events = events_query.order_by(Event.date.asc()).all()

    for event in events:
        if isinstance(event.date, str):
            try:
                event.date = datetime.strptime(event.date, "%Y-%m-%d")
            except ValueError:
                pass

    session.close()
    return render_template("results.html", events=events,
                           query=query,
                           location_filter=location_filter,
                           category_filter=category_filter,
                           date_filter=date_filter,
                           categories=categories)

# 📄 Event-Detailseite anzeigen
@app.route("/event/<int:event_id>")
def event_detail(event_id):
    session = Session()
    event = session.query(Event).get(event_id)
    # 🔐 Sicherstellen, dass date ein datetime-Objekt ist
    if isinstance(event.date, str):
        try:
            event.date = datetime.strptime(event.date, "%Y-%m-%d")
        except ValueError:
            event.date = datetime.now()  # fallback

    readable_date = format_event_datetime(event.date)
    session.close()

    # 🗓 Google Calendar Link generieren
    google_calendar_url = (
        "https://www.google.com/calendar/render"
        f"?action=TEMPLATE"
        f"&text={quote(event.title)}"
        f"&dates={event.date.strftime('%Y%m%d')}T090000Z/{event.date.strftime('%Y%m%d')}T100000Z"
        f"&details={quote(event.description or '')}"
        f"&location={quote(event.location or '')}"
    )

    return render_template("event.html", event=event, readable_date=readable_date,
                           events=[], google_calendar_url=google_calendar_url)


# 📆 Kalender Eintrag erstellen
@app.route("/event/<int:event_id>/download.ics")
def download_ics(event_id):
    session = Session()
    event = session.query(Event).get(event_id)
    if isinstance(event.date, str):
        try:
            event.date = datetime.strptime(event.date, "%Y-%m-%d")
        except ValueError:
            event.date = datetime.now()
    cal = Calendar()
    e = ICS_Event()
    e.name = event.title
    e.begin = event.date
    e.description = event.description or ""
    e.location = event.location or ""
    cal.events.add(e)
    session.close()

    file = io.StringIO(str(cal))
    return send_file(io.BytesIO(file.getvalue().encode("utf-8")),
                     mimetype="text/calendar",
                     as_attachment=True,
                     download_name=f"{event.title}.ics")
# PDF-Unterstützung optional
try:
    from pdf2image import convert_from_path
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False

# 📄 Optional: PDF → Bild konvertieren (falls installiert)
try:
    from pdf2image import convert_from_path
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False

# 🔧 Setup

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def extract_fields(text):
    def find(pattern, default="unbekannt"):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(0).strip() if match else default

    date = find(r"\d{1,2}\.\d{1,2}\.\d{2,4}")
    time = find(r"\d{1,2}[:.]\d{2}\s?(Uhr)?", default="")
    location = find(r"(Ort|in)\s[:]? ?([A-ZÄÖÜ][a-zäöüß]+(\s[A-Z][a-zäöüß]+)?)")
    age = find(r"(ab\s\d{1,2}\s(Jahre|Monate)|Kinder\s(von|ab)\s\d+)")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    title = lines[0] if lines else "ohne Titel"

    return {
        "title": title,
        "date": date,
        "time": time,
        "location": location,
        "age_group": age,
        "description": text[:1000]
    }

# ➕ Event erstellen mit OCR oder manuell
@app.route("/event-erstellen", methods=["GET", "POST"])
def event_erstellen():
    session = Session()

    if request.method == "POST":
        try:
            # 📎 Datei-Upload prüfen (Bild/PDF)
            image_file = request.files.get("summary_file")
            image_url = ""
            extracted = {}

            if image_file and image_file.filename != "":
                filename = secure_filename(image_file.filename)
                path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                image_file.save(path)
                image_url = f"/static/uploads/{filename}"

                # 🧠 OCR-Text extrahieren
                text = extract_text_from_file(path)
                extracted = extract_fields(text)

            # 📝 Werte aus dem Formular (werden genutzt oder überschreiben OCR)
            title = request.form.get("title") or extracted.get("title")
            date = request.form.get("date") or extracted.get("date")
            location = request.form.get("location") or extracted.get("location")
            description = request.form.get("description") or extracted.get("description")

            if not title or not date:
                flash("Titel oder Datum fehlt – bitte ergänzen.", "error")
                return redirect(url_for("event_erstellen"))

            # 🗓️ Datum formatieren (optional)
            try:
                date_obj = datetime.strptime(date, "%d.%m.%Y")
                date = date_obj.strftime("%Y-%m-%d")
            except:
                pass  # Falls OCR-Datum nicht formatierbar

            # 📦 Event anlegen
            event = Event(
                title=title,
                description=description,
                date=date,
                location=location,
                image_url=image_url,
                source_name="OCR/Manuell",
                source_url="",
                category="Manuell"
            )
            session.add(event)
            session.commit()

            flash("🎉 Event erfolgreich erstellt!", "success")
            return redirect(url_for("event_detail", event_id=event.id))

        except Exception as e:
            session.rollback()
            flash(f"Fehler beim Speichern: {e}", "error")
        finally:
            session.close()

    return render_template("event-erstellen.html")

# 🧩 (Ergänzt): Event-Batch aus OCR speichern
@app.route("/event-erstellen-batch", methods=["POST"])
def event_erstellen_batch():
    session = Session()
    try:
        events = request.form.to_dict(flat=False)
        count = 0
        for i in range(len(events["events[0][title]"])):
            title = request.form.get(f"events[{i}][title]")
            date = request.form.get(f"events[{i}][date]")
            location = request.form.get(f"events[{i}][location]")
            description = request.form.get(f"events[{i}][description]")
            if title and date:
                event = Event(
                    title=title,
                    date=date,
                    location=location,
                    description=description,
                    source_name="OCR",
                    source_url="",
                    category="OCR"
                )
                session.add(event)
                count += 1
        session.commit()
        flash(f"🎉 {count} Events gespeichert.", "success")
    except Exception as e:
        session.rollback()
        flash(f"❌ Fehler: {e}", "error")
    finally:
        session.close()
    return redirect(url_for("index"))
from flask import jsonify

@app.route("/ocr-upload", methods=["POST"])
def ocr_upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Keine Datei erhalten."}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    try:
        text = extract_text_from_file(filepath)
        events = extract_multiple_events(text)

        if not events:
            return jsonify({"error": "Kein verwertbarer Text erkannt"}), 422

        # Nur erstes Event zurückgeben (optional für Preview)
        return jsonify(events[0])

        # Oder alle Vorschläge zurückgeben:
        # return jsonify(events)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 👤 Registrierung
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        session = Session()
        email = request.form["email"]
        firstname = request.form["firstname"]
        lastname = request.form["lastname"]
        password = request.form["password"]
        password_repeat = request.form["password_repeat"]
        city = request.form.get("city")

        if session.query(User).filter_by(email=email).first():
            flash("Diese E-Mail ist bereits registriert.", "danger")
            return redirect(url_for("register"))
        if password != password_repeat:
            flash("Passwörter stimmen nicht überein.", "danger")
            return redirect(url_for("register"))

        user = User(email=email, firstname=firstname, lastname=lastname, city=city)
        user.set_password(password)
        session.add(user)
        session.commit()

        login_user(user)
        flash("Willkommen bei Flotti!", "success")
        return redirect(url_for("profil"))
    return render_template("register.html")

# 🔐 Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session = Session()
        email = request.form["email"]
        password = request.form["password"]
        user = session.query(User).filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Erfolgreich eingeloggt", "success")
            return redirect(url_for("profil"))
        else:
            flash("Falsche E-Mail oder Passwort", "danger")
    return render_template("login.html")

# 👤 Nutzerprofil anzeigen
@app.route("/profil")
@login_required
def profil():
    return render_template("profil.html", user=current_user)

# Profilbild hinzufügen
@app.route("/profilbild-upload", methods=["POST"])
@login_required
def profilbild_upload():
    file = request.files.get("profilbild")
    if file and file.filename:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        session = Session()
        user = session.query(User).get(current_user.id)
        user.profile_image = filename
        session.commit()
        session.close()
        flash("✅ Profilbild aktualisiert", "success")

    return redirect(url_for("profil"))

# 🚪 Logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

# 💳 Stripe-Checkout (Abo starten)
@app.route("/checkout")
@login_required
def checkout():
    session = Session()
    if not current_user.stripe_customer_id:
        customer = stripe.Customer.create(email=current_user.email)
        current_user.stripe_customer_id = customer.id
        session.commit()

    checkout_session = stripe.checkout.Session.create(
        customer=current_user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": "price_ABC123", "quantity": 1}],
        mode="subscription",
        success_url=url_for("profil", _external=True),
        cancel_url=url_for("preise", _external=True),
    )
    return redirect(checkout_session.url, code=303)

# 💶 Preise
@app.route("/preise")
def preise():
    return render_template("preise.html")

#Impressum
@app.route("/impressum")
def impressum():
    return render_template("impressum.html")

#Datenschutz
@app.route("/datenschutz")
def datenschutz():
    return render_template("datenschutz.html")

#Nutzungsbedingungen
@app.route("/nutzungsbedingungen")
def nutzungsbedingungen():
    return render_template("nutzungsbedingungen.html")

#Über uns
@app.route("/ueber-uns")
def ueber_uns():
    return render_template("ueber_uns.html")

#So funktionierts
@app.route("/so-funktionierts")
def so_funktionierts():
    return render_template("so_funktionierts.html")

#Vorgaben
@app.route("/vorgaben")
def vorgaben():
    return render_template("vorgaben.html")


# 📩 Stripe Webhook-Handler
@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('stripe-signature')
    endpoint_secret = "whsec_..."

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError:
        return "Invalid signature", 400

    if event["type"] == "checkout.session.completed":
        session_data = event["data"]["object"]
        customer_id = session_data["customer"]
        subscription_id = session_data["subscription"]

        db = Session()
        user = db.query(User).filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.stripe_subscription_id = subscription_id
            user.is_premium = True
            db.commit()
    return "", 200

# 📆 Jahr dynamisch im Footer
@app.context_processor
def inject_year():
    return {"current_year": datetime.now().year}

# 🏁 Start der App
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
