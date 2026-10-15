import json
from pathlib import Path

import app as web_app


class FakeQueue:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


def test_create_jobs_assign_numbers_when_submitted(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(web_app, "DB_PATH", tmp_path / "test.sqlite3")
    fake_queue = FakeQueue()
    monkeypatch.setattr(web_app, "job_queue", fake_queue)
    web_app.initialize_db()

    client = web_app.app.test_client()
    payload = {
        "content": "Đoạn truyện thử nghiệm.",
        "voice": "vi-VN-NamMinhNeural",
        "rate": "1.25",
    }

    first = client.post(
        "/api/jobs", data=json.dumps(payload), content_type="application/json"
    )
    second = client.post(
        "/api/jobs", data=json.dumps(payload), content_type="application/json"
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["job"]["label"] == "AU 1"
    assert second.get_json()["job"]["label"] == "AU 2"
    assert fake_queue.items == [1, 2]

    history = client.get("/api/jobs").get_json()["jobs"]
    assert [job["label"] for job in history] == ["AU 2", "AU 1"]
    assert all(job["status"] == "queued" for job in history)


def test_create_job_rejects_missing_text_and_invalid_options(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(web_app, "DB_PATH", tmp_path / "test.sqlite3")
    fake_queue = FakeQueue()
    monkeypatch.setattr(web_app, "job_queue", fake_queue)
    web_app.initialize_db()
    client = web_app.app.test_client()

    missing_text = client.post(
        "/api/jobs",
        json={"content": "  ", "voice": "vi-VN-NamMinhNeural", "rate": "1.25"},
    )
    invalid_voice = client.post(
        "/api/jobs",
        json={"content": "Nội dung", "voice": "invalid", "rate": "1.25"},
    )

    assert missing_text.status_code == 400
    assert invalid_voice.status_code == 400
    assert fake_queue.items == []
