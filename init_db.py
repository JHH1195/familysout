# init_db.py
from models import Base, engine

Base.metadata.create_all(engine)
print("✅ Neue Datenbank mit Spalte 'category' erstellt.")
