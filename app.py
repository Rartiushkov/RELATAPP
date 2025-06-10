from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import sqlite3
import os
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
import asyncio

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "change_me")
csrf = CSRFProtect(app)

DATABASE = "chat.db"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
API_ID = os.environ.get("TG_API_ID")
API_HASH = os.environ.get("TG_API_HASH")
telegram_client = None
telegram_loop = None


def init_db():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)"
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY,
            user_id TEXT,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            msg_id INTEGER UNIQUE
        )
        """
    )
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def get_telegram_client():
    global telegram_client, telegram_loop
    if telegram_client is None and API_ID and API_HASH:
        if telegram_loop is None:
            telegram_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(telegram_loop)
        telegram_client = TelegramClient(
            "web_session", int(API_ID), API_HASH, loop=telegram_loop
        )
    elif telegram_loop:
        asyncio.set_event_loop(telegram_loop)
    return telegram_client


def store_message(user_id, chat_id, role, content, msg_id=None):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO messages(user_id, chat_id, role, content, msg_id) VALUES(?,?,?,?,?)",
            (user_id, chat_id, role, content, msg_id),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


def sync_messages_from_telegram(chat_id, limit=20):
    client = get_telegram_client()
    if client is None:
        return
    client.connect()
    for msg in client.iter_messages(chat_id, limit=limit, reverse=True):
        role = "user" if msg.out else "peer"
        store_message(session["user"]["id"], chat_id, role, msg.message or "", msg.id)


@app.route("/")
def index():
    if "user" in session:
        if session.get("telegram"):
            return redirect(url_for("dialogs"))
        return redirect(url_for("chat"))
    telegram_enabled = bool(API_ID and API_HASH)
    return render_template("login.html", telegram_enabled=telegram_enabled)


@app.route("/telegram_login", methods=["GET", "POST"])
def telegram_login():
    client = get_telegram_client()
    if client is None:
        return "Telegram login not configured", 500
    if request.method == "POST":
        phone = request.form.get("phone")
        if not phone:
            return render_template("telegram_login.html", error="Phone required")
        client.connect()
        if not client.is_user_authorized():
            client.send_code_request(phone)
            session["tg_phone"] = phone
            return render_template("telegram_code.html")
    return render_template("telegram_login.html")


@app.route("/telegram_code", methods=["POST"])
def telegram_code():
    client = get_telegram_client()
    if client is None:
        return "Telegram login not configured", 500
    phone = session.get("tg_phone")
    code = request.form["code"]
    client.connect()
    if not client.is_user_authorized():
        client.sign_in(phone, code)
    me = client.get_me()
    session["user"] = {"id": me.id, "username": me.username or me.first_name}
    session["telegram"] = True
    return redirect(url_for("dialogs"))


@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, password FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    if row and check_password_hash(row["password"], password):
        session["user"] = {"id": row["id"], "username": username}
        return redirect(url_for("chat"))
    return "Invalid credentials", 401


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users(username, password) VALUES(?, ?)",
                (username, generate_password_hash(password)),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return "User already exists", 400
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/chat")
def chat():
    if "user" not in session:
        return redirect(url_for("index"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content FROM messages WHERE user_id=? ORDER BY id",
        (session["user"]["id"],),
    )
    messages = cur.fetchall()
    return render_template("chat.html", messages=messages, user=session["user"])


@app.route("/send", methods=["POST"])
def send_local():
    if "user" not in session:
        return "Unauthorized", 401
    message = request.form["message"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages(user_id, role, content) VALUES(?,?,?)",
        (session["user"]["id"], "user", message),
    )
    conn.commit()

    reply = ""
    if OPENAI_API_KEY:
        chat_history = [
            {"role": row["role"], "content": row["content"]}
            for row in cur.execute(
                "SELECT role, content FROM messages WHERE user_id=? ORDER BY id",
                (session["user"]["id"],),
            )
        ]
        chat_history.append({"role": "user", "content": message})
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": "gpt-3.5-turbo", "messages": chat_history},
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = f"OpenAI API error: {resp.status_code}"
    else:
        reply = "No OpenAI API key configured."

    cur.execute(
        "INSERT INTO messages(user_id, role, content) VALUES(?,?,?)",
        (session["user"]["id"], "assistant", reply),
    )
    conn.commit()
    return jsonify({"reply": reply})


@app.route("/send/<int:chat_id>", methods=["POST"])
def send_telegram(chat_id):
    if "user" not in session or not session.get("telegram"):
        return "Unauthorized", 401
    message = request.form["message"]
    client = get_telegram_client()
    client.connect()
    sent = client.send_message(chat_id, message)
    store_message(session["user"]["id"], chat_id, "user", message, sent.id)
    return jsonify({"status": "ok"})


@app.route("/dialogs")
def dialogs():
    if "user" not in session or not session.get("telegram"):
        return redirect(url_for("index"))
    client = get_telegram_client()
    client.connect()
    dialogs = [d for d in client.get_dialogs() if d.is_user]
    return render_template("dialogs.html", dialogs=dialogs)


@app.route("/dialog/<int:chat_id>")
def dialog(chat_id):
    if "user" not in session or not session.get("telegram"):
        return redirect(url_for("index"))
    sync_messages_from_telegram(chat_id)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content FROM messages WHERE user_id=? AND chat_id=? ORDER BY msg_id",
        (session["user"]["id"], chat_id),
    )
    messages = cur.fetchall()
    return render_template("chat.html", messages=messages, user=session["user"], chat_id=chat_id)



@app.route("/auto_reply", methods=["POST"])
def auto_reply_local():
    if "user" not in session:
        return "Unauthorized", 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content FROM messages WHERE user_id=? ORDER BY id",
        (session["user"]["id"],),
    )
    chat_history = [
        {"role": row["role"], "content": row["content"]} for row in cur.fetchall()
    ]
    reply = ""
    if OPENAI_API_KEY:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": "gpt-3.5-turbo", "messages": chat_history},
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = f"OpenAI API error: {resp.status_code}"
    else:
        reply = "No OpenAI API key configured."
    cur.execute(
        "INSERT INTO messages(user_id, role, content) VALUES(?,?,?)",
        (session["user"]["id"], "assistant", reply),
    )
    conn.commit()
    return jsonify({"reply": reply})


@app.route("/auto_reply/<int:chat_id>", methods=["POST"])
def auto_reply_telegram(chat_id):
    if "user" not in session or not session.get("telegram"):
        return "Unauthorized", 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content FROM messages WHERE user_id=? AND chat_id=? ORDER BY msg_id",
        (session["user"]["id"], chat_id),
    )
    chat_history = []
    for row in cur.fetchall():
        role = row["role"]
        if role == "peer":
            mapped = "assistant"
        else:
            mapped = role
        chat_history.append({"role": mapped, "content": row["content"]})

    reply = ""
    if OPENAI_API_KEY:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": "gpt-3.5-turbo", "messages": chat_history},
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = f"OpenAI API error: {resp.status_code}"
    else:
        reply = "No OpenAI API key configured."
    client = get_telegram_client()
    client.connect()
    sent = client.send_message(chat_id, reply)
    store_message(session["user"]["id"], chat_id, "assistant", reply, sent.id)
    return jsonify({"reply": reply})


@app.route("/analytics")
def analytics():
    if "user" not in session:
        return redirect(url_for("index"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, COUNT(*) as count FROM messages WHERE user_id=? GROUP BY role",
        (session["user"]["id"],),
    )
    stats = {row["role"]: row["count"] for row in cur.fetchall()}
    return render_template("analytics.html", stats=stats)


@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("tg_phone", None)
    client = get_telegram_client()
    if client and client.is_user_authorized():
        client.log_out()
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
