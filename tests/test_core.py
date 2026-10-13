from pathlib import Path

import pytest

from tts_engine import (
    DEFAULT_CHUNK_SIZE,
    MAX_CHUNK_SIZE,
    MIN_CHUNK_SIZE,
    JobManager,
    rate_to_edge,
    safe_title,
    split_text,
)


def test_split_text_rejoins_source_exactly():
    source = (
        "Chương 1: Khởi đầu.\n\n"
        + ("Đây là đoạn văn tiếng Việt có dấu, lời thoại: ‘Xin chào!’ " * 160)
        + "\n\nKết thúc chương.\n"
    )
    chunks = split_text(source, 1200)
    assert len(chunks) > 1
    assert "".join(chunks) == source
    assert all(0 < len(chunk) <= 1200 for chunk in chunks)


@pytest.mark.parametrize(
    "size",
    [MIN_CHUNK_SIZE, 1200, DEFAULT_CHUNK_SIZE, MAX_CHUNK_SIZE],
)
def test_split_text_accepts_supported_sizes(size):
    source = "abc " * 2000
    chunks = split_text(source, size)
    assert "".join(chunks) == source
    assert max(map(len, chunks)) <= size


def test_split_text_uses_hard_boundary_for_unbroken_text():
    source = "字" * 6000
    chunks = split_text(source, 1200)
    assert [len(part) for part in chunks] == [1200] * 5
    assert "".join(chunks) == source


def test_split_text_rejects_invalid_chunk_size():
    with pytest.raises(ValueError):
        split_text("some text", 100)
    with pytest.raises(ValueError):
        split_text("some text", 10000)


def test_split_text_empty_or_whitespace():
    assert split_text("   \n\n  ") == []


@pytest.mark.parametrize(
    ("ui_rate", "edge_rate"),
    [
        ("0.75", "-25%"),
        ("1.0", "+0%"),
        ("1.25", "+25%"),
        ("1.5", "+50%"),
        ("1.75", "+75%"),
    ],
)
def test_rate_mapping(ui_rate, edge_rate):
    assert rate_to_edge(ui_rate) == edge_rate


def test_rate_rejects_unknown_values():
    with pytest.raises(ValueError):
        rate_to_edge("9.0")


def test_safe_title_removes_windows_invalid_filename_chars():
    result = safe_title("  Tên truyện: Phần 1/?*  ")
    assert result
    assert not any(char in result for char in '<>:"/\\|?*')
    assert result == "Tên_truyện__Phần_1"


def test_split_text_preserves_tabs_and_newlines():
    source = ("A\tB\nC\n\nD. " * 300)
    assert "".join(split_text(source, 500)) == source


def test_job_manager_processes_segments_and_merges_with_fake_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import time
    import tts_engine

    def fake_synthesize(text, voice, rate, output_path):
        output_path.write_bytes((f"[{voice}|{rate}]" + text).encode("utf-8"))

    def fake_merge(segment_paths, job_dir, output_path):
        output_path.write_bytes(b"".join(path.read_bytes() for path in segment_paths))

    monkeypatch.setattr(tts_engine, "synthesize_chunk", fake_synthesize)
    monkeypatch.setattr(tts_engine, "merge_mp3_segments", fake_merge)

    manager = JobManager(
        tmp_path / "jobs", tmp_path / "outputs", max_retries=1
    )
    source = "Một đoạn truyện tiếng Việt. " * 90
    job = manager.create_job(
        "Truyện kiểm thử", source, "vi-VN-NamMinhNeural", "1.0", 500
    )

    deadline = time.time() + 5
    state = manager.get_job(job["id"])
    while state["status"] not in {"completed", "failed"} and time.time() < deadline:
        time.sleep(0.025)
        state = manager.get_job(job["id"])

    assert state["status"] == "completed", state.get("error")
    assert state["completed_chunks"] == state["total_chunks"]
    assert state["output_filename"]
    output = tmp_path / "outputs" / state["output_filename"]
    assert output.is_file()
    assert output.stat().st_size > 0
    segments = tmp_path / "jobs" / job["id"] / "segments"
    assert len(list(segments.glob("*.mp3"))) == state["total_chunks"]
