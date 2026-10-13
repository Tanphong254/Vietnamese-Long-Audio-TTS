import asyncio
from pathlib import Path

import edge_tts
import pytest

import generate_audio


@pytest.mark.parametrize(
    ("multiplier", "expected"),
    [("0.75", "-25%"), ("1.0", "+0%"), ("1.25", "+25%"),
     ("1.5", "+50%"), ("1.75", "+75%")],
)
def test_rate_mapping(multiplier, expected):
    assert generate_audio.rate_to_edge(multiplier) == expected


def test_reader_accepts_long_utf8_bom_text_without_app_limit(tmp_path: Path):
    source = tmp_path / "kichban.txt"
    expected = ("Tiếng Việt, hội thoại và dấu câu.\n" * 250_000)
    source.write_text("\ufeff" + expected, encoding="utf-8")
    assert generate_audio.read_text_file(source) == expected


def test_reader_rejects_empty_and_placeholder_files(tmp_path: Path):
    source = tmp_path / "kichban.txt"
    source.write_text("  \n", encoding="utf-8")
    with pytest.raises(ValueError, match="trống"):
        generate_audio.read_text_file(source)
    source.write_text(generate_audio.PLACEHOLDER, encoding="utf-8")
    with pytest.raises(ValueError, match="thay dòng hướng dẫn"):
        generate_audio.read_text_file(source)


def test_one_full_script_one_communicate_one_mp3(tmp_path: Path, monkeypatch):
    calls = []

    class FakeCommunicate:
        def __init__(self, *, text, voice, rate):
            calls.append({"text": text, "voice": voice, "rate": rate})

        async def save(self, destination):
            Path(destination).write_bytes(b"mock-mp3-data")

    monkeypatch.setattr(edge_tts, "Communicate", FakeCommunicate)
    monkeypatch.setattr(generate_audio, "configure_websocket_endpoint", lambda: None)
    text = "TRUYỆN DÀI: tiếng Việt.\n" * 100_000
    output = tmp_path / "audio_youtube.mp3"

    result = asyncio.run(generate_audio.synthesize_one_audio(
        text, "vi-VN-HoaiMyNeural", "1.25", output
    ))

    assert result == output
    assert output.read_bytes() == b"mock-mp3-data"
    assert len(calls) == 1
    assert calls[0] == {
        "text": text, "voice": "vi-VN-HoaiMyNeural", "rate": "+25%"
    }
    assert not (tmp_path / "audio_youtube.partial.mp3").exists()


def test_failed_synthesis_retries_the_whole_script(tmp_path: Path, monkeypatch):
    seen = []

    class SometimesFails:
        def __init__(self, *, text, voice, rate):
            seen.append(text)

        async def save(self, destination):
            if len(seen) == 1:
                Path(destination).write_bytes(b"partial")
                raise RuntimeError("temporary service error")
            Path(destination).write_bytes(b"complete-mp3")

    async def no_wait(_):
        return None

    monkeypatch.setattr(edge_tts, "Communicate", SometimesFails)
    monkeypatch.setattr(generate_audio, "configure_websocket_endpoint", lambda: None)
    monkeypatch.setattr(generate_audio.asyncio, "sleep", no_wait)
    output = tmp_path / "audio_youtube.mp3"
    source_text = "Toàn bộ kịch bản, không chia thành các job MP3 riêng."

    result = asyncio.run(generate_audio.synthesize_one_audio(
        source_text, "vi-VN-NamMinhNeural", "1.0", output
    ))

    assert seen == [source_text, source_text]
    assert result.read_bytes() == b"complete-mp3"


def test_failure_after_max_attempts_cleans_partial_file(tmp_path: Path, monkeypatch):
    calls = []

    class AlwaysFails:
        def __init__(self, *, text, voice, rate):
            calls.append(text)

        async def save(self, destination):
            Path(destination).write_bytes(b"partial")
            raise RuntimeError("service unavailable")

    async def no_wait(_):
        return None

    monkeypatch.setattr(edge_tts, "Communicate", AlwaysFails)
    monkeypatch.setattr(generate_audio, "configure_websocket_endpoint", lambda: None)
    monkeypatch.setattr(generate_audio.asyncio, "sleep", no_wait)
    output = tmp_path / "audio_youtube.mp3"

    with pytest.raises(RuntimeError, match="sau 2 lần thử"):
        asyncio.run(generate_audio.synthesize_one_audio(
            "Nội dung thử", "vi-VN-NamMinhNeural", "1.0", output, attempts=2
        ))

    assert len(calls) == 2
    assert not output.exists()
    assert not (tmp_path / "audio_youtube.partial.mp3").exists()
