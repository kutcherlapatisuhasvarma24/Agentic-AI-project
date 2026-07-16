import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# Database folder configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)  # Class, Exam, Study Session, Break, Personal
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    description = Column(Text, nullable=True)
    is_recurring = Column(Boolean, default=False)
    recurrence_rule = Column(String(200), nullable=True)  # Simple rule like "DAILY" or "WEEKLY:MON"

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "description": self.description,
            "is_recurring": self.is_recurring,
            "recurrence_rule": self.recurrence_rule,
        }

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    due_date = Column(DateTime, nullable=False)
    priority = Column(String(20), nullable=False, default="Medium")  # High, Medium, Low
    difficulty = Column(Integer, nullable=False, default=3)  # 1 to 5
    estimated_hours = Column(Float, nullable=False, default=2.0)
    status = Column(String(20), nullable=False, default="Pending")  # Pending, Completed

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.due_date.isoformat() if isinstance(self.due_date, datetime) else self.due_date,
            "due_date": self.due_date.isoformat(),
            "priority": self.priority,
            "difficulty": self.difficulty,
            "estimated_hours": self.estimated_hours,
            "status": self.status,
        }

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(50), primary_key=True, index=True)
    value = Column(String(200), nullable=False)

# Helper function to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize database
def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Pre-populate default settings if they don't exist
    db = SessionLocal()
    try:
        default_settings = {
            "sleep_start": "22:00",
            "sleep_end": "06:00",
            "study_start": "08:00",
            "study_end": "20:00",
            "timezone": "UTC",
        }
        for key, value in default_settings.items():
            setting = db.query(Setting).filter(Setting.key == key).first()
            if not setting:
                db.add(Setting(key=key, value=value))
        db.commit()
    finally:
        db.close()
