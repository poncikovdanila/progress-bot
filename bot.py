import logging
import os
import re
import threading
import time as time_module
from datetime import time

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from tasks import (
    TASKS,
    MORNING_DIGEST_HOUR,
    MORNING_DIGEST_MINUTE,
    EVENING_REMINDER_HOUR,
    EVENING_REMINDER_MINUTE,
)
import storage
from webapp_server import run_webapp_server

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")  # куда слать напоминания; можно узнать через /start
WEBAPP_URL = os.environ.get("WEBAPP_URL")  # https-адрес вида https://твой-сервис.onrender.com/webapp


def progress_bar(done: int, target: int, width: int = 10) -> str:
    filled = min(width, round(width * done / target)) if target else 0
    return "▓" * filled + "░" * (width - filled)


def build_habits_text_and_keyboard():
    habits = storage.get_habits()
    if not habits:
        return (
            "Привычек пока нет. Добавь первую: `/addhabit 3 Зал`",
            InlineKeyboardMarkup([]),
        )
    lines = ["*Твои привычки на этой неделе:*\n"]
    buttons = []
    for habit in habits:
        done = storage.get_week_count(habit["id"])
        target = habit["weekly_target"]
        bar = progress_bar(done, target)
        logged = storage.is_habit_logged_today(habit["id"])
        logged_today = "✅" if logged else ""
        lines.append(f"{habit['title']}: {bar} {done}/{target} {logged_today}")
        if logged:
            buttons.append(
                [InlineKeyboardButton(f"↩️ Отменить: {habit['title']}", callback_data=f"unlog_{habit['id']}")]
            )
        else:
            buttons.append(
                [InlineKeyboardButton(f"Отметить: {habit['title']}", callback_data=f"log_{habit['id']}")]
            )
    return "\n".join(lines), InlineKeyboardMarkup(buttons)


def build_tasks_text():
    if not TASKS:
        return "Разовых задач с дедлайном пока нет. Добавь их в tasks.py."
    lines = ["*Задачи:*\n"]
    for task in TASKS:
        status = "✅" if storage.is_task_done(task["id"]) else "▫️"
        lines.append(f"{status} {task['title']} (до {task['deadline']})")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if WEBAPP_URL:
        # постоянная кнопка внизу экрана + инлайн-кнопка для открытия прямо сейчас
        reply_kb = ReplyKeyboardMarkup(
            [[KeyboardButton("Открыть привычки", web_app=WebAppInfo(url=WEBAPP_URL))]],
            resize_keyboard=True,
            is_persistent=True,
        )
        inline_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Открыть привычки", web_app=WebAppInfo(url=WEBAPP_URL))]]
        )
        await update.message.reply_text("Привычки:", reply_markup=reply_kb)
        await update.message.reply_text("Жми:", reply_markup=inline_kb)
        return

    await update.message.reply_text(
        f"Привет! Я твой бот-трекер.\n\n"
        f"Твой chat_id: `{chat_id}`\n"
        f"Mini App пока не настроен — не задана переменная окружения WEBAPP_URL.\n\n"
        f"Команды:\n"
        f"/habits — привычки за неделю\n"
        f"/tasks — разовые задачи\n"
        f"/progress — общая сводка\n"
        f"/addhabit <цель> <название> — добавить привычку\n"
        f"/sethabit <id> <цель> — поменять недельную цель\n"
        f"/removehabit <id> — удалить привычку\n"
        f"/unlog <id> — снять сегодняшнюю отметку\n"
        f"/help — все команды",
        parse_mode="Markdown",
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Твой chat_id: `{update.effective_chat.id}`\n\n"
        f"Команды:\n"
        f"/app — открыть мини-приложение\n"
        f"/habits — привычки за неделю (текстом)\n"
        f"/tasks — разовые задачи\n"
        f"/progress — общая сводка\n"
        f"/addhabit <цель> <название> — добавить привычку, например `/addhabit 4 Чтение`\n"
        f"/sethabit <id> <цель> — поменять недельную цель\n"
        f"/removehabit <id> — удалить привычку\n"
        f"/unlog <id> — снять сегодняшнюю отметку",
        parse_mode="Markdown",
    )


async def habits_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, keyboard = build_habits_text_and_keyboard()
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_tasks_text(), parse_mode="Markdown")


async def progress_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    habits_text, keyboard = build_habits_text_and_keyboard()
    tasks_text = build_tasks_text()
    await update.message.reply_text(
        f"{tasks_text}\n\n{habits_text}", parse_mode="Markdown", reply_markup=keyboard
    )


async def on_habit_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Отмечено!")
    habit_id = query.data.replace("log_", "")
    storage.log_habit_today(habit_id)
    text, keyboard = build_habits_text_and_keyboard()
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-zа-яё0-9]+", "_", title.lower()).strip("_")
    return slug or f"habit_{int(time_module.time())}"


async def addhabit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Формат: `/addhabit <цель_в_неделю> <название>`\nНапример: `/addhabit 4 Чтение`",
            parse_mode="Markdown",
        )
        return
    try:
        target = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Первый аргумент — число (сколько раз в неделю).")
        return
    title = " ".join(context.args[1:])
    habit_id = _slugify(title)
    if storage.add_habit(habit_id, title, target):
        await update.message.reply_text(f"Добавил «{title}», цель {target}/нед. (id: `{habit_id}`)", parse_mode="Markdown")
    else:
        await update.message.reply_text("Привычка с таким id уже есть — попробуй другое название.")


async def removehabit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        ids = ", ".join(h["id"] for h in storage.get_habits())
        await update.message.reply_text(f"Укажи id: `/removehabit <id>`\nТекущие: {ids}", parse_mode="Markdown")
        return
    habit_id = context.args[0]
    if storage.remove_habit(habit_id):
        await update.message.reply_text(f"Удалил привычку `{habit_id}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Не нашёл привычку с таким id. Посмотри id через /habits.")


async def sethabit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Формат: `/sethabit <id> <новая_цель>`", parse_mode="Markdown")
        return
    habit_id, raw_target = context.args[0], context.args[1]
    try:
        target = int(raw_target)
    except ValueError:
        await update.message.reply_text("Цель должна быть числом.")
        return
    if storage.set_habit_target(habit_id, target):
        await update.message.reply_text(f"Обновил цель для `{habit_id}`: {target}/нед.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Не нашёл привычку с таким id. Посмотри id через /habits.")


async def app_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not WEBAPP_URL:
        await update.message.reply_text(
            "Mini App пока не настроен: не задана переменная окружения WEBAPP_URL "
            "(нужен https-адрес, локально это не сработает — см. README)."
        )
        return
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Открыть привычки", web_app=WebAppInfo(url=WEBAPP_URL))]]
    )
    await update.message.reply_text("Жми, чтобы открыть:", reply_markup=keyboard)


async def on_unlog_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    habit_id = query.data.replace("unlog_", "")
    if storage.unlog_habit_today(habit_id):
        await query.answer("Отметка снята")
    else:
        await query.answer("Сегодня и не было отмечено")
    text, keyboard = build_habits_text_and_keyboard()
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def unlog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        ids = ", ".join(h["id"] for h in storage.get_habits())
        await update.message.reply_text(
            f"Формат: `/unlog <id>`\nТекущие: {ids}\n\nИли просто нажми кнопку «↩️ Отменить» в /habits.",
            parse_mode="Markdown",
        )
        return
    habit_id = context.args[0]
    if storage.unlog_habit_today(habit_id):
        await update.message.reply_text(f"Снял сегодняшнюю отметку с `{habit_id}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Сегодня эта привычка не отмечена (или неверный id).")


async def morning_digest(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID:
        return
    tasks_text = build_tasks_text()
    habits_text, keyboard = build_habits_text_and_keyboard()
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"Доброе утро! Вот сводка на сегодня:\n\n{tasks_text}\n\n{habits_text}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def evening_reminder(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID:
        return
    habit_ids = [h["id"] for h in storage.get_habits()]
    if not storage.any_habit_unlogged_today(habit_ids):
        return  # всё уже отмечено, не спамим
    text, keyboard = build_habits_text_and_keyboard()
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"Вечер. Кое-что из привычек ещё не отмечено сегодня:\n\n{text}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def post_init(application: Application):
    """Ставит кнопку-меню слева от поля ввода — она открывает Mini App одним тапом."""
    if WEBAPP_URL:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Привычки", web_app=WebAppInfo(url=WEBAPP_URL))
        )
        logger.info("Кнопка-меню настроена на Mini App")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения BOT_TOKEN")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("habits", habits_cmd))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("progress", progress_cmd))
    app.add_handler(CommandHandler("addhabit", addhabit_cmd))
    app.add_handler(CommandHandler("removehabit", removehabit_cmd))
    app.add_handler(CommandHandler("sethabit", sethabit_cmd))
    app.add_handler(CommandHandler("app", app_cmd))
    app.add_handler(CommandHandler("unlog", unlog_cmd))
    app.add_handler(CallbackQueryHandler(on_habit_button, pattern="^log_"))
    app.add_handler(CallbackQueryHandler(on_unlog_button, pattern="^unlog_"))

    app.job_queue.run_daily(
        morning_digest, time=time(MORNING_DIGEST_HOUR, MORNING_DIGEST_MINUTE)
    )
    app.job_queue.run_daily(
        evening_reminder, time=time(EVENING_REMINDER_HOUR, EVENING_REMINDER_MINUTE)
    )

    logger.info("Бот запущен")

    webapp_thread = threading.Thread(target=run_webapp_server, daemon=True)
    webapp_thread.start()
    logger.info("Веб-сервер для Mini App запущен")

    app.run_polling()


if __name__ == "__main__":
    main()
