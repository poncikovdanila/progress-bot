import json
import os
from datetime import date, timedelta

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


def _empty_state():
    return {"habit_logs": {}, "completed_tasks": [], "habits": None}


def load_state():
    if not os.path.exists(DATA_FILE):
        return _empty_state()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty_state()


def save_state(state):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def log_habit_today(habit_id: str):
    state = load_state()
    today = date.today().isoformat()
    state["habit_logs"].setdefault(habit_id, [])
    if today not in state["habit_logs"][habit_id]:
        state["habit_logs"][habit_id].append(today)
    save_state(state)


def is_habit_logged_today(habit_id: str) -> bool:
    state = load_state()
    today = date.today().isoformat()
    return today in state.get("habit_logs", {}).get(habit_id, [])


def week_start():
    today = date.today()
    return today - timedelta(days=today.weekday())  # Monday


def get_week_count(habit_id: str) -> int:
    state = load_state()
    logs = state.get("habit_logs", {}).get(habit_id, [])
    start = week_start()
    count = 0
    for entry in logs:
        d = date.fromisoformat(entry)
        if d >= start:
            count += 1
    return count


def any_habit_unlogged_today(habit_ids) -> bool:
    return any(not is_habit_logged_today(h) for h in habit_ids)


def get_habits():
    """Возвращает список привычек. При первом запуске сидируется из tasks.HABITS,
    дальше живёт только в data.json — правки через бота переживают редеплой кода."""
    state = load_state()
    if not state.get("habits"):
        from tasks import HABITS as DEFAULT_HABITS

        state["habits"] = DEFAULT_HABITS
        save_state(state)
    return state["habits"]


def add_habit(habit_id: str, title: str, weekly_target: int) -> bool:
    state = load_state()
    state.setdefault("habits", get_habits())
    if any(h["id"] == habit_id for h in state["habits"]):
        return False
    state["habits"].append(
        {"id": habit_id, "title": title, "weekly_target": weekly_target}
    )
    save_state(state)
    return True


def remove_habit(habit_id: str) -> bool:
    state = load_state()
    habits = state.get("habits") or get_habits()
    new_habits = [h for h in habits if h["id"] != habit_id]
    removed = len(new_habits) != len(habits)
    state["habits"] = new_habits
    save_state(state)
    return removed


def set_habit_target(habit_id: str, weekly_target: int) -> bool:
    state = load_state()
    habits = state.get("habits") or get_habits()
    for h in habits:
        if h["id"] == habit_id:
            h["weekly_target"] = weekly_target
            state["habits"] = habits
            save_state(state)
            return True
    return False


def mark_task_done(task_id: str):
    state = load_state()
    if task_id not in state["completed_tasks"]:
        state["completed_tasks"].append(task_id)
    save_state(state)


def is_task_done(task_id: str) -> bool:
    state = load_state()
    return task_id in state.get("completed_tasks", [])
