# 📦 Imports & Konfiguration
from dotenv import load_dotenv
load_dotenv()

import os
import stripe
import locale
import tempfile
import pytesseract
import re
from PIL import Image
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.orm import sessionmaker
from sqlalchemy import cast, String, create_engine

from python_app.models import Event, Session, User

# 📁 Setup: Datenbank & Session
engine = create_engine("sqlite:///events.db")
Session = sessionmaker(bind=engine)
session = Session()

# ✅ Admin-User automatisch anlegen
admin = session.query(User).filter_by(email="admin@flotti.de").first()
if not admin:
    admin = User(email="admin@flotti.de", firstname="Flotti", lastname="Admin", city="Flottistadt")
    admin.set_password("flottipass")
    session.add(admin)
    session.commit()
    print("✅ Admin-Nutzer angelegt.")
else:
    print(f"ℹ️ Admin existiert: {admin.email}")

# 🚀 Flask-App initialisieren
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "flottikarotti")

# 🔐 Login-Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return Session().query(User).get(int(user_id))

# 📂 Upload-Verzeichnis
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# 🌍 Lokale Sprache
locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")

# 🧠 Datum formatieren
def format_event_datetime(date_raw):
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

        now = datetime.now()
        weekday = dt.strftime("%A")
        time_str = dt.strftime("%H:%M").replace(":00", " Uhr") if dt.hour else ""
        date_str = dt.strftime("%d.%m.%Y")
        return f"{weekday}, {time_str} ({date_str})".strip().replace(" ,", ",")
    except Exception as e:
        print("🛠 Fehler beim Datumsformat:", e)
        return "Datum unbekannt"

# 🧠 OCR-Helfer
try:
    from pdf2image import convert_from_path
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False

def extract_text_from_file(file_path):
    ext = os.path.splitext(file_path)[-1].lower()
    if ext in [".jpg", ".jpeg", ".png"]:
        return pytesseract.image_to_string(Image.open(file_path), lang="deu")
    elif ext == ".pdf" and PDF_ENABLED:
        images = convert_from_path(file_path, dpi=300, first_page=1, last_page=1)
        return pytesseract.image_to_string(images[0], lang="deu") if images else ""
    return ""

def extract_fields(text):
    def find(pattern, default="unbekannt"):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(0).strip() if match else default

    date = find(r"\d{1,2}\.\d{1,2}\.\d{2,4}")
    time = find(r"\d{1,2}[:.]\d{2}\s?(Uhr)?", "")
    location = find(r"(Ort|in)\s[:]?\s?[A-ZÄÖÜ][a-zäöüß]+")
    age = find(r"(ab\s\d{1,2}\s(Jahre|Monate)|Kinder\s(von|ab)\s\d+)")
    title = next((l.strip() for l in text.split("\n") if l.strip()), "ohne Titel")

    return {
        "title": title, "date": date, "time": time,
        "location": location, "age_group": age,
        "description": text[:1000]
    }

# 📄 Weitere Routen folgen...