import os
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.database import get_db, init_db, Event, Task, Setting
from backend.agent import SchedulingAgent
from backend.scheduling import resolve_and_insert_event, auto_schedule_study_blocks

# Configure directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")

# Ensure frontend dir exists
os.makedirs(FRONTEND_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    init_db()
    yield

app = FastAPI(title="Smart Timetable Assistant API", lifespan=lifespan)

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas
class PromptRequest(BaseModel):
    prompt: str

class EventCreate(BaseModel):
    title: str
    category: str  # Class, Exam, Study Session, Break, Personal
    start_time: str  # ISO string
    end_time: str    # ISO string
    description: Optional[str] = ""
    is_recurring: Optional[bool] = False
    recurrence_rule: Optional[str] = None

class TaskCreate(BaseModel):
    title: str
    due_date: str  # ISO string
    priority: Optional[str] = "Medium"  # High, Medium, Low
    difficulty: Optional[int] = 3        # 1 to 5
    estimated_hours: Optional[float] = 2.0

class SettingUpdate(BaseModel):
    sleep_start: Optional[str] = None
    sleep_end: Optional[str] = None
    study_start: Optional[str] = None
    study_end: Optional[str] = None
    timezone: Optional[str] = None

# Endpoints
@app.post("/api/chat")
async def chat_with_agent(payload: PromptRequest, db: Session = Depends(get_db)):
    """Processes natural language input and schedules events/tasks accordingly."""
    if not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    
    agent = SchedulingAgent(db)
    result = agent.process_prompt(payload.prompt)
    return result

@app.get("/api/events")
async def list_events(db: Session = Depends(get_db)):
    """Lists all events sorted by start time."""
    events = db.query(Event).order_by(Event.start_time.asc()).all()
    return [e.to_dict() for e in events]

@app.post("/api/events")
async def create_event(event_data: EventCreate, db: Session = Depends(get_db)):
    """Creates a calendar event, performing conflict checking and priority resolution."""
    try:
        st = datetime.fromisoformat(event_data.start_time)
        et = datetime.fromisoformat(event_data.end_time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
        
    result = resolve_and_insert_event(
        db, 
        event_data.title, 
        event_data.category, 
        st, 
        et, 
        event_data.description, 
        event_data.is_recurring, 
        event_data.recurrence_rule
    )
    return result

@app.delete("/api/events/{event_id}")
async def delete_event(event_id: int, db: Session = Depends(get_db)):
    """Deletes an event by ID."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    db.delete(event)
    db.commit()
    return {"status": "success", "message": f"Event {event_id} deleted"}

@app.get("/api/tasks")
async def list_tasks(db: Session = Depends(get_db)):
    """Lists all tasks."""
    tasks = db.query(Task).order_by(Task.due_date.asc()).all()
    return [t.to_dict() for t in tasks]

@app.post("/api/tasks")
async def create_task(task_data: TaskCreate, db: Session = Depends(get_db)):
    """Creates a task and automatically schedules dedicated study sessions."""
    try:
        dt = datetime.fromisoformat(task_data.due_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
        
    new_task = Task(
        title=task_data.title,
        due_date=dt,
        priority=task_data.priority,
        difficulty=task_data.difficulty,
        estimated_hours=task_data.estimated_hours,
        status="Pending"
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    # Auto-schedule study blocks
    schedule_res = auto_schedule_study_blocks(db, new_task.id)
    
    return {
        "status": "success",
        "task": new_task.to_dict(),
        "study_scheduling": schedule_res
    }

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Deletes a task and all study sessions linked to it."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Also delete associated study sessions
    db.query(Event).filter(
        Event.category == "Study Session",
        Event.description.like(f"%Task ID: {task_id}%")
    ).delete(synchronize_session=False)
    
    db.delete(task)
    db.commit()
    return {"status": "success", "message": f"Task {task_id} and its study sessions deleted"}

@app.get("/api/settings")
async def get_settings(db: Session = Depends(get_db)):
    """Gets all settings as key-value pairs."""
    settings = db.query(Setting).all()
    return {s.key: s.value for s in settings}

@app.post("/api/settings")
async def update_settings(settings_data: SettingUpdate, db: Session = Depends(get_db)):
    """Updates user preferences (sleep/study bounds)."""
    updated = {}
    data_dict = settings_data.model_dump(exclude_unset=True)
    for key, value in data_dict.items():
        if value is not None:
            setting = db.query(Setting).filter(Setting.key == key).first()
            if setting:
                setting.value = value
            else:
                db.add(Setting(key=key, value=value))
            updated[key] = value
    db.commit()
    return {"status": "success", "updated": updated}

# Serve frontend files
# Note: we check if index.html exists, if not, we create it dynamically to serve.
@app.get("/")
async def get_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(index_path):
        return {"message": "Frontend index.html is missing. Setting up frontend files now."}
    return FileResponse(index_path)

# Mount remaining static assets (styles.css, app.js)
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
