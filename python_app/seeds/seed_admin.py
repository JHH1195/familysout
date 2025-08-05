# seed_admin.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from python_app.models import Base, User

# Datenbankverbindung
engine = create_engine("sqlite:///events.db")
Session = sessionmaker(bind=engine)
session = Session()

# Tabellenstruktur sicherstellen
Base.metadata.create_all(engine)

# Admin prüfen oder anlegen
ADMIN_EMAIL = "admin@flotti.de"
ADMIN_PASSWORT = "flottipass"

existing = session.query(User).filter_by(email=ADMIN_EMAIL).first()

if existing:
    print(f"⚠️ User existiert bereits: {existing.email}")
else:
    user = User(email=ADMIN_EMAIL)
    user.set_password(ADMIN_PASSWORT)
    session.add(user)
    session.commit()
    print(f"✅ Admin wurde angelegt: {ADMIN_EMAIL} / {ADMIN_PASSWORT}")
