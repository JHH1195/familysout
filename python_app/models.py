import os
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Float,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import UserMixin
from dotenv import load_dotenv

# 🔁 .env laden
load_dotenv()

# 🧱 Base definieren
Base = declarative_base()

# 📦 Datenbank-Verbindung
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///events.db")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


# 🗂 Event-Modell
class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String)
    date = Column(String)
    image_url = Column(String)
    location = Column(String)
    maps_url = Column(String)
    category = Column(String, default="Unbekannt")
    source_url = Column(String)
    source_name = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    price = Column(Float)
    is_free = Column(Boolean)
    is_outdoor = Column(Boolean)
    age_group = Column(String)


# 📚 Quellen-Modell
class Quelle(Base):
    __tablename__ = "quellen"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    url = Column(String, unique=True)
    typ = Column(String)
    stadt = Column(String)
    aktiv = Column(Boolean)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


# 👤 Benutzer-Modell
class User(Base, UserMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    firstname = Column(String, nullable=False)
    lastname = Column(String, nullable=False)
    city = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    is_premium = Column(Boolean, default=False)
    stripe_customer_id = Column(String)
    stripe_subscription_id = Column(String)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"
