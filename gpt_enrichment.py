import openai
import os
from models import Session, Event
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def enrich_event(event: Event) -> Event:
    prompt = f"""
    Du bist ein Assistent für ein Familienportal. Bitte bewerte und ergänze folgende Event-Daten:
    
    Titel: {event.title}
    Beschreibung: {event.description or 'Keine Beschreibung'}
    Ort: {event.location or 'Unbekannt'}

    Antworte im JSON-Format mit:
    {{
      "beschreibung": "...",
      "kategorie": "...",
      "maps_url": "..."
    }}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Du bist ein hilfreicher Assistent für ein Familienevent-Portal."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        content = response.choices[0].message.content
        import json
        result = json.loads(content)

        # Event anreichern
        event.description = result.get("beschreibung", event.description)
        event.category = result.get("kategorie", "Unbekannt")
        event.maps_url = result.get("maps_url", event.maps_url)

        return event

    except Exception as e:
        print(f"❌ GPT-Anreicherung fehlgeschlagen: {e}")
        return event

def enrich_all_events():
    session = Session()
    events = session.query(Event).filter(Event.description == None).all()

    print(f"🔍 {len(events)} Events ohne Beschreibung gefunden")

    for event in events:
        enriched = enrich_event(event)
        session.add(enriched)

    session.commit()
    print("✅ Alle Events wurden angereichert")
