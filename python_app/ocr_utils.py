import pytesseract
from PIL import Image
import re
import tempfile
import os

# 📄 Optional: PDF → Bild konvertieren (falls notwendig)
try:
    from pdf2image import convert_from_path
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False

def extract_text_from_file(file_path):
    ext = os.path.splitext(file_path)[-1].lower()
    text = ""

    if ext in [".jpg", ".jpeg", ".png"]:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image, lang="deu")

    elif ext == ".pdf" and PDF_ENABLED:
        images = convert_from_path(file_path, dpi=300, first_page=1, last_page=1)
        if images:
            text = pytesseract.image_to_string(images[0], lang="deu")
    else:
        raise ValueError("Nur Bilder (.jpg, .png) oder PDFs unterstützt.")

    return text


def extract_fields(text):
    def find(pattern, default="unbekannt"):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(0).strip() if match else default

    # 📅 Einfaches Datum (z. B. 21.07.2025)
    date = find(r"\d{1,2}\s?[.–]\s?\d{1,2}\.\s?\w+\s?[‘']?\d{2,4}")

    # ⏰ Uhrzeit
    time = find(r"ab\s\d{1,2}\s?Uhr|ca\.\s?\d{1,2}[:.]?\d{2}\s?Uhr")

    # 📍 Ort (einfacher Trigger: z. B. hinter „Ort:“ oder „in ...“)
    location = find(r"\d{5}\s[A-ZÄÖÜ][a-zäöüß]+")

    # 🧒 Altersgruppe (optional)
    age = find(r"(ab\s\d{1,2}\s(Jahre|Monate)|Kinder\s(von|ab)\s\d+)")

    # 🧾 Titel aus erstem Satz oder Großschreibung
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    title = lines[0] if lines else "ohne Titel"

    return {
        "title": title,
        "date": date,
        "time": time,
        "location": location,
        "age_group": age,
        "description": text[:1000]  # optional begrenzt
    }
