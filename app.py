from flask import Flask, render_template
import json

app = Flask(__name__)

@app.route("/")
def index():
    try:
        with open("events_kingkalli.json", encoding="utf-8") as f:
            events = json.load(f)
    except Exception as e:
        print("❌ Fehler beim Laden der JSON-Datei:", e)
        events = []

    print(f"🔢 {len(events)} Events geladen")  # ← Ausgabe ins Terminal
    return render_template("index.html", events=events)

from livereload import Server

if __name__ == "__main__":
    print("🚀 Starte Flask-App mit Live Reload...")
    server = Server(app.wsgi_app)
    server.serve(debug=True, port=5000)

