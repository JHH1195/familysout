import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///events.db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Thread/Request-sichere Session-Factory
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False)
)
