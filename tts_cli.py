from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from tts_engine import JobManager, RATE_OPTIONS, VOICE_OPTIONS

BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = BASE_DIR / "jobs"
OUTPUTS_DIR = BASE_DIR / "outputs"


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
    print("Tiếp tục một tác vụ: python tts_cli.py --resume MA_TAC_VU")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Tạo audio truyện dài bằng Edge-TTS ngay trong GitHub Codespaces. "
            "Từng đoạn được lưu để có thể tiếp tục sau khi bị gián đoạn."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", help="Đường dẫn tệp TXT UTF-8/UTF-8 BOM.")
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
        help="Độ dài mỗi đoạn văn bản (500–3500 ký tự).",
    )
    parser.add_argument(
        "--resume",
        metavar="JOB_ID",
        help="Tiếp tục hoặc thử lại một tác vụ đã lưu.",
    )
    parser.add_argument(
        "--list-jobs",
        action="store_true",
        help="Liệt kê tác vụ đã lưu và không bắt đầu tạo audio.",
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
                    print("TẠO AUDIO THÀNH CÔNG")
                    print(f"Tệp: {output_path}")
                    print(f"Mã tác vụ: {job_id}")
                    print("Trong Explorer của Codespaces, mở thư mục outputs và tải MP3 về máy.")
                    return 0

                if status == "failed":
                    print("TÁC VỤ THẤT BẠI")
                    print(state.get("error") or "Không có thông tin lỗi.")
                    print(f"Các đoạn đã tạo vẫn được giữ lại. Tiếp tục bằng:")
                    print(f"    python tts_cli.py --resume {job_id}")
                    return 1

                print("Tác vụ đã bị hủy.")
                print(f"Tiếp tục bằng: python tts_cli.py --resume {job_id}")
                return 1

            time.sleep(max(0.5, poll_interval))

    except KeyboardInterrupt:
        print("\nĐã ngắt theo dõi. Nếu Codespace bị dừng, hãy tiếp tục bằng:")
        print(f"    python tts_cli.py --resume {job_id}")
        print("Các đoạn đã lưu trên đĩa sẽ được giữ lại.")
        return 130


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()

    if args.list_jobs:
        return print_jobs()

    if args.poll_interval <= 0:
        parser.error("--poll-interval phải lớn hơn 0.")

    if args.resume and args.input:
        parser.error("Chọn --resume hoặc --input, không dùng cả hai cùng lúc.")

    if not args.resume and not args.input:
        parser.error("Cần cung cấp --input FILE hoặc --resume JOB_ID.")

    manager: JobManager

    if args.resume:
        try:
            manager = JobManager(JOBS_DIR, OUTPUTS_DIR)
            state = manager.get_job(args.resume)
            if state.get("status") in {"failed", "cancelled"}:
                state = manager.retry(args.resume)
                print("Đã đưa tác vụ trở lại hàng đợi; các đoạn MP3 hợp lệ được giữ lại.")
            elif state.get("status") == "completed":
                output = state.get("output_filename")
                print("Tác vụ này đã hoàn thành.")
                if output:
                    print(f"Tệp: {OUTPUTS_DIR / str(output)}")
                return 0
            print(f"Đang tiếp tục tác vụ: {args.resume}")
            return monitor_job(manager, args.resume, args.poll_interval)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Không thể tiếp tục tác vụ: {exc}", file=sys.stderr)
            return 2

    input_path = Path(args.input).expanduser()
    if not input_path.is_file():
        print(f"Không tìm thấy tệp đầu vào: {input_path}", file=sys.stderr)
        print("Trong Codespaces, tải tệp TXT vào workspace rồi truyền đường dẫn sau --input.")
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

    title = args.title or input_path.stem

    try:
        manager = JobManager(JOBS_DIR, OUTPUTS_DIR)
        job = manager.create_job(
            title=title,
            text=text,
            voice=args.voice,
            rate=args.rate,
            chunk_size=args.chunk_size,
        )
    except (ValueError, OSError) as exc:
        print(f"Không thể tạo tác vụ: {exc}", file=sys.stderr)
        return 2

    job_id = str(job["id"])
    print(f"Đã tạo tác vụ cho: {title}")
    print(f"Mã tác vụ: {job_id}")
    print(f"Tổng số đoạn: {job.get('total_chunks', 0)}")
    print("Đang tổng hợp bằng Edge-TTS. Không commit tệp truyện hoặc MP3 lên repository Public.")
    return monitor_job(manager, job_id, args.poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
