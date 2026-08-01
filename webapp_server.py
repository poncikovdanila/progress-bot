import hashlib
import hmac
import os
from urllib.parse import parse_qsl

from flask import Flask, jsonify, request, send_from_directory

import storage

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_DIR = os.path.join(os.path.dirname(__file__), "webapp")

app = Flask(__name__)


def verify_init_data(init_data: str) -> bool:
    """Проверяет подпись Telegram.WebApp.initData по алгоритму из документации Telegram:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or not BOT_TOKEN:
        return False
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return False
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return False
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_hash, received_hash)


def require_valid_init_data():
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not verify_init_data(init_data):
        return jsonify({"error": "invalid init data"}), 401
    return None


def habits_payload():
    habits = storage.get_habits()
    result = []
    for h in habits:
        result.append(
            {
                "id": h["id"],
                "title": h["title"],
                "weekly_target": h["weekly_target"],
                "done": storage.get_week_count(h["id"]),
                "logged_today": storage.is_habit_logged_today(h["id"]),
            }
        )
    return {"habits": result}


@app.route("/webapp")
@app.route("/webapp/")
def serve_webapp():
    return send_from_directory(WEBAPP_DIR, "index.html")


@app.route("/api/habits", methods=["GET"])
def get_habits():
    err = require_valid_init_data()
    if err:
        return err
    return jsonify(habits_payload())


@app.route("/api/log", methods=["POST"])
def log_habit():
    err = require_valid_init_data()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    habit_id = body.get("habit_id")
    if not habit_id or not any(h["id"] == habit_id for h in storage.get_habits()):
        return jsonify({"error": "unknown habit_id"}), 400
    storage.log_habit_today(habit_id)
    return jsonify(habits_payload())


@app.route("/api/unlog", methods=["POST"])
def unlog_habit():
    err = require_valid_init_data()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    habit_id = body.get("habit_id")
    if not habit_id or not any(h["id"] == habit_id for h in storage.get_habits()):
        return jsonify({"error": "unknown habit_id"}), 400
    storage.unlog_habit_today(habit_id)
    return jsonify(habits_payload())


@app.route("/api/add", methods=["POST"])
def add_habit_api():
    err = require_valid_init_data()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    try:
        target = int(body.get("weekly_target"))
    except (TypeError, ValueError):
        return jsonify({"error": "bad target"}), 400
    if not title or not (1 <= target <= 7):
        return jsonify({"error": "bad input"}), 400

    import re as _re

    habit_id = _re.sub(r"[^a-zа-яё0-9]+", "_", title.lower()).strip("_") or "habit"
    existing = {h["id"] for h in storage.get_habits()}
    base, n = habit_id, 2
    while habit_id in existing:
        habit_id = f"{base}_{n}"
        n += 1

    storage.add_habit(habit_id, title, target)
    return jsonify(habits_payload())


@app.route("/api/remove", methods=["POST"])
def remove_habit_api():
    err = require_valid_init_data()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    habit_id = body.get("habit_id")
    if not habit_id or not storage.remove_habit(habit_id):
        return jsonify({"error": "unknown habit_id"}), 400
    return jsonify(habits_payload())


@app.route("/healthz")
def healthz():
    return "ok"


def run_webapp_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
