from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import sqlite3

import os
import requests
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "change_me")

DATABASE = "chat.db"


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("chat"))

    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)"
    )
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
        cur.execute(
            "CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)"
        )
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
