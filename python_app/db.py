import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///events.db")

# 🛡️ Fallback: wenn Host "db" ist (Docker) und wir lokal arbeiten → SQLite
if DATABASE_URL.startswith("postgres") and "@db" in DATABASE_URL:
    print("[db.py] Host 'db' nicht verfügbar → Fallback auf SQLite")
    DATABASE_URL = "sqlite:///events.db"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Gemeinsame Basisklasse für alle Models
Base = declarative_base()

# Thread/Request-sichere Session-Factory
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False)
)
