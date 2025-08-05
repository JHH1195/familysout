# init_db.py
from python_app.models import Base, engine

Base.metadata.create_all(engine)
print("✅ Neue Datenbank mit Spalte 'category' erstellt.")
