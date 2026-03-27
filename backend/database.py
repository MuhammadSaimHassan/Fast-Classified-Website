# ...existing code...
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
import sys
from sqlalchemy.exc import OperationalError

# load backend/.env explicitly
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Please set backend/.env with a valid URL, e.g.:\n"
        "DATABASE_URL=postgresql://postgres:1234@localhost:5432/fast_classified"
    )

# Add pool_pre_ping to recover from dropped connections
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

# quick connectivity check to give a clear error when DB is unreachable
try:
    conn = engine.connect()
    conn.close()
except OperationalError as e:
    raise RuntimeError(
        f"Unable to connect to the database at {SQLALCHEMY_DATABASE_URL!r}. "
        "Make sure Postgres is running and accessible. Original error: " + str(e)
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# ...existing code...
