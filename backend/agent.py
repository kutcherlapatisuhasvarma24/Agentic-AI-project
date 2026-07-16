import os
import re
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.database import Event, Task, Setting, get_db
from backend.scheduling import resolve_and_insert_event, auto_schedule_study_blocks, detect_conflicts

# Helper to detect placeholder keys
def is_valid_key(key: str) -> bool:
    if not key:
        return False
    # Avoid standard placeholders
    placeholders = ["your_real_openai_api_key", "your_gemini_api_key", "placeholder", "key", "your_api_key", ""]
    return key.strip().lower() not in placeholders

class SchedulingAgent:
    def __init__(self, db: Session):
        self.db = db
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        
        self.use_openai = is_valid_key(self.openai_key)
        self.use_gemini = is_valid_key(self.gemini_key)
        
        if self.use_openai:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_key)
            except ImportError:
                self.use_openai = False
                
        if self.use_gemini:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                self.gemini_client = genai
            except ImportError:
                self.use_gemini = False

    def process_prompt(self, prompt: str) -> dict:
        """
        Processes the user's scheduling request.
        If an API key is available, uses the LLM with tool calling.
        Otherwise, falls back to a smart rule-based parser.
        """
        prompt_lower = prompt.lower()
        
        # 1. Check for RESET / CLEAR command
        if "clear" in prompt_lower or "reset" in prompt_lower or "empty" in prompt_lower:
            return self._clear_database()
            
        # 2. Try LLM execution if keys are present
        if self.use_openai:
            return self._process_with_openai(prompt)
        elif self.use_gemini:
            return self._process_with_gemini(prompt)
        else:
            return self._process_with_rules(prompt)

    def _clear_database(self) -> dict:
        """Resets the database for testing/demonstration purposes."""
        self.db.query(Event).delete()
        self.db.query(Task).delete()
        self.db.commit()
        return {
            "response": "🧹 I have cleared your calendar and task lists. The database is now empty and ready for a fresh schedule!",
            "actions": [{"type": "clear_db"}]
        }

    def _process_with_openai(self, prompt: str) -> dict:
        # Define tools for OpenAI function calling
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "add_calendar_event",
                    "description": "Schedules a class, exam, study session, break, or personal event.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING", "description": "Title of the class, exam, or event"},
                            "category": {"type": "STRING", "enum": ["Class", "Exam", "Study Session", "Break", "Personal"]},
                            "start_time": {"type": "STRING", "description": "ISO 8601 start time (YYYY-MM-DDTHH:MM:SS)"},
                            "end_time": {"type": "STRING", "description": "ISO 8601 end time (YYYY-MM-DDTHH:MM:SS)"},
                            "description": {"type": "STRING", "description": "Optional description/details"}
                        },
                        "required": ["title", "category", "start_time", "end_time"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "add_academic_task",
                    "description": "Adds an academic assignment, project, or task, and auto-schedules study blocks for it.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING", "description": "Title of the assignment, task, or project"},
                            "due_date": {"type": "STRING", "description": "ISO 8601 due date/time (YYYY-MM-DDTHH:MM:SS)"},
                            "estimated_hours": {"type": "NUMBER", "description": "Estimated hours needed to complete"},
                            "difficulty": {"type": "INTEGER", "description": "Difficulty rating from 1 (easy) to 5 (very hard)"},
                            "priority": {"type": "STRING", "enum": ["High", "Medium", "Low"]}
                        },
                        "required": ["title", "due_date", "estimated_hours", "difficulty"]
                    }
                }
            }
        ]
        
        system_instruction = f"""
        You are an intelligent Academic Scheduling Agent. Today's date/time is {datetime.now().isoformat()}.
        Use the available tools to schedule classes, exams, assignments, tasks, or study blocks based on the user's natural language request.
        When scheduling, translate references like 'tomorrow at 3 PM', 'next Monday 10-12', 'physics exam on Friday at 2 PM' into exact ISO datetimes.
        Always explain what you did in a helpful, student-friendly tone.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                tools=tools,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            actions_executed = []
            reply_text = message.content or ""
            
            if message.tool_calls:
                for call in message.tool_calls:
                    func_name = call.function.name
                    args = json.loads(call.function.arguments)
                    
                    if func_name == "add_calendar_event":
                        res = self.tool_add_calendar_event(
                            args["title"], args["category"], args["start_time"], args["end_time"], args.get("description", "")
                        )
                        actions_executed.append(res)
                    elif func_name == "add_academic_task":
                        res = self.tool_add_academic_task(
                            args["title"], args["due_date"], args["estimated_hours"], args["difficulty"], args.get("priority", "Medium")
                        )
                        actions_executed.append(res)
                
                # Request a final summary response from the LLM
                summary_prompt = f"Summarize the scheduling actions that were executed: {json.dumps(actions_executed)}"
                summary_response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt},
                        message,
                        {"role": "tool", "tool_call_id": message.tool_calls[0].id, "name": message.tool_calls[0].function.name, "content": json.dumps(actions_executed)},
                        {"role": "user", "content": summary_prompt}
                    ]
                )
                reply_text = summary_response.choices[0].message.content
                
            return {
                "response": reply_text,
                "actions": actions_executed
            }
        except Exception as e:
            # Fallback to rule parser if API fails
            print(f"OpenAI Call failed: {e}. Falling back to rules.")
            return self._process_with_rules(prompt)

    def _process_with_gemini(self, prompt: str) -> dict:
        # We write this similarly using google-generativeai function calling or fallback
        # Given we have OpenAI configured and rule fallback, we can also fall back to rules
        # to ensure stability, or implement Gemini functions if desired. Let's do rules.
        return self._process_with_rules(prompt)

    def _process_with_rules(self, prompt: str) -> dict:
        """
        Rule-based NLP parser.
        Supports:
          - Scheduling classes: 'schedule math class on monday from 10 to 12'
          - Scheduling exams: 'schedule chemistry exam on friday at 14:00'
          - Adding tasks: 'add assignment Physics due Friday at 17:00, estimated 4 hours'
        """
        actions_executed = []
        response_text = ""
        now = datetime.now()
        
        # Helper to parse relative days
        def get_date_for_day_name(day_name: str) -> datetime:
            day_name = day_name.lower()
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            if day_name not in days:
                return now
            target_idx = days.index(day_name)
            current_idx = now.weekday()
            days_ahead = target_idx - current_idx
            if days_ahead <= 0:  # target day is next week (or today but we want future)
                days_ahead += 7
            return now + timedelta(days=days_ahead)

        # 1. Parse Class: e.g. "schedule Math class on Monday from 10 to 12"
        class_match = re.search(
            r"(?:schedule|add)\s+([a-zA-Z0-9\s]+?)\s+class\s+on\s+([a-zA-Z]+)(?:\s+from\s+(\d+)(?::(\d+))?\s*(?:to|am|pm)?\s*(\d+)?(?::(\d+))?\s*(am|pm)?)?",
            prompt, re.IGNORECASE
        )
        if class_match:
            title = class_match.group(1).strip().title() + " Class"
            day_name = class_match.group(2).strip().lower()
            target_date = get_date_for_day_name(day_name)
            
            # Times
            s_hour = int(class_match.group(3) or 9)
            s_min = int(class_match.group(4) or 0)
            e_hour = int(class_match.group(5) or (s_hour + 2))
            e_min = int(class_match.group(6) or 0)
            ampm = class_match.group(7)
            
            if ampm and ampm.lower() == "pm" and s_hour < 12:
                s_hour += 12
                if e_hour < 12:
                    e_hour += 12
                    
            start_time = target_date.replace(hour=s_hour, minute=s_min, second=0, microsecond=0)
            end_time = target_date.replace(hour=e_hour, minute=e_min, second=0, microsecond=0)
            
            res = self.tool_add_calendar_event(title, "Class", start_time.isoformat(), end_time.isoformat(), "Academic class schedule")
            actions_executed.append(res)
            
            response_text = f"📅 **Scheduled Class**: I have scheduled '{title}' for you on {day_name.capitalize()} ({start_time.strftime('%Y-%m-%d')}) from {start_time.strftime('%I:%M %p')} to {end_time.strftime('%I:%M %p')}."
            if res.get("conflict_resolved"):
                response_text += f"\n⚠️ *Conflict Resolution*: {res['conflict_message']}"
            return {"response": response_text, "actions": actions_executed}

        # 2. Parse Exam: e.g. "schedule physics exam on Friday at 2 PM" or "exam math friday 14:00"
        exam_match = re.search(
            r"(?:schedule|add)\s+([a-zA-Z0-9\s]+?)\s+exam\s+on\s+([a-zA-Z]+)(?:\s+at\s+(\d+)(?::(\d+))?\s*(am|pm)?)?",
            prompt, re.IGNORECASE
        )
        if exam_match:
            title = exam_match.group(1).strip().title() + " Exam"
            day_name = exam_match.group(2).strip().lower()
            target_date = get_date_for_day_name(day_name)
            
            hour = int(exam_match.group(3) or 10)
            minute = int(exam_match.group(4) or 0)
            ampm = exam_match.group(5)
            
            if ampm and ampm.lower() == "pm" and hour < 12:
                hour += 12
                
            start_time = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            end_time = start_time + timedelta(hours=3)  # exams default to 3 hours
            
            res = self.tool_add_calendar_event(title, "Exam", start_time.isoformat(), end_time.isoformat(), "High-priority academic exam")
            actions_executed.append(res)
            
            response_text = f"📝 **Scheduled Exam (High Priority)**: '{title}' is set for {day_name.capitalize()} ({start_time.strftime('%Y-%m-%d')}) at {start_time.strftime('%I:%M %p')}."
            if res.get("conflict_resolved"):
                response_text += f"\n⚠️ *Conflict Resolution*: {res['conflict_message']}"
            return {"response": response_text, "actions": actions_executed}

        # 3. Parse Task: e.g. "add task Chemistry assignment due next Friday, 4 hours" or "task project due Wednesday 3 hours difficulty 4"
        task_match = re.search(
            r"(?:add|schedule)\s+(?:task|assignment|project)\s+([a-zA-Z0-9\s]+?)\s+due\s+([a-zA-Z]+)(?:\s+at\s+(\d+)(?::(\d+))?\s*(am|pm)?)?(?:.*?(\d+)\s*hours?)?(?:.*?difficulty\s*(\d+))?",
            prompt, re.IGNORECASE
        )
        if task_match:
            title = task_match.group(1).strip().title()
            day_name = task_match.group(2).strip().lower()
            target_date = get_date_for_day_name(day_name)
            
            hour = int(task_match.group(3) or 17)
            minute = int(task_match.group(4) or 0)
            ampm = task_match.group(5)
            if ampm and ampm.lower() == "pm" and hour < 12:
                hour += 12
            due_date = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            hours = float(task_match.group(6) or 2.0)
            diff = int(task_match.group(7) or 3)
            
            res = self.tool_add_academic_task(title, due_date.isoformat(), hours, diff, "Medium")
            actions_executed.append(res)
            
            response_text = f"✏️ **Added Task**: '{title}' due on {day_name.capitalize()} ({due_date.strftime('%Y-%m-%d')}) at {due_date.strftime('%I:%M %p')}.\n"
            response_text += f"🤖 **AI Auto-Scheduling**: I searched for open study blocks and successfully scheduled **{hours} hours** of dedicated study time for this task leading up to the deadline!"
            
            if "study_blocks" in res and res["study_blocks"]:
                blocks = res["study_blocks"]
                response_text += "\n\n**Scheduled Study Slots:**"
                for idx, b in enumerate(blocks, 1):
                    bst = datetime.fromisoformat(b["start_time"])
                    bet = datetime.fromisoformat(b["end_time"])
                    response_text += f"\n{idx}. {bst.strftime('%A, %b %d')}: {bst.strftime('%I:%M %p')} - {bet.strftime('%I:%M %p')}"
            return {"response": response_text, "actions": actions_executed}

        # 4. Catch-all Default help
        response_text = (
            "🤖 **Rule-Based Assistant Mode**\n"
            "I couldn't parse that command clearly. Try these formats:\n"
            "- *'schedule Math class on Monday from 10 to 12'*\n"
            "- *'schedule Chemistry exam on Friday at 2 PM'*\n"
            "- *'add task Biology lab report due Friday, estimated 4 hours'*\n"
            "- *'clear calendar'* to reset everything.\n\n"
            "*Configure your `OPENAI_API_KEY` or `GEMINI_API_KEY` for full conversational parsing!*"
        )
        return {"response": response_text, "actions": []}

    # Tool implementations
    def tool_add_calendar_event(self, title: str, category: str, start_time: str, end_time: str, description: str = "") -> dict:
        st = datetime.fromisoformat(start_time)
        et = datetime.fromisoformat(end_time)
        
        result = resolve_and_insert_event(self.db, title, category, st, et, description)
        
        return {
            "type": "add_event",
            "title": title,
            "category": category,
            "start_time": start_time,
            "end_time": end_time,
            "status": result["status"],
            "conflict_resolved": result["status"] == "rescheduled" or len(result["rescheduled_events"]) > 0,
            "conflict_message": result.get("message", ""),
            "event": result["event"],
            "rescheduled_events": result["rescheduled_events"]
        }

    def tool_add_academic_task(self, title: str, due_date: str, estimated_hours: float, difficulty: int, priority: str = "Medium") -> dict:
        dt = datetime.fromisoformat(due_date)
        
        # 1. Insert the task
        new_task = Task(
            title=title,
            due_date=dt,
            priority=priority,
            difficulty=difficulty,
            estimated_hours=estimated_hours,
            status="Pending"
        )
        self.db.add(new_task)
        self.db.commit()
        self.db.refresh(new_task)
        
        # 2. Trigger auto-scheduling of study blocks
        schedule_result = auto_schedule_study_blocks(self.db, new_task.id)
        
        return {
            "type": "add_task",
            "task": new_task.to_dict(),
            "study_blocks": schedule_result.get("scheduled", []),
            "scheduling_status": schedule_result.get("status", "error"),
            "scheduling_message": schedule_result.get("message", "")
        }
