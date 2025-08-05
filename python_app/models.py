from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from flask_login import UserMixin

Base = declarative_base()

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
    lat = Column(Float)  # 🆕 Latitude
    lon = Column(Float)  # 🆕 Longitude
    price = Column(Float)            # Preis falls bekannt
    is_free = Column(Boolean)        # kostenlos
    is_outdoor = Column(Boolean)     # draußen
    age_group = Column(String) 

class Quelle(Base):
    __tablename__ = "quellen"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    url = Column(String, unique=True)
    typ = Column(String)       # z. B. "playwright", "rss", "html"
    stadt = Column(String)     # z. B. "Aachen"
    aktiv = Column(Boolean)    # True = aktiv nutzen
    status = Column(String, default="pending")  # "pending", "success", "error"
    created_at = Column(DateTime, default=datetime.utcnow)



class User(Base, UserMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    firstname = Column(String, nullable=False)
    lastname = Column(String, nullable=False)
    city = Column(String, nullable=True)
    image_url = Column(String, nullable=True)  # ✅ Profilbild
    is_premium = Column(Boolean, default=False)  # ✅ Flotti+

    # Stripe & Abo
    stripe_customer_id = Column(String)
    stripe_subscription_id = Column(String)
    is_premium = Column(Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"

   
# DB-Verbindung (lokal, SQLite-Datei)
engine = create_engine("sqlite:///events.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
