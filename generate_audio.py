from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

VOICE_OPTIONS = {
    "vi-VN-NamMinhNeural": "Nam Minh",
    "vi-VN-HoaiMyNeural": "Hoài My",
}
RATE_OPTIONS = ("0.75", "1.0", "1.25", "1.5", "1.75")
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "kichban.txt"
DEFAULT_OUTPUT = BASE_DIR / "outputs" / "audio_youtube.mp3"
PLACEHOLDER = "__DAN_NOI_DUNG_TRUYEN_VAO_DAY__"


def rate_to_edge(rate: str) -> str:
    if rate not in RATE_OPTIONS:
        raise ValueError("Tốc độ đọc không hợp lệ.")
    percent = round((float(rate) - 1.0) * 100)
    return f"{percent:+d}%"


def read_text_file(path: str | Path) -> str:
    """Read the complete UTF-8 input file without an app-level character cap."""
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise ValueError(
            f"Không đọc được {source} dưới dạng UTF-8. Hãy lưu tệp bằng UTF-8."
        ) from exc

    if not text.strip():
        raise ValueError(f"Tệp đầu vào đang trống: {source}")
    if text.strip() == PLACEHOLDER:
        raise ValueError(
            "Hãy thay dòng hướng dẫn trong kichban.txt bằng nội dung truyện trước khi chạy."
        )
    return text


def configure_websocket_endpoint() -> None:
    """Use Edge-TTS's upstream endpoint unless an explicit override is supplied.

    The upstream Edge-TTS code now handles the current Sec-MS-GEC v2 handshake.
    Forcing an alternate endpoint while installing a package with an older
    handshake can make the service reject the WebSocket request.
    """
    try:
        import edge_tts.communicate as edge_communicate
    except ImportError as exc:
        raise RuntimeError(
            "Chưa cài edge-tts. Hãy chạy: python -m pip install -r requirements.txt"
        ) from exc

    override = os.environ.get("EDGE_TTS_WEBSOCKET_URL", "").strip()
    if override and override.lower() != "default":
        edge_communicate.WSS_URL = override

async def synthesize_one_audio(
    text: str,
    voice: str,
    rate: str,
    output_path: str | Path,
    attempts: int = 3,
) -> Path:
    """Submit the complete script in one Communicate/save call per attempt.

    This app does not split a story into many separate MP3 jobs. Edge-TTS may
    internally stream smaller text fragments as required by its own protocol,
    but writes all received audio to one continuous output MP3.
    """
    if voice not in VOICE_OPTIONS:
        raise ValueError("Giọng đọc không hợp lệ.")
    edge_rate = rate_to_edge(rate)
    if attempts < 1:
        raise ValueError("Số lần thử phải ít nhất là 1.")

    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError(
            "Chưa cài edge-tts. Hãy chạy: python -m pip install -r requirements.txt"
        ) from exc

    configure_websocket_endpoint()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.stem + ".partial" + destination.suffix)
    partial.unlink(missing_ok=True)

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        partial.unlink(missing_ok=True)
        try:
            communicator = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=edge_rate,
            )
            await communicator.save(str(partial))
            if not partial.is_file() or partial.stat().st_size == 0:
                raise RuntimeError("Edge-TTS không tạo được tệp MP3 hợp lệ.")
            os.replace(partial, destination)
            return destination
        except Exception as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt >= attempts:
                break
            delay = (3, 8)[min(attempt - 1, 1)]
            print(
                f"Lần thử {attempt}/{attempts} thất bại: {exc}. "
                f"Thử lại sau {delay} giây...",
                file=sys.stderr,
                flush=True,
            )
            await asyncio.sleep(delay)

    raise RuntimeError(
        f"Không tạo được audio sau {attempts} lần thử. "
        "Hãy xem log GitHub Actions để biết lỗi chi tiết."
    ) from last_error


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tạo một MP3 từ toàn bộ kichban.txt bằng Edge-TTS."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Tệp TXT UTF-8.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Đường dẫn MP3 đầu ra.")
    parser.add_argument("--voice", choices=sorted(VOICE_OPTIONS),
                        default="vi-VN-NamMinhNeural")
    parser.add_argument("--rate", choices=RATE_OPTIONS, default="1.25")
    parser.add_argument("--attempts", type=int, default=3)
    return parser


def resolve_from_project(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (BASE_DIR / candidate).resolve()


def main() -> int:
    args = make_parser().parse_args()
    try:
        text = read_text_file(resolve_from_project(args.input))
        output = resolve_from_project(args.output)
        print(f"Tệp đầu vào: {args.input}")
        print(f"Số ký tự: {len(text):,}")
        print(f"Giọng đọc: {VOICE_OPTIONS[args.voice]} ({args.voice})")
        print(f"Tốc độ: {args.rate}x")
        print("Đang tổng hợp toàn bộ kịch bản thành một tệp MP3.")
        result = asyncio.run(
            synthesize_one_audio(text, args.voice, args.rate, output, args.attempts)
        )
        print("\nTẠO AUDIO THÀNH CÔNG")
        print(f"MP3: {result}")
        print(f"Dung lượng: {result.stat().st_size:,} byte")
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"\nLỖI: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
