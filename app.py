from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory, url_for
from werkzeug.exceptions import RequestEntityTooLarge

from tts_engine import JobManager, RATE_OPTIONS, VOICE_OPTIONS

BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = BASE_DIR / "jobs"
OUTPUTS_DIR = BASE_DIR / "outputs"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MiB request limit
app.json.ensure_ascii = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("vietnamese_long_audio_tts")
manager = JobManager(JOBS_DIR, OUTPUTS_DIR)


@app.get("/")
def index():
    return render_template(
        "index.html",
        voices=VOICE_OPTIONS,
        rates=RATE_OPTIONS,
    )


@app.get("/api/jobs")
def list_jobs():
    jobs = manager.list_jobs()
    for job in jobs:
        if job.get("output_filename") and job.get("status") == "completed":
            job["output_url"] = url_for("play_output", filename=job["output_filename"])
            job["download_url"] = url_for("download_output", filename=job["output_filename"])
    return jsonify({"jobs": jobs})


@app.post("/api/jobs")
def create_job():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Dữ liệu gửi lên không hợp lệ."}), 400

    text = data.get("text")
    title = data.get("title", "")
    voice = data.get("voice", "vi-VN-NamMinhNeural")
    rate = str(data.get("rate", "1.25"))
    chunk_size = data.get("chunk_size", 2400)

    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "Vui lòng nhập hoặc tải lên văn bản trước."}), 400
    if not isinstance(title, str):
        return jsonify({"error": "Tên truyện không hợp lệ."}), 400
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool):
        return jsonify({"error": "Độ dài đoạn phải là số nguyên."}), 400

    try:
        job = manager.create_job(title, text, voice, rate, chunk_size)
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    except OSError:
        logger.exception("Could not create TTS job")
        return jsonify({"error": "Không thể lưu dữ liệu tác vụ. Hãy kiểm tra dung lượng ổ đĩa và quyền ghi."}), 500

    return jsonify({"message": "Đã thêm tác vụ vào hàng đợi.", "job": job}), 202


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    try:
        job = manager.get_job(job_id)
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 404
    if job.get("output_filename") and job.get("status") == "completed":
        job["output_url"] = url_for("play_output", filename=job["output_filename"])
        job["download_url"] = url_for("download_output", filename=job["output_filename"])
    return jsonify({"job": job})


@app.post("/api/jobs/<job_id>/cancel")
def cancel_job(job_id: str):
    try:
        job = manager.cancel(job_id)
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"message": "Đã yêu cầu hủy. Đoạn đang xử lý có thể cần hoàn tất trước khi dừng.", "job": job})


@app.post("/api/jobs/<job_id>/retry")
def retry_job(job_id: str):
    try:
        job = manager.retry(job_id)
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"message": "Đã đưa tác vụ trở lại hàng đợi; các đoạn MP3 hợp lệ sẽ được giữ lại.", "job": job}), 202


def _validate_output_name(filename: str) -> bool:
    return bool(filename) and Path(filename).name == filename and ".." not in filename


@app.get("/outputs/<path:filename>")
def play_output(filename: str):
    if not _validate_output_name(filename):
        return jsonify({"error": "Tên tệp không hợp lệ."}), 400
    response = send_from_directory(OUTPUTS_DIR, filename, mimetype="audio/mpeg", as_attachment=False)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/download/<path:filename>")
def download_output(filename: str):
    if not _validate_output_name(filename):
        return jsonify({"error": "Tên tệp không hợp lệ."}), 400
    response = send_from_directory(OUTPUTS_DIR, filename, mimetype="audio/mpeg", as_attachment=True)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return jsonify({"error": "Dữ liệu gửi lên quá lớn (giới hạn yêu cầu 100 MiB). Hãy dùng tệp TXT và chia nhỏ truyện nếu cần."}), 413


@app.errorhandler(500)
def internal_error(_error):
    logger.error("Unhandled Flask server error: %s", _error)
    return jsonify({"error": "Lỗi máy chủ nội bộ. Hãy xem Terminal để biết chi tiết."}), 500


if __name__ == "__main__":
    print("=" * 64)
    print("Vietnamese Long Audio TTS")
    print(f"Jobs:    {JOBS_DIR}")
    print(f"Outputs: {OUTPUTS_DIR}")
    print("Open:    http://127.0.0.1:5000")
    print("Edge-TTS cần Internet để tạo giọng nói.")
    print("Nhấn Ctrl+C trong Terminal để dừng máy chủ.")
    print("=" * 64)
    # Local-only server. Do not expose this development server publicly.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True, use_reloader=False)
