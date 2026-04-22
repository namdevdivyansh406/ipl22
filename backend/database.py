"""
database.py — PostgreSQL connection + table definitions
WHY: We need persistent storage for messages and emotion scores
     so the frontend can query historical data and trends.
"""

import os
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Float, DateTime, Text, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/crowdpulse")

# SQLAlchemy engine — connects Python to PostgreSQL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─────────────────────────────────────────────
# TABLE 1: messages
# Stores every raw Telegram message we receive
# ─────────────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"

    id            = Column(Integer, primary_key=True, index=True)
    telegram_id   = Column(String, unique=True, index=True)   # Telegram message ID
    username      = Column(String, nullable=True)              # Sender's Telegram username
    text          = Column(Text, nullable=False)               # Raw message text
    timestamp     = Column(DateTime, default=datetime.utcnow)  # When received
    chat_id       = Column(String, nullable=True)              # Which group it came from

    # One message → many emotion scores
    emotions = relationship("Emotion", back_populates="message")


# ─────────────────────────────────────────────
# TABLE 2: emotions
# Stores AI-detected emotion scores per message
# ─────────────────────────────────────────────
class Emotion(Base):
    __tablename__ = "emotions"

    id           = Column(Integer, primary_key=True, index=True)
    message_id   = Column(Integer, ForeignKey("messages.id"))
    emotion_type = Column(String)   # "joy", "tension", "anger", "surprise", "disbelief"
    score        = Column(Float)    # 0.0 – 1.0 confidence score
    over_number  = Column(Integer, nullable=True)   # Cricket over (1–20)

    message = relationship("Message", back_populates="emotions")


# ─────────────────────────────────────────────
# TABLE 3: events
# Stores aggregated per-over emotion summaries
# and spike/viral moment detection
# ─────────────────────────────────────────────
class OverEvent(Base):
    __tablename__ = "events"

    id             = Column(Integer, primary_key=True, index=True)
    over_number    = Column(Integer, unique=True)
    peak_emotion   = Column(String)    # Dominant emotion for this over
    joy_avg        = Column(Float, default=0)
    tension_avg    = Column(Float, default=0)
    anger_avg      = Column(Float, default=0)
    surprise_avg   = Column(Float, default=0)
    disbelief_avg  = Column(Float, default=0)
    message_count  = Column(Integer, default=0)
    is_spike       = Column(Integer, default=0)   # 1 = viral moment
    created_at     = Column(DateTime, default=datetime.utcnow)


def create_tables():
    """Call this once on startup to create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency — gives each request its own DB session,
    then closes it when the request is done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()