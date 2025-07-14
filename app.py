from dotenv import load_dotenv
load_dotenv()
import os
from flask import Flask, render_template, request
from models import Event, Session

app = Flask(__name__)

# Datenbankverbindung prüfen
db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise ValueError("❌ DATABASE_URL nicht gefunden – bitte in Railway setzen")

# Startseite
@app.route("/", methods=["GET"])
def startseite():
    return render_template("index.html")

# Ergebnisseite
@app.route("/results", methods=["GET"])
def suchergebnisse():
    query = request.args.get("q", "").lower()
    location_filter = request.args.get("location", "").lower()
    category_filter = request.args.get("category", "").lower()
    date_filter = request.args.get("date", "").strip()

    session = Session()
    events_query = session.query(Event)

    if query:
        events_query = events_query.filter(
            Event.title.ilike(f"%{query}%") | Event.date.ilike(f"%{query}%")
        )

    if location_filter:
        events_query = events_query.filter(
            Event.location.ilike(f"%{location_filter}%")
        )

    if category_filter:
        events_query = events_query.filter(
            Event.category.ilike(f"%{category_filter}%")
        )

    if date_filter:
        events_query = events_query.filter(
            Event.date.ilike(f"%{date_filter}%")
        )

    events = events_query.all()
    print(f"🔎 Filter aktiv – {len(events)} Events angezeigt")
    return render_template("results.html", events=events, query=query,
                           location_filter=location_filter,
                           category_filter=category_filter,
                           date_filter=date_filter)

# Eventseite
@app.route("/event/<int:event_id>")
def event_detail(event_id):
    session = Session()
    event = session.query(Event).get(event_id)

    # Filter-Query für linke Seitenleiste
    query = request.args.get("q", "").lower()
    location_filter = request.args.get("location", "").lower()
    category_filter = request.args.get("category", "").lower()

    events_query = session.query(Event)

    if query:
        events_query = events_query.filter(
            Event.title.ilike(f"%{query}%") | Event.date.ilike(f"%{query}%")
        )

    if location_filter:
        events_query = events_query.filter(
            Event.location.ilike(f"%{location_filter}%")
        )

    if category_filter:
        events_query = events_query.filter(
            Event.category.ilike(f"%{category_filter}%")
        )

    event_list = events_query.all()

    return render_template("event.html", event=event, events=event_list)

# App starten
if __name__ == "__main__":
    print("🚀 Starte Flask-App...")
    app.run(debug=True, port=5000)
