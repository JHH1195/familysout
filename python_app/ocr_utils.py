# ocr_utils.py
from __future__ import annotations
import os, re, sys, json, importlib, subprocess
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from datetime import date as _date

from PIL import Image, ImageFilter, ImageOps
import pytesseract
from pdf2image import convert_from_path

# ---------------------------------- Config ----------------------------------
LANGS = "deu+eng"
TESS_CONFIGS = [r'--oem 3 --psm 6', r'--oem 3 --psm 11', r'--oem 3 --psm 4']
USE_PADDLE = os.getenv("OCR_ENGINE", "tesseract").lower().startswith("paddle")
PADDLE_TIMEOUT_SEC = int(os.getenv("PADDLE_TIMEOUT_SEC", "25"))

# --------------------------------- Dataclass --------------------------------
@dataclass
class OCRResult:
    text: str
    fields: Dict[str, Any]
    found: List[str]
    missing: List[str]
    confidence: Dict[str, float]
    candidates: List[Dict[str, Any]]

# ------------------------------- Regex/Heuristik -----------------------------
MONTH_WORDS = {
    'jan':1,'feb':2,'mär':3,'mrz':3,'apr':4,'mai':5,'jun':6,'jul':7,'aug':8,'sep':9,'sept':9,'okt':10,'nov':11,'dez':12
}
TIME_RE = re.compile(r'\b(\d{1,2})[:\.h ](\d{2})\s*(?:uhr)?\b', re.I)
DATE_FULL_RE = re.compile(r'\b(\d{1,2})\s*[\.\-/]\s*(\d{1,2})\s*[\.\-/]\s*(\d{2,4})\b')
DATE_DM_RE = re.compile(r'\b(\d{1,2})\s*[\.\-/]\s*(\d{1,2})(?!\s*[\.\-/]\s*\d)\b')
DATE_WORD_RE = re.compile(r'\b(\d{1,2})\.\s*(Jan|Feb|Mär|Mrz|Apr|Mai|Jun|Jul|Aug|Sep|Sept|Okt|Nov|Dez)\w*\.?,?\s*(\d{2,4})?\b', re.I)
PRICE_RE = re.compile(r'(\d{1,3}(?:[\.\,]\d{3})*(?:[\.\,]\d{2}))\s*(?:€|EUR)\b')
URL_RE   = re.compile(r'(https?://[^\s\)\]]+|www\.[^\s\)\]]+)', re.I)
FREE_HINTS   = ['eintritt frei','kostenlos','gratis','ohne eintritt','frei']
OUTDOOR_HINTS= ['open air','open-air','freiluft','park','platz','festivalgelände','strand','garten']
LOCATION_HINTS=['Theater Brand','Buchhandlung am Markt','Stadthalle','Rathaus','Markt','Park','Platz','Kirche','Haus','Theater','Bürgerhaus','Bürgerzentrum']

# ---------------------------------- Utils -----------------------------------
def _normalize_text(t: str) -> str:
    if not t: return ""
    t = t.replace("\u00a0"," ").replace("•"," ").replace("·"," ").replace("●"," ")
    t = re.sub(r'[–—]', '-', t)
    return t

def _guess_year(month: int) -> int:
    today = _date.today()
    return today.year + (1 if month < today.month else 0)

def _preprocess_pil(img: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    bw = gray.point(lambda x: 0 if x < 140 else 255, mode='1')
    return bw.convert("L")

def _preprocess_cv2(path: str) -> Optional[Image.Image]:
    try:
        cv2 = importlib.import_module("cv2")
    except Exception:
        return None
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None: return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 31, 15)
    return Image.fromarray(bw)

def _avg_conf_from_data(d: dict) -> float:
    confs = []
    for c in d.get("conf", []):
        try:
            v = float(c); 
            if v >= 0: confs.append(v)
        except: pass
    return float(sum(confs)/len(confs)) if confs else 0.0

# ------------------------------- Tesseract OCR -------------------------------
def _ocr_passes(pil_img: Image.Image) -> Tuple[str, float, dict]:
    best_text, best_conf, best_data = "", 0.0, {}
    for cfg in TESS_CONFIGS:
        data = pytesseract.image_to_data(pil_img, lang=LANGS, config=cfg, output_type=pytesseract.Output.DICT)
        text = " ".join([t for t in data.get("text", []) if t])
        conf = _avg_conf_from_data(data)
        if conf > best_conf:
            best_text, best_conf, best_data = text, conf, data
    return best_text, best_conf, best_data

def _ocr_with_tesseract(path: str) -> Tuple[str, float, List[dict]]:
    img = _preprocess_cv2(path)
    t1, c1, d1 = ("", 0.0, {})
    if img is not None:
        t1, c1, d1 = _ocr_passes(img)
    pil = Image.open(path)
    pil = _preprocess_pil(pil)
    t2, c2, d2 = _ocr_passes(pil)
    # Map to unified "lines"
    text, conf, data = (t2, c2, d2) if c2 >= c1 else (t1, c1, d1)
    lines = []
    n = len(data.get("text", []))
    for i in range(n):
        t = (data["text"][i] or "").strip()
        if not t: continue
        try:
            x, y, w, h = int(data["left"][i]), int(data["top"][i]), int(data["width"][i]), int(data["height"][i])
            c = float(data["conf"][i]) if float(data["conf"][i]) >= 0 else 0.0
        except Exception:
            continue
        lines.append({"text": t, "conf": c, "bbox": (x, y, x+w, y+h), "height": h})
    lines.sort(key=lambda l: (round(l["bbox"][1]/15), l["bbox"][0]))
    return text, conf, lines

# --------------------------- Paddle via Subprozess ---------------------------
def _ocr_with_paddle_subprocess(path: str, timeout_sec: int = PADDLE_TIMEOUT_SEC) -> Tuple[str, float, List[dict]]:
    """Startet diesen Code als Worker-Prozess, der PaddleOCR importiert.
       Gibt (text, avg_conf, lines) zurück. Timeouts/Fehler → Exception."""
    cmd = [sys.executable, os.path.abspath(__file__), "--paddle-worker", path]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "Paddle worker failed")
    try:
        payload = json.loads(proc.stdout.strip())
        return payload["text"], float(payload["avg_conf"]), payload["lines"]
    except Exception as e:
        raise RuntimeError(f"Paddle worker invalid JSON: {e}")

# ------------------------------ Field Parsing -------------------------------
def _extract_dates(text: str) -> List[str]:
    dates: set[str] = set()
    # dd.mm.yyyy
    for d, m, y in DATE_FULL_RE.findall(text):
        try:
            year = int(y) if len(y) == 4 else 2000 + int(y)
            month = int(m); day = int(d)
            _ = _date(year, month, day)
            dates.add(f"{year:04d}-{month:02d}-{day:02d}")
        except: pass
    # dd.mm
    for d, m in DATE_DM_RE.findall(text):
        # wenn dd.mm.yyyy schon existiert, skip duplicates
        if re.search(rf'\b{re.escape(d)}\s*[\.\-/]\s*{re.escape(m)}\s*[\.\-/]\s*\d{{2,4}}\b', text):
            continue
        try:
            month = int(m); day = int(d)
            year = _guess_year(month)
            _ = _date(year, month, day)
            dates.add(f"{year:04d}-{month:02d}-{day:02d}")
        except: pass
    # 12. Aug 2025
    for d, mw, y in DATE_WORD_RE.findall(text):
        try:
            day = int(d); mw = mw.lower()
            month = next((v for k,v in MONTH_WORDS.items() if mw.startswith(k)), 0)
            if not month: continue
            year = int(y) if y else _guess_year(month)
            if len(str(year)) == 2: year = 2000 + int(year)
            _ = _date(year, month, day)
            dates.add(f"{year:04d}-{month:02d}-{day:02d}")
        except: pass
    return sorted(dates)

def _extract_time(text: str) -> Optional[str]:
    m = TIME_RE.search(text)
    if not m: return None
    try:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    except: return None

def _find_prices(text: str) -> List[float]:
    vals = []
    for raw in PRICE_RE.findall(text):
        try: vals.append(float(raw.replace('.','').replace(',','.')))
        except: pass
    return vals

def _guess_is_free(text: str, prices: List[float]) -> Optional[bool]:
    t = text.lower()
    if any(h in t for h in FREE_HINTS): return True
    if prices: return False
    return None

def _guess_location(text: str) -> Optional[str]:
    for hint in LOCATION_HINTS:
        if re.search(re.escape(hint), text, flags=re.I):
            return hint
    m = re.search(r'([A-Za-zÄÖÜäöüß\.\- ]+\s\d{1,4}[a-zA-Z]?,\s?\d{4,5}\s[A-Za-zÄÖÜäöüß\.\- ]+)', text)
    return m.group(1) if m else None

def _guess_title(lines: List[dict], raw_text: str) -> Optional[str]:
    # nimm Zeile mit größter Boxhöhe ohne typische Metawörter
    blacklist = {'datum','zeit','uhr','eintritt','preis','ort','adresse','location','tickets','info','jeweils','vorführungen','vorfuehrungen'}
    scored = []
    for L in lines:
        txt = (L.get("text") or "").strip()
        if len(txt) < 4: continue
        if any(b in txt.lower() for b in blacklist): continue
        score = L.get("height", 0) * (1 + (1 if txt.isupper() else 0))
        scored.append((score, txt))
    if scored:
        scored.sort(reverse=True)
        return scored[0][1][:160]
    # Fallback: erste brauchbare Zeile aus Volltext
    for ln in (raw_text or "").splitlines():
        ln = ln.strip()
        if len(ln) > 4 and not re.search(r'(datum|uhr|eintritt|preis|ort|adresse|tickets)', ln, re.I):
            return ln[:160]
    return None

def _guess_category(text: str) -> str:
    t = text.lower()
    if re.search(r'theater|theaterst(ü|u)ck', t): return "Theater"
    if 'zirkus' in t or 'kinder' in t or 'familie' in t: return "Familie"
    if 'konzert' in t or 'musik' in t: return "Konzert"
    return "Sonstiges"

def _any_url(text: str) -> Optional[str]:
    m = URL_RE.search(text)
    if not m: return None
    u = m.group(1)
    return "http://" + u if u.startswith("www.") else u

def _guess_outdoor(text: str) -> Optional[bool]:
    t = text.lower()
    return True if any(h in t for h in OUTDOOR_HINTS) else None

# ---------------------------- Public API (Main) ------------------------------
def extract_event_fields_from_path(path: str) -> OCRResult:
    # 1) OCR (Paddle → Subprozess, sonst Tesseract)
    if USE_PADDLE:
        try:
            text, base_conf, lines = _ocr_with_paddle_subprocess(path, timeout_sec=PADDLE_TIMEOUT_SEC)
        except Exception:
            text, base_conf, lines = _ocr_with_tesseract(path)
    else:
        text, base_conf, lines = _ocr_with_tesseract(path)

    raw_text = _normalize_text(text or "")
    oneline  = re.sub(r'\s+', ' ', raw_text)

    # 2) Kernfelder
    dates = _extract_dates(oneline)
    time  = _extract_time(oneline)
    prices = _find_prices(oneline)
    price  = min(prices) if prices else None
    is_free = _guess_is_free(oneline, prices)
    title = _guess_title(lines, raw_text)
    location = _guess_location(oneline)
    category = _guess_category(oneline)
    age_group = None
    m_age = re.search(r'\bab\s*(\d{1,2})\s*(?:J|Jahre|Jahren)\b', oneline, flags=re.I)
    if m_age: age_group = f"ab {m_age.group(1)} Jahren"
    elif re.search(r'Kinder|Familie|Kids', oneline, flags=re.I):
        age_group = "Familie/Kinder"
    source_url = _any_url(oneline)
    is_outdoor = _guess_outdoor(oneline)

    base_fields = {
        "title": title,
        "description": raw_text[:1000] if raw_text else None,
        "location": location,
        "category": category or "Unbekannt",
        "maps_url": None,
        "source_url": source_url,
        "source_name": None,
        "lat": None,
        "lon": None,
        "price": price,
        "is_free": is_free,
        "is_outdoor": is_outdoor,
        "age_group": age_group,
        "image_url": None
    }

    # 3) Kandidaten (ein Event pro Datum)
    candidates: List[Dict[str, Any]] = []
    if dates:
        for d in dates:
            c = dict(base_fields)
            c["date"] = f"{d} {time}" if time else d
            c["time"] = time
            candidates.append(c)
    else:
        c = dict(base_fields); c["date"] = None; c["time"] = time
        candidates.append(c)

    fields = dict(candidates[0])

    keys = ["title","description","date","time","location","image_url","maps_url","source_url","source_name","lat","lon","price","is_free","is_outdoor","age_group","category"]
    found = [k for k in keys if fields.get(k) not in (None, "", [])]
    missing = [k for k in keys if k not in found]
    conf_val = max(min(float(base_conf)/100.0, 1.0), 0.0)
    confidence = {k: conf_val for k in keys}

    return OCRResult(text=raw_text, fields=fields, found=found, missing=missing, confidence=confidence, candidates=candidates)

# ----------------------------- Helper CLI Worker -----------------------------
# Wird von _ocr_with_paddle_subprocess() aufgerufen.
# Führt PaddleOCR NUR in einem Subprozess aus und gibt JSON nach stdout.
def _paddle_worker(image_path: str) -> int:
    try:
        from paddleocr import PaddleOCR  # type: ignore # Import hier → isoliert
    except Exception as e:
        sys.stderr.write(f"IMPORT_ERROR: {e}\n")
        return 2
    try:
        ocr = PaddleOCR(lang='german', use_angle_cls=False, show_log=False)
        result = ocr.ocr(image_path, cls=False)
        lines = []
        text_chunks = []
        confs = []
        if result and result[0]:
            for det in result[0]:
                box, (txt, conf) = det
                if not txt: continue
                xs = [p[0] for p in box]; ys = [p[1] for p in box]
                x_min, y_min, x_max, y_max = min(xs), min(ys), max(xs), max(ys)
                h = y_max - y_min
                lines.append({"text": txt, "conf": float(conf), "bbox": [x_min, y_min, x_max, y_max], "height": h})
                text_chunks.append(txt); confs.append(float(conf))
        payload = {
            "text": " ".join(text_chunks),
            "avg_conf": float(sum(confs)/len(confs)) if confs else 0.0,
            "lines": lines
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as e:
        sys.stderr.write(str(e))
        return 1

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--paddle-worker":
        sys.exit(_paddle_worker(sys.argv[2]))
