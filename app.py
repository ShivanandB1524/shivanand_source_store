
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from functools import wraps

from flask import Flask, jsonify, request, render_template, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "store.db"
PROTECTED_DIR = BASE_DIR / "protected_files"
SECRET_KEY = os.environ.get("SOURCE_STORE_SECRET", "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        payment_id TEXT,
        purchased_at TEXT NOT NULL,
        UNIQUE(user_id, product_id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    con.commit()
    con.close()


def make_token(user_id):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(days=30)},
        SECRET_KEY,
        algorithm="HS256",
    )


def current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], SECRET_KEY, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except Exception:
        return None
    con = db()
    user = con.execute("SELECT id,name,phone FROM users WHERE id=?", (user_id,)).fetchone()
    con.close()
    return user


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"detail": "Please login again."}), 401
        return fn(user, *args, **kwargs)
    return wrapper


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/api/auth/signup")
def signup():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    phone = "".join(ch for ch in str(data.get("phone", "")) if ch.isdigit())
    password = str(data.get("password", ""))

    if len(name) < 2:
        return jsonify({"detail": "Please enter your full name."}), 400
    if len(phone) != 10:
        return jsonify({"detail": "Enter a valid 10-digit phone number."}), 400
    if len(password) < 8:
        return jsonify({"detail": "Password must be at least 8 characters."}), 400

    con = db()
    try:
        cur = con.execute(
            "INSERT INTO users(name,phone,password_hash,created_at) VALUES(?,?,?,?)",
            (name, phone, generate_password_hash(password), datetime.now(timezone.utc).isoformat()),
        )
        con.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        con.close()
        return jsonify({"detail": "An account with this phone number already exists."}), 409
    con.close()

    return jsonify({
        "token": make_token(user_id),
        "user": {"id": user_id, "name": name, "phone": phone}
    })


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    phone = "".join(ch for ch in str(data.get("phone", "")) if ch.isdigit())
    password = str(data.get("password", ""))

    con = db()
    user = con.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
    con.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"detail": "Incorrect phone number or password."}), 401

    return jsonify({
        "token": make_token(user["id"]),
        "user": {"id": user["id"], "name": user["name"], "phone": user["phone"]}
    })


@app.get("/api/purchases")
@require_auth
def purchases(user):
    con = db()
    rows = con.execute(
        "SELECT product_id,product_name,purchased_at FROM purchases WHERE user_id=? ORDER BY purchased_at DESC",
        (user["id"],)
    ).fetchall()
    con.close()
    return jsonify({"purchases": [dict(r) for r in rows]})


@app.get("/api/purchases/<product_id>/download")
@require_auth
def download_purchase(user, product_id):
    con = db()
    purchase = con.execute(
        "SELECT product_id FROM purchases WHERE user_id=? AND product_id=?",
        (user["id"], product_id)
    ).fetchone()
    con.close()

    if not purchase:
        return jsonify({"detail": "This source code has not been purchased on this account."}), 403

    # Put the actual ZIP files in protected_files/ and name them <product_id>.zip.
    filename = f"{product_id}.zip"
    if not (PROTECTED_DIR / filename).is_file():
        return jsonify({"detail": "The source file is not configured on the server yet."}), 404

    return send_from_directory(PROTECTED_DIR, filename, as_attachment=True)


@app.post("/api/admin/grant-purchase")
def grant_purchase():
    """
    DEVELOPMENT / ADMIN ENDPOINT.
    In production, protect this with an admin secret and preferably replace it
    with a verified Razorpay webhook handler.

    JSON:
    {
      "admin_secret": "...",
      "phone": "9876543210",
      "product_id": "macosclone",
      "product_name": "MAC OS Clone",
      "payment_id": "pay_xxx"
    }
    """
    data = request.get_json(silent=True) or {}
    if data.get("admin_secret") != os.environ.get("STORE_ADMIN_SECRET"):
        return jsonify({"detail": "Forbidden"}), 403

    phone = "".join(ch for ch in str(data.get("phone", "")) if ch.isdigit())
    product_id = str(data.get("product_id", "")).strip()
    product_name = str(data.get("product_name", "")).strip()
    payment_id = str(data.get("payment_id", "")).strip()

    con = db()
    user = con.execute("SELECT id FROM users WHERE phone=?", (phone,)).fetchone()
    if not user:
        con.close()
        return jsonify({"detail": "User not found."}), 404

    con.execute(
        """INSERT INTO purchases(user_id,product_id,product_name,payment_id,purchased_at)
           VALUES(?,?,?,?,?)
           ON CONFLICT(user_id,product_id) DO UPDATE SET
             payment_id=excluded.payment_id,
             purchased_at=excluded.purchased_at""",
        (user["id"], product_id, product_name, payment_id, datetime.now(timezone.utc).isoformat())
    )
    con.commit()
    con.close()
    return jsonify({"ok": True})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
