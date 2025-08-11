from python_app.models import Base, engine

Base.metadata.create_all(engine)
print("✅ Neue PostgreSQL-Datenbank initialisiert.")
