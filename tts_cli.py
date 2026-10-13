from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from tts_engine import JobManager, RATE_OPTIONS, VOICE_OPTIONS

BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = BASE_DIR / "jobs"
OUTPUTS_DIR = BASE_DIR / "outputs"
DEFAULT_INPUT = BASE_DIR / "kichban.txt"


def write_github_output(name: str, value: str) -> None:
    """Expose a value as a step output when running inside GitHub Actions."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        return
    with open(output_file, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def read_job_files() -> list[dict[str, Any]]:
    """Read saved job summaries without starting the background worker."""
    jobs: list[dict[str, Any]] = []
    if not JOBS_DIR.exists():
        return jobs

    for status_path in JOBS_DIR.glob("*/status.json"):
        try:
            state = json.loads(status_path.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                jobs.append(state)
        except (OSError, json.JSONDecodeError):
            continue

    jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return jobs


def _read_state_file(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_state_file(path: Path, state: dict[str, Any]) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def prepare_auto_resume_matching(
    text: str,
    voice: str,
    rate: str,
    chunk_size: int,
) -> str | None:
    """Find the newest unfinished job with identical source and settings.

    Older jobs from a downloaded Actions checkpoint are suspended so that the
    single worker cannot accidentally resume a different story or voice.
    """
    resumable_statuses = {
        "queued", "running", "merging", "interrupted",
        "failed", "cancelled", "cancelling", "suspended",
    }
    active_statuses = {"queued", "running", "merging", "interrupted", "cancelling"}
    matches: list[dict[str, Any]] = []

    if JOBS_DIR.exists():
        for status_path in JOBS_DIR.glob("*/status.json"):
            state = _read_state_file(status_path)
            if not state:
                continue
            if (
                state.get("voice") != voice
                or state.get("rate") != rate
                or state.get("chunk_size") != chunk_size
            ):
                continue
            source_path = status_path.parent / "source.txt"
            try:
                saved_text = source_path.read_text(encoding="utf-8")
            except OSError:
                continue
            if saved_text == text:
                matches.append(state)

    matches.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    newest = matches[0] if matches else None
    selected_id: str | None = None

    # A most-recent completed task means the user intentionally started a new
    # run with the same story/settings; don't resume an older failed duplicate.
    if newest and newest.get("status") in resumable_statuses:
        candidate_id = str(newest.get("id", ""))
        if len(candidate_id) == 32:
            selected_id = candidate_id

    if JOBS_DIR.exists():
        for status_path in JOBS_DIR.glob("*/status.json"):
            state = _read_state_file(status_path)
            if not state or str(state.get("id", "")) == selected_id:
                continue
            if state.get("status") in active_statuses:
                state["status"] = "suspended"
                state["current_chunk"] = None
                state["cancel_requested"] = False
                state["error"] = (
                    "Tạm dừng để ưu tiên tác vụ hiện tại. "
                    "Tác vụ này không bị xóa."
                )
                _write_state_file(status_path, state)

    return selected_id


def print_jobs() -> int:
    jobs = read_job_files()
    if not jobs:
        print("Chưa có tác vụ nào được lưu.")
        return 0

    print("TÁC VỤ ĐÃ LƯU")
    print("-" * 90)
    for job in jobs[:50]:
        total = int(job.get("total_chunks", 0) or 0)
        done = int(job.get("completed_chunks", 0) or 0)
        job_id = str(job.get("id", "unknown"))
        title = str(job.get("title", "Truyện không tên"))
        status = str(job.get("status", "unknown"))
        output = job.get("output_filename")
        print(f"{job_id} | {status:10} | {done}/{total} đoạn | {title}")
        if output:
            print(f"    MP3: {OUTPUTS_DIR / str(output)}")
        elif job.get("error"):
            print(f"    Lỗi: {str(job['error'])[:240]}")
    print("-" * 90)
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Tạo audio truyện dài bằng Edge-TTS. "
            "Trong GitHub Actions, tệp đầu vào mặc định là kichban.txt."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Tệp TXT UTF-8/UTF-8 BOM.")
    parser.add_argument("--title", help="Tên truyện dùng cho tên tệp MP3.")
    parser.add_argument(
        "--voice",
        choices=sorted(VOICE_OPTIONS),
        default="vi-VN-NamMinhNeural",
        help="Mã giọng đọc tiếng Việt.",
    )
    parser.add_argument(
        "--rate",
        choices=sorted(RATE_OPTIONS, key=float),
        default="1.25",
        help="Tốc độ đọc.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=2400,
        help="Kích thước nội bộ của mỗi đoạn gửi Edge-TTS.",
    )
    parser.add_argument(
        "--resume",
        metavar="JOB_ID",
        help="Tiếp tục hoặc thử lại tác vụ đã lưu theo mã.",
    )
    parser.add_argument(
        "--auto-resume-matching",
        action="store_true",
        help="Tự tiếp tục checkpoint khớp nội dung, giọng đọc và tốc độ.",
    )
    parser.add_argument(
        "--list-jobs",
        action="store_true",
        help="Liệt kê tác vụ đã lưu.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Số giây giữa hai lần cập nhật tiến trình.",
    )
    return parser


def monitor_job(manager: JobManager, job_id: str, poll_interval: float) -> int:
    terminal_states = {"completed", "failed", "cancelled"}
    last_line = ""

    try:
        while True:
            state = manager.get_job(job_id)
            status = str(state.get("status", "unknown"))
            completed = int(state.get("completed_chunks", 0) or 0)
            total = int(state.get("total_chunks", 0) or 0)
            percent = int(state.get("percent", 0) or 0)
            current = state.get("current_chunk")
            current_text = f" | đang xử lý đoạn {current}" if current else ""
            line = (
                f"[{percent:3d}%] {completed}/{total} đoạn"
                f" | trạng thái: {status}{current_text}"
            )
            if line != last_line:
                print("\r" + line + " " * 20, end="", flush=True)
                last_line = line

            if status in terminal_states:
                print()
                if status == "completed":
                    filename = state.get("output_filename")
                    if not filename:
                        print("Tác vụ báo hoàn thành nhưng chưa có tên MP3.", file=sys.stderr)
                        return 1
                    output_path = OUTPUTS_DIR / str(filename)
                    if not output_path.is_file() or output_path.stat().st_size == 0:
                        print(f"Không tìm thấy MP3 hợp lệ: {output_path}", file=sys.stderr)
                        return 1
                    relative_path = output_path.relative_to(BASE_DIR).as_posix()
                    write_github_output("output_file", relative_path)
                    print("TẠO AUDIO THÀNH CÔNG")
                    print(f"Tệp: {output_path}")
                    print(f"Mã tác vụ: {job_id}")
                    return 0

                if status == "failed":
                    print("TÁC VỤ THẤT BẠI")
                    print(state.get("error") or "Không có thông tin lỗi.")
                    print("Checkpoint sẽ được giữ lại nếu GitHub Actions tải artifact thành công.")
                    print(f"Mã tác vụ: {job_id}")
                    return 1

                print("Tác vụ đã bị hủy.")
                print(f"Mã tác vụ: {job_id}")
                return 1

            time.sleep(max(0.5, poll_interval))

    except KeyboardInterrupt:
        print("\nĐã ngắt theo dõi. Các đoạn đã lưu sẽ được giữ lại nếu checkpoint được tải lên.")
        print(f"Mã tác vụ: {job_id}")
        return 130


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()

    if args.list_jobs:
        return print_jobs()

    if args.poll_interval <= 0:
        parser.error("--poll-interval phải lớn hơn 0.")
    if args.resume and args.auto_resume_matching:
        parser.error("Chọn --resume hoặc --auto-resume-matching, không dùng cả hai.")
    if args.resume and args.input != str(DEFAULT_INPUT):
        parser.error("--resume không cần --input.")
    if not args.resume and not args.input:
        parser.error("Cần cung cấp tệp TXT.")

    manager: JobManager

    if args.resume:
        try:
            write_github_output("job_id", args.resume)
            manager = JobManager(JOBS_DIR, OUTPUTS_DIR)
            state = manager.get_job(args.resume)
            if state.get("status") in {"failed", "cancelled", "suspended"}:
                manager.retry(args.resume)
                print("Đã đưa tác vụ trở lại hàng đợi; các đoạn MP3 hợp lệ được giữ lại.")
            elif state.get("status") == "completed":
                output = state.get("output_filename")
                if output and (OUTPUTS_DIR / str(output)).is_file():
                    path = OUTPUTS_DIR / str(output)
                    write_github_output("output_file", path.relative_to(BASE_DIR).as_posix())
                    print(f"Tác vụ này đã hoàn thành: {path}")
                    return 0
            print(f"Đang tiếp tục tác vụ: {args.resume}")
            return monitor_job(manager, args.resume, args.poll_interval)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Không thể tiếp tục tác vụ: {exc}", file=sys.stderr)
            return 2

    input_path = Path(args.input).expanduser()
    if not input_path.is_absolute():
        input_path = (BASE_DIR / input_path).resolve()
    if not input_path.is_file():
        print(f"Không tìm thấy tệp đầu vào: {input_path}", file=sys.stderr)
        return 2

    try:
        text = input_path.read_text(encoding="utf-8-sig")
    except UnicodeError:
        print("Không đọc được tệp dưới dạng UTF-8. Hãy lưu TXT bằng UTF-8 rồi thử lại.", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Không đọc được tệp đầu vào: {exc}", file=sys.stderr)
        return 2

    if not text.strip():
        print("Tệp đầu vào không có nội dung.", file=sys.stderr)
        return 2
    if text.strip() == "__DAN_NOI_DUNG_TRUYEN_VAO_DAY__":
        print("Hãy thay dòng hướng dẫn trong kichban.txt bằng nội dung truyện trước khi chạy.", file=sys.stderr)
        return 2

    title = args.title or input_path.stem
    selected_job_id: str | None = None

    try:
        if args.auto_resume_matching:
            selected_job_id = prepare_auto_resume_matching(
                text=text,
                voice=args.voice,
                rate=args.rate,
                chunk_size=args.chunk_size,
            )
            if selected_job_id:
                print(f"Tìm thấy checkpoint phù hợp: {selected_job_id}")

        manager = JobManager(JOBS_DIR, OUTPUTS_DIR)

        if selected_job_id:
            state = manager.get_job(selected_job_id)
            if state.get("status") in {"failed", "cancelled", "suspended"}:
                state = manager.retry(selected_job_id)
            write_github_output("job_id", selected_job_id)
            print("Đang tiếp tục tác vụ phù hợp; các đoạn MP3 hợp lệ sẽ được giữ lại.")
            return monitor_job(manager, selected_job_id, args.poll_interval)

        job = manager.create_job(
            title=title,
            text=text,
            voice=args.voice,
            rate=args.rate,
            chunk_size=args.chunk_size,
        )
    except (ValueError, OSError, FileNotFoundError) as exc:
        print(f"Không thể tạo hoặc tiếp tục tác vụ: {exc}", file=sys.stderr)
        return 2

    job_id = str(job["id"])
    write_github_output("job_id", job_id)
    print(f"Đã thêm tác vụ cho: {title}")
    print(f"Mã tác vụ: {job_id}")
    print(f"Tổng số đoạn: {job.get('total_chunks', 0)}")
    print("Đang tổng hợp bằng Edge-TTS. Tệp input/MP3 không cần commit trong lúc tạo audio.")
    return monitor_job(manager, job_id, args.poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
