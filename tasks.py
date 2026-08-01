from datetime import date

# Разовые задачи с дедлайном (можно оставить пустым списком, если не нужны)
TASKS = [
    # {
    #     "id": "unique_id",
    #     "title": "Что нужно сделать",
    #     "deadline": date(2026, 8, 15),
    #     "category": "любая метка",
    # },
]

# Привычки с недельной целью (сколько раз за Пн-Вс)
HABITS = [
    {"id": "gym", "title": "Зал / бассейн", "weekly_target": 3},
    {"id": "python", "title": "Python практика", "weekly_target": 5},
    {"id": "english", "title": "Английский", "weekly_target": 3},
    {"id": "ml_roadmap", "title": "ML-роадмап / Stepik", "weekly_target": 2},
]

# Время напоминаний (по времени сервера, см. README про таймзону)
MORNING_DIGEST_HOUR = 9
MORNING_DIGEST_MINUTE = 0

EVENING_REMINDER_HOUR = 20
EVENING_REMINDER_MINUTE = 0
