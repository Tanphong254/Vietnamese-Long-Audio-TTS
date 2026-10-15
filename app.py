from __future__ import annotations

import asyncio
import hmac
import os
import queue
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from generate_audio import RATE_OPTIONS, VOICE_OPTIONS, synthesize_one_audio

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("TTS_DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "jobs.sqlite3"
APP_PASSWORD = os.environ.get("WEB_APP_PASSWORD", "")
SESSION_SECRET = os.environ.get("WEB_SESSION_SECRET") or secrets.token_hex(32)

app = Flask(__name__)
app.secret_key = SESSION_SECRET
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "").lower() in {"1", "true", "yes"}

job_queue: queue.Queue[int] = queue.Queue()
_worker_lock = threading.Lock()
_worker_started = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


def initialize_db() -> None:
    with connect_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                voice TEXT NOT NULL,
                rate TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error TEXT,
                audio_path TEXT,
                source_text TEXT
            )
            """
        )
        # A server restart may interrupt a generation. Re-queue unfinished jobs;
        # synthesize_one_audio removes any stale partial MP3 before retrying.
        db.execute(
            "UPDATE jobs SET status='queued', started_at=NULL "
            "WHERE status='generating'"
        )


def job_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label": f"AU {row['id']}",
        "status": row["status"],
        "voice": row["voice"],
        "voice_label": VOICE_OPTIONS.get(row["voice"], row["voice"]),
        "rate": row["rate"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "error": row["error"],
        "has_audio": bool(row["audio_path"] and Path(row["audio_path"]).is_file()),
    }


def get_job(job_id: int, include_text: bool = False) -> sqlite3.Row | None:
    with connect_db() as db:
        columns = "*" if include_text else (
            "id, status, voice, rate, created_at, started_at, completed_at, "
            "error, audio_path"
        )
        return db.execute(
            f"SELECT {columns} FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()


def set_job_status(
    job_id: int,
    status: str,
    *,
    started_at: str | None = None,
    completed_at: str | None = None,
    error: str | None = None,
    audio_path: str | None = None,
    clear_text: bool = False,
) -> None:
    with connect_db() as db:
        db.execute(
            """
            UPDATE jobs SET status=?, started_at=COALESCE(?, started_at),
                completed_at=COALESCE(?, completed_at), error=?, audio_path=?,
                source_text=CASE WHEN ? THEN NULL ELSE source_text END
            WHERE id=?
            """,
            (
                status,
                started_at,
                completed_at,
                error,
                audio_path,
                int(clear_text),
                job_id,
            ),
        )


def process_job(job_id: int) -> None:
    with connect_db() as db:
        row = db.execute(
            "SELECT id, voice, rate, source_text FROM jobs WHERE id=?",
            (job_id,),
        ).fetchone()

    if row is None or row["status"] not in {"queued", "generating"}:
        return

    text = row["source_text"]
    if not text or not text.strip():
        set_job_status(
            job_id,
            "failed",
            completed_at=utc_now(),
            error="Không tìm thấy nội dung cần tổng hợp. Hãy tạo lượt mới.",
            clear_text=True,
        )
        return

    voice = row["voice"]
    rate = row["rate"]
    output_path = AUDIO_DIR / f"au_{job_id:06d}.mp3"
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    set_job_status(job_id, "generating", started_at=utc_now(), error=None)

    try:
        asyncio.run(
            synthesize_one_audio(
                text=text,
                voice=voice,
                rate=rate,
                output_path=output_path,
                attempts=3,
            )
        )
        if not output_path.is_file() or output_path.stat().st_size < 128:
            raise RuntimeError("Tệp MP3 đầu ra rỗng hoặc không hợp lệ.")
        set_job_status(
            job_id,
            "completed",
            completed_at=utc_now(),
            audio_path=str(output_path),
            error=None,
            clear_text=True,
        )
    except Exception as exc:  # Keep a failed AU in history; never reuse its number.
        partial_path = output_path.with_name(output_path.stem + ".partial" + output_path.suffix)
        partial_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        message = str(exc).strip() or exc.__class__.__name__
        set_job_status(
            job_id,
            "failed",
            completed_at=utc_now(),
            error=message[:1500],
            audio_path=None,
            clear_text=True,
        )


def worker_loop() -> None:
    while True:
        job_id = job_queue.get()
        try:
            process_job(job_id)
        except Exception as exc:
            try:
                set_job_status(
                    job_id,
                    "failed",
                    completed_at=utc_now(),
                    error=f"Lỗi nội bộ: {str(exc)[:1200]}",
                    clear_text=True,
                )
            except Exception:
                app.logger.exception("Unable to save failure state for AU %s", job_id)
        finally:
            job_queue.task_done()


def start_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        initialize_db()
        with connect_db() as db:
            unfinished = db.execute(
                "SELECT id FROM jobs WHERE status='queued' ORDER BY id"
            ).fetchall()
        for row in unfinished:
            job_queue.put(row["id"])
        thread = threading.Thread(
            target=worker_loop, name="long-audio-worker", daemon=True
        )
        thread.start()
        _worker_started = True


def local_request() -> bool:
    return request.remote_addr in {"127.0.0.1", "::1", "localhost", None}


@app.before_request
def protect_web_app():
    if request.endpoint == "health":
        return None

    # Local development can be used without a password. A network-hosted app
    # refuses non-local connections until a password is configured.
    if not APP_PASSWORD and not local_request():
        return (
            "Ứng dụng chưa được bảo vệ. Hãy đặt biến môi trường WEB_APP_PASSWORD "
            "trước khi mở website ra Internet.",
            503,
        )

    if not APP_PASSWORD or request.endpoint in {"login", "static"}:
        return None
    if session.get("authenticated"):
        return None
    if request.path.startswith("/api/"):
        return jsonify({"error": "Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại."}), 401
    return redirect(url_for("login", next=request.path))


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        candidate = str(request.form.get("password", ""))
        if APP_PASSWORD and hmac.compare_digest(candidate, APP_PASSWORD):
            session.clear()
            session["authenticated"] = True
            target = request.args.get("next", "")
            if not target.startswith("/") or target.startswith("//"):
                target = url_for("index")
            return redirect(target)
        error = "Mật khẩu chưa đúng."
    return render_template("login.html", error=error, password_required=bool(APP_PASSWORD))


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
def index():
    start_worker()
    return render_template(
        "index.html",
        voices=VOICE_OPTIONS,
        rates=RATE_OPTIONS,
        password_enabled=bool(APP_PASSWORD),
    )


@app.get("/api/jobs")
def list_jobs():
    start_worker()
    try:
        limit = int(request.args.get("limit", "60"))
    except ValueError:
        limit = 60
    limit = min(max(limit, 1), 200)
    with connect_db() as db:
        rows = db.execute(
            """
            SELECT id, status, voice, rate, created_at, started_at,
                   completed_at, error, audio_path
            FROM jobs ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return jsonify({"jobs": [job_to_dict(row) for row in rows]})


@app.post("/api/jobs")
def create_job():
    start_worker()
    payload = request.get_json(silent=True) or {}
    content = payload.get("content")
    voice = payload.get("voice")
    rate = str(payload.get("rate", ""))

    if not isinstance(content, str) or not content.strip():
        return jsonify({"error": "Hãy nhập nội dung cần chuyển thành audio."}), 400
    if voice not in VOICE_OPTIONS:
        return jsonify({"error": "Giọng đọc không hợp lệ."}), 400
    if rate not in RATE_OPTIONS:
        return jsonify({"error": "Tốc độ đọc không hợp lệ."}), 400

    created_at = utc_now()
    with connect_db() as db:
        cursor = db.execute(
            """
            INSERT INTO jobs(status, voice, rate, created_at, source_text)
            VALUES('queued', ?, ?, ?, ?)
            """,
            (voice, rate, created_at, content),
        )
        job_id = int(cursor.lastrowid)

    # Number is allocated before queueing, so failures never renumber later jobs.
    job_queue.put(job_id)
    row = get_job(job_id)
    return jsonify({"job": job_to_dict(row)}), 201


@app.get("/api/jobs/<int:job_id>/audio")
def get_audio(job_id: int):
    row = get_job(job_id)
    if row is None:
        abort(404)
    if row["status"] != "completed" or not row["audio_path"]:
        return jsonify({"error": "Audio chưa sẵn sàng."}), 409
    path = Path(row["audio_path"])
    if not path.is_file():
        return jsonify({"error": "Không tìm thấy tệp audio trên ổ lưu trữ."}), 410

    download = request.args.get("download") == "1"
    return send_file(
        path,
        mimetype="audio/mpeg",
        as_attachment=download,
        download_name=f"AU_{job_id}.mp3",
        conditional=True,
        max_age=0,
    )


# Initialize the durable queue on import so it also works under Gunicorn.
start_worker()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
        threaded=True,
    )
