from sqlalchemy import Column, DateTime, Float, Integer
from database import Base

class SessionRecord(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=False)
    duration_seconds = Column(Float, default=0)
    bites = Column(Integer, default=0)
    chews = Column(Integer, default=0)
