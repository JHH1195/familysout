# FamilySout – Veranstaltungs-Crawler 🗓️

**FamilySout** ist eine Flask-basierte Web-App mit integriertem Crawler zur Erfassung und Verwaltung von Veranstaltungen aus verschiedenen Quellen – lokal oder online. Ziel ist eine zentrale Oberfläche für mehrere Nutzer*innen, mit Fokus auf Familien-Events.

---

## 🔧 Features

- 🕵️‍♀️ Automatischer Event-Crawler (in Entwicklung)
- 📋 Admin-Oberfläche zur Bearbeitung von Events
- 🔐 Authentifizierung mit `flask_login`
- 🧠 KI-Unterstützung bei Event-Analyse (OCR, OpenAI)
- 📦 Deployment mit Fly.io
- 🌐 Bereit für echtes Domain-Mapping (`familysout.de`)

---

## 🚀 Lokale Entwicklung

1. **Projekt klonen**
   ```bash
   git clone https://github.com/JHH1195/familysout.git
   cd familysout
   ```

2. **Python-Umgebung einrichten**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Abhängigkeiten installieren**
   ```bash
   pip install -r python_app/requirements.txt
   ```

4. **App starten**
   ```bash
   cd python_app
   flask run
   ```

---

## 📁 Projektstruktur

```bash
familysout/
├── python_app/
│   ├── app.py               # Flask Entry-Point
│   ├── crawler_v2/          # Crawler-Module
│   ├── models.py            # DB-Modelle
│   ├── templates/           # HTML-Templates
│   ├── static/              # CSS, JS, Bilder
│   ├── requirements.txt     # Python Dependencies
│   └── ...
├── fly.toml                 # Fly.io Konfiguration
├── docker-compose.yml       # (Optional) Lokale Container-Orchestration
├── .gitignore
└── README.md
```

---

## ☁️ Deployment (Fly.io)

```bash
flyctl launch     # Nur beim ersten Setup
flyctl deploy     # Aktualisieren & Ausrollen
```

Zugriff dann unter:
```
https://familysout.fly.dev
```

---

## 🌍 Eigene Domain verbinden

1. Domain kaufen (z. B. via IONOS, Namecheap o. ä.)
2. In der Fly.io Console:
   ```bash
   flyctl certs create familysout.de
   ```
3. DNS-Einträge beim Hoster setzen:
   - `CNAME` → `familysout.fly.dev` oder
   - `A` und `AAAA` → IPs ausgeben lassen via:
     ```bash
     flyctl ips list
     ```

---

## 🔐 Beispiel `.env`

> **Hinweis:** `.env` ist in `.gitignore` und **nicht Teil des Repos**

```env
FLASK_APP=app.py
FLASK_ENV=development
OPENAI_API_KEY=sk-...
STRIPE_SECRET_KEY=...
```

---

## 🧠 Mitwirkende

- **Jan Borggreven** – Idee, Konzeption, Umsetzung  
- **[Dein Name hier]** – (komm an Bord!)

---

## 🗒️ Lizenz

MIT – Frei verwendbar mit Namensnennung. Für familiäre oder gemeinnützige Zwecke bevorzugt ❤️

---

## 💬 Feedback

Bei Fragen, Anregungen oder Interesse an Zusammenarbeit:
[flotti.de](https://flotti.de) oder GitHub Issues nutzen.