import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import init_db
from backend.agent import SchedulingAgent
from backend.database import get_db, Event, Task

st.set_page_config(page_title="Smart Timetable Assistant", page_icon="🗓️", layout="wide")

init_db()

st.title("🗓️ Smart Timetable Assistant")
st.write("Manage your schedule with a simple chat-style interface.")

if "db" not in st.session_state:
    st.session_state.db = next(get_db())

with st.sidebar:
    st.header("Quick actions")
    if st.button("Clear calendar"):
        db = st.session_state.db
        db.query(Event).delete()
        db.query(Task).delete()
        db.commit()
        st.success("Calendar cleared")

    st.write("Enter a prompt such as:")
    st.code("Schedule Math class on Monday from 10 to 12")
    st.code("Add Physics assignment due Friday at 5 PM, estimated 4 hours")

prompt = st.text_area("What would you like to schedule?")

if st.button("Run") and prompt:
    agent = SchedulingAgent(st.session_state.db)
    result = agent.process_prompt(prompt)
    st.success(result.get("response", "Done"))

    if result.get("actions"):
        st.subheader("Actions")
        st.json(result["actions"])

st.subheader("Current schedule")

query = st.session_state.db.query(Event).order_by(Event.start_time.asc()).all()
if query:
    for event in query:
        st.write(f"- {event.title} ({event.category}) {event.start_time} → {event.end_time}")
else:
    st.info("No events yet.")

def render_app():
    return None
