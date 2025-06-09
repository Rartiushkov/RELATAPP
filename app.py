from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import sqlite3
import hmac
import hashlib
import os
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "change_me")

DATABASE = "chat.db"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def verify_telegram_auth(data: dict) -> bool:
    """Validate Telegram login widget data."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    auth_hash = data.pop("hash", None)
    if not auth_hash:
        return False
    data_check = [f"{k}={v}" for k, v in sorted(data.items())]
    data_string = "\n".join(data_check)
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    h = hmac.new(secret_key, data_string.encode(), hashlib.sha256).hexdigest()
    return h == auth_hash


@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("chat"))
    return render_template("index.html", bot_username=TELEGRAM_BOT_USERNAME)


@app.route("/login")
def login():
    data = request.args.to_dict()
    if verify_telegram_auth(data):
        session["user"] = {
            "id": data.get("id"),
            "username": data.get("username"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
        }
        return redirect(url_for("chat"))
    return "Unauthorized", 401


@app.route("/chat")
def chat():
    if "user" not in session:
        return redirect(url_for("index"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, user_id TEXT, role TEXT, content TEXT)"
    )
    cur.execute(
        "SELECT role, content FROM messages WHERE user_id=? ORDER BY id",
        (session["user"]["id"],),
    )
    messages = cur.fetchall()
    return render_template("chat.html", messages=messages, user=session["user"])


@app.route("/send", methods=["POST"])
def send():
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
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
    else:
        reply = "No OpenAI API key configured."

    cur.execute(
        "INSERT INTO messages(user_id, role, content) VALUES(?,?,?)",
        (session["user"]["id"], "assistant", reply),
    )
    conn.commit()
    return jsonify({"reply": reply})



@app.route("/auto_reply", methods=["POST"])
def auto_reply():
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
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
    else:
        reply = "No OpenAI API key configured."
    cur.execute(
        "INSERT INTO messages(user_id, role, content) VALUES(?,?,?)",
        (session["user"]["id"], "assistant", reply),
    )
    conn.commit()
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
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
