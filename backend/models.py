from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base
import datetime

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    telegram_msg_id = Column(Integer, unique=True, index=True)
    username = Column(String, index=True)
    text = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class EmotionScore(Base):
    __tablename__ = "emotions"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, index=True) # links to Message.id
    tension = Column(Float, default=0.0)
    joy = Column(Float, default=0.0)
    anger = Column(Float, default=0.0)
    surprise = Column(Float, default=0.0)
    disbelief = Column(Float, default=0.0)
    over_number = Column(Integer, default=1) # Simulated over for grouping
