# 🤖 Smart Timetable Assistant AI Agent

A state-of-the-art, full-stack Academic Calendar Management Agent designed for students to organize academic schedules, track assignment deadlines, and automate study slot allocations with priority-based conflict resolution.

This project is built using a **FastAPI** backend serving a highly polished **React & Tailwind CSS** glassmorphism dashboard, featuring real-time AI natural language processing.

---

## ✨ Features

- **🗣️ Natural Language Chat Agent**: Input natural prompts (e.g. *"Schedule Math class on Mondays from 10 to 12"* or *"Add Physics assignment due Friday at 5 PM, estimated 4 hours"*) to automatically configure schedules.
- **🔄 AI Auto-Scheduling**: Adding an academic task automatically searches for open spots in your preferred study window and schedules dedicated study sessions leading up to the deadline.
- **⚖️ Priority-Based Conflict Resolution**: If an event (e.g. Class, Exam, Personal) overlaps:
  - Higher-priority events (e.g. Exams, Classes) automatically bump lower-priority events (e.g. Personal, Study Sessions).
  - The bumped events are rescheduled to the next available study window.
  - Users are notified of conflicts and their resolution in the chat history.
- **🎨 Glassmorphic Dashboard**: A gorgeous dark-mode web application featuring:
  - Weekly view visual calendar.
  - Active tasks panel showing difficulty, priority, and study hour estimates.
  - Customizable profile settings (study window limits, sleep bounds, and timezone).
  - Live AI chat assistant interface with quick-action suggestion chips.
  - Complete database reset controls for staging and testing.

---

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy (SQLite DB), Pydantic
- **AI Brain**: OpenAI API (with robust rule-based parsing fallback if no key is configured)
- **Frontend**: HTML5, CSS3, React, Tailwind CSS (Glassmorphism layout), Lucide Icons

---

## 🚀 Setup & Execution

### 1. Prerequisites
Make sure Python 3.8+ is installed on your system.

### 2. Install Dependencies
Run the following command in your terminal from this project directory:
```bash
pip install fastapi uvicorn sqlalchemy pydantic openai
```
*(Note: These dependencies are already pre-installed in your environment).*

### 3. Run the Server
Start the FastAPI server:
```bash
uvicorn backend.main:app --reload
```

### 4. Access the Application
Open your web browser and navigate to:
```
http://127.0.0.1:8000
```

---

## 🤖 How to Test the AI Agent

You can test the scheduling agent by typing commands into the chat box or clicking the quick action buttons:

1. **Reset Database**: Type `clear calendar` or click **Reset calendar** to empty the schedule.
2. **Schedule a Class**: Type `schedule Math class on Monday from 10 to 12`. You will see it appear in the calendar!
3. **Schedule an Exam**: Type `schedule chemistry exam on Friday at 2 PM`. This schedules a high-priority 3-hour exam.
4. **Auto-Schedule Tasks & Study Blocks**: Type `Add Physics task due next Friday at 5 PM, estimated 4 hours`. The AI will create the task and find 4 hours of free study blocks on the days leading up to it, adjusting for sleep/class slots.
5. **Conflict Trigger**: Schedule a personal appointment that overlaps with your math class. The AI will detect the conflict, maintain the math class, and schedule the personal event at the next free slot!
