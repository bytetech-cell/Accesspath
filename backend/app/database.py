"""Database setup. Works with SQLite (default) and PostgreSQL."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def now_utc():
    return datetime.now(timezone.utc)


class Audit(Base):
    __tablename__ = "audits"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id = Column(String(36), nullable=True, index=True)  # set when this is a re-run
    url = Column(Text, nullable=False)
    task = Column(Text, nullable=False)
    journey_steps = Column(JSON, default=list)      # labels the user (or TinyFish) gave
    conditions = Column(JSON, default=dict)         # {"keyboard": true, "screen_reader": true, "mobile": true}
    use_tinyfish = Column(Integer, default=1)

    status = Column(String(20), default="queued")   # queued | running | done | error
    current_step = Column(Integer, default=1)       # 1..9 from the workflow
    progress = Column(JSON, default=list)           # the 9 workflow steps with status + detail
    task_status = Column(String(20), default="unknown")  # passed | failed | unknown
    score = Column(Float, nullable=True)
    issue_count = Column(Integer, default=0)
    result = Column(JSON, default=dict)             # full report
    error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=now_utc)
    finished_at = Column(DateTime(timezone=True), nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)
