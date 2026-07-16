from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.database import Event, Task, Setting

def get_setting(db: Session, key: str, default: str) -> str:
    setting = db.query(Setting).filter(Setting.key == key).first()
    return setting.value if setting else default

def detect_conflicts(db: Session, start_time: datetime, end_time: datetime, exclude_event_id: int = None):
    """
    Returns any events that overlap with [start_time, end_time].
    Two intervals [s1, e1] and [s2, e2] overlap if max(s1, s2) < min(e1, e2).
    """
    query = db.query(Event).filter(
        Event.start_time < end_time,
        Event.end_time > start_time
    )
    if exclude_event_id:
        query = query.filter(Event.id != exclude_event_id)
    return query.all()

def find_next_free_slot(db: Session, duration_hours: float, start_search: datetime, before_limit: datetime = None) -> datetime:
    """
    Finds the next available free slot of duration_hours within preferred study hours,
    not overlapping with any existing events.
    """
    study_start_str = get_setting(db, "study_start", "08:00")
    study_end_str = get_setting(db, "study_end", "20:00")
    
    sh_hour, sh_min = map(int, study_start_str.split(":"))
    eh_hour, eh_min = map(int, study_end_str.split(":"))
    
    current_time = start_search
    # Make sure we don't start in the past relative to now
    now = datetime.now()
    if current_time < now:
        current_time = now
        
    duration = timedelta(hours=duration_hours)
    
    # Search day by day for up to 30 days
    for _ in range(30):
        if before_limit and current_time >= before_limit:
            break
            
        # Preferred study hours for current_time's day
        day_start = current_time.replace(hour=sh_hour, minute=sh_min, second=0, microsecond=0)
        day_end = current_time.replace(hour=eh_hour, minute=eh_min, second=0, microsecond=0)
        
        # Adjust start time if we are already in the middle of the day
        search_start = max(current_time, day_start)
        
        # Loop through the day in 30-minute intervals
        temp_time = search_start
        while temp_time + duration <= day_end:
            if before_limit and temp_time + duration > before_limit:
                break
                
            conflicts = detect_conflicts(db, temp_time, temp_time + duration)
            if not conflicts:
                return temp_time
                
            # Skip past the latest conflicting event's end time
            latest_end = max(c.end_time for c in conflicts)
            temp_time = latest_end
            # Align to next 15-minute mark
            minutes_to_add = 15 - (temp_time.minute % 15)
            temp_time += timedelta(minutes=minutes_to_add)
            temp_time = temp_time.replace(second=0, microsecond=0)
            
        # Move to the start of study hours on the next day
        current_time = (current_time + timedelta(days=1)).replace(hour=sh_hour, minute=sh_min, second=0, microsecond=0)
        
    return None

def auto_schedule_study_blocks(db: Session, task_id: int):
    """
    Automatically allocates study blocks for a task leading up to its due date.
    Splits the estimated hours into manageable sessions (max 2 hours each).
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return {"status": "error", "message": "Task not found"}
        
    total_hours = task.estimated_hours
    due_date = task.due_date
    
    # Delete any existing study sessions associated with this task to avoid duplicates
    db.query(Event).filter(
        Event.category == "Study Session",
        Event.description.like(f"%Task ID: {task_id}%")
    ).delete(synchronize_session=False)
    db.commit()
    
    # We split total hours into blocks of max 2 hours
    block_size = 2.0
    remaining_hours = total_hours
    scheduled_blocks = []
    
    start_search = datetime.now() + timedelta(hours=1)  # start searching from 1 hour from now
    
    while remaining_hours > 0:
        current_block_size = min(remaining_hours, block_size)
        slot_start = find_next_free_slot(db, current_block_size, start_search, before_limit=due_date)
        
        if not slot_start:
            # If we can't find a free slot before the due date, we might have to relax constraints
            # Let's try searching without preferred study hour constraints, or just warn the user
            break
            
        slot_end = slot_start + timedelta(hours=current_block_size)
        
        # Create the event
        new_event = Event(
            title=f"Study: {task.title}",
            category="Study Session",
            start_time=slot_start,
            end_time=slot_end,
            description=f"Auto-scheduled study session for task. Task ID: {task_id}. Priority: {task.priority}.",
            is_recurring=False
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        scheduled_blocks.append(new_event)
        
        # Update search start for next block to be after this block ends
        start_search = slot_end + timedelta(minutes=30)  # add 30 mins buffer between study sessions
        remaining_hours -= current_block_size
        
    if remaining_hours > 0:
        return {
            "status": "partial",
            "message": f"Scheduled {total_hours - remaining_hours} of {total_hours} hours. Could not find enough free slots before the due date for the remaining {remaining_hours} hours.",
            "scheduled": [b.to_dict() for b in scheduled_blocks]
        }
        
    return {
        "status": "success",
        "message": f"Successfully scheduled {len(scheduled_blocks)} study sessions totaling {total_hours} hours.",
        "scheduled": [b.to_dict() for b in scheduled_blocks]
    }

CATEGORY_PRIORITIES = {
    "Exam": 5,
    "Class": 4,
    "Study Session": 3,
    "Break": 2,
    "Personal": 1
}

def resolve_and_insert_event(db: Session, title: str, category: str, start_time: datetime, end_time: datetime, description: str = "", is_recurring: bool = False, recurrence_rule: str = None):
    """
    Inserts a new event, detecting conflicts.
    If conflicts exist:
      - Compare priorities.
      - If new event has higher priority, reschedule the conflicting events.
      - If new event has lower or equal priority, reschedule the new event.
    Returns a log of changes made.
    """
    conflicts = detect_conflicts(db, start_time, end_time)
    
    if not conflicts:
        # No conflict, insert directly
        new_event = Event(
            title=title,
            category=category,
            start_time=start_time,
            end_time=end_time,
            description=description,
            is_recurring=is_recurring,
            recurrence_rule=recurrence_rule
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        return {
            "status": "success",
            "event": new_event.to_dict(),
            "rescheduled_events": []
        }
        
    new_priority = CATEGORY_PRIORITIES.get(category, 1)
    rescheduled_log = []
    
    # Check if new event wins all conflicts
    new_event_wins = all(new_priority > CATEGORY_PRIORITIES.get(c.category, 1) for c in conflicts)
    
    if new_event_wins:
        # Schedule the new event at the requested time
        new_event = Event(
            title=title,
            category=category,
            start_time=start_time,
            end_time=end_time,
            description=description,
            is_recurring=is_recurring,
            recurrence_rule=recurrence_rule
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        
        # Now reschedule each conflicting event
        for conf in conflicts:
            conf_duration = (conf.end_time - conf.start_time).total_seconds() / 3600.0
            # Find next free slot for conflicting event, searching from new_event's end time
            search_start = end_time + timedelta(minutes=15)
            next_slot = find_next_free_slot(db, conf_duration, search_start)
            
            old_start = conf.start_time
            old_end = conf.end_time
            
            if next_slot:
                conf.start_time = next_slot
                conf.end_time = next_slot + timedelta(hours=conf_duration)
                db.commit()
                db.refresh(conf)
                rescheduled_log.append({
                    "id": conf.id,
                    "title": conf.title,
                    "category": conf.category,
                    "old_start": old_start.isoformat(),
                    "old_end": old_end.isoformat(),
                    "new_start": conf.start_time.isoformat(),
                    "new_end": conf.end_time.isoformat(),
                    "rescheduled_by_user": False
                })
            else:
                # If we couldn't find a free slot, we just move it to tomorrow morning
                # to prevent complete loss
                fallback_start = (old_start + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
                conf.start_time = fallback_start
                conf.end_time = fallback_start + timedelta(hours=conf_duration)
                db.commit()
                db.refresh(conf)
                rescheduled_log.append({
                    "id": conf.id,
                    "title": conf.title,
                    "category": conf.category,
                    "old_start": old_start.isoformat(),
                    "old_end": old_end.isoformat(),
                    "new_start": conf.start_time.isoformat(),
                    "new_end": conf.end_time.isoformat(),
                    "note": "Rescheduled to fallback slot due to high utilization"
                })
                
        return {
            "status": "success",
            "message": f"Scheduled '{title}' at requested time. Rescheduled {len(conflicts)} conflicting lower-priority events.",
            "event": new_event.to_dict(),
            "rescheduled_events": rescheduled_log
        }
    else:
        # New event loses (or tie). Reschedule the NEW event.
        duration_hours = (end_time - start_time).total_seconds() / 3600.0
        # Find next free slot for the new event, searching from the start_time
        next_slot = find_next_free_slot(db, duration_hours, start_time)
        
        if not next_slot:
            # Fallback
            next_slot = (start_time + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            
        new_event = Event(
            title=title,
            category=category,
            start_time=next_slot,
            end_time=next_slot + timedelta(hours=duration_hours),
            description=f"{description} (Rescheduled due to conflict with higher-priority event)",
            is_recurring=is_recurring,
            recurrence_rule=recurrence_rule
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        
        conflicting_titles = ", ".join([f"'{c.title}' ({c.category})" for c in conflicts])
        return {
            "status": "rescheduled",
            "message": f"Conflict detected with higher-priority event(s): {conflicting_titles}. '{title}' was automatically scheduled at a later free slot.",
            "event": new_event.to_dict(),
            "rescheduled_events": [{
                "id": new_event.id,
                "title": new_event.title,
                "category": new_event.category,
                "old_start": start_time.isoformat(),
                "old_end": end_time.isoformat(),
                "new_start": new_event.start_time.isoformat(),
                "new_end": new_event.end_time.isoformat(),
                "rescheduled_by_user": True
            }]
        }
