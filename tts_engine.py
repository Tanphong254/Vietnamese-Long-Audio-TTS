from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Any

logger = logging.getLogger(__name__)

VOICE_OPTIONS = {
    "vi-VN-NamMinhNeural": "Nam Minh (Nam)",
    "vi-VN-HoaiMyNeural": "Hoài My (Nữ)",
}
RATE_OPTIONS = {
    "0.75": "0.75x",
    "1.0": "1.0x",
    "1.25": "1.25x",
    "1.5": "1.5x",
    "1.75": "1.75x",
}
DEFAULT_CHUNK_SIZE = 2400
MIN_CHUNK_SIZE = 500
MAX_CHUNK_SIZE = 3500
MAX_RETRIES = 3


def rate_to_edge(rate: str) -> str:
    """Convert a UI speed multiplier into Edge-TTS's percentage rate."""
    if rate not in RATE_OPTIONS:
        raise ValueError("Tốc độ đọc không hợp lệ.")
    value = float(rate)
    percent = round((value - 1.0) * 100)
    return f"{percent:+d}%"


def split_text(text: str, max_chars: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    """Split text at natural boundaries without dropping or reordering characters.

    Joining the returned chunks reproduces the input exactly. Paragraph and
    sentence boundaries are preferred; a hard character boundary is the final
    fallback for very long sentences or unbroken text.
    """
    if not isinstance(text, str):
        raise TypeError("Nội dung phải là chuỗi văn bản.")
    if max_chars < MIN_CHUNK_SIZE or max_chars > MAX_CHUNK_SIZE:
        raise ValueError(
            f"Độ dài mỗi đoạn phải nằm trong khoảng {MIN_CHUNK_SIZE}–{MAX_CHUNK_SIZE}."
        )
    if not text.strip():
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)
    min_preferred = int(max_chars * 0.40)
    sentence_end = re.compile(r"[.!?。！？…]+[\"'”’»）)]*\s+")

    while start < length:
        if len(text) - start <= max_chars:
            chunks.append(text[start:])
            break

        hard_end = start + max_chars
        window = text[start:hard_end]
        cut: int | None = None

        # Prefer the last paragraph boundary, keeping the newline characters.
        paragraph_pos = window.rfind("\n\n")
        if paragraph_pos >= min_preferred:
            cut = start + paragraph_pos + 2

        # Then prefer a sentence boundary.
        if cut is None:
            matches = list(sentence_end.finditer(window))
            if matches and matches[-1].end() >= min_preferred:
                cut = start + matches[-1].end()

        # Then a line break, then any whitespace.
        if cut is None:
            line_pos = window.rfind("\n")
            if line_pos >= min_preferred:
                cut = start + line_pos + 1

        if cut is None:
            space_pos = max(window.rfind(" "), window.rfind("\t"))
            if space_pos >= min_preferred:
                cut = start + space_pos + 1

        if cut is None or cut <= start:
            cut = hard_end

        chunks.append(text[start:cut])
        start = cut

    # Do not strip chunk boundaries: source characters and whitespace are retained.
    return [chunk for chunk in chunks if chunk]


def safe_title(value: str, fallback: str = "truyen") -> str:
    value = (value or "").strip()
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", value)
    value = re.sub(r"\s+", "_", value)
    value = value.strip("._ ")[:80]
    return value or fallback


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temp_path, path)


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def get_ffmpeg_executable() -> str:
    """Find the FFmpeg binary installed on PATH or bundled by imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).is_file():
            return bundled
    except (ImportError, RuntimeError, OSError):
        pass
    raise RuntimeError(
        "Không tìm thấy FFmpeg. Hãy cài lại các thư viện trong requirements.txt "
        "(gói imageio-ffmpeg bao gồm FFmpeg) hoặc cài FFmpeg và thêm vào PATH. "
        "Các đoạn audio đã tạo vẫn được giữ lại."
    )


def merge_mp3_segments(segment_paths: list[Path], job_dir: Path, output_path: Path) -> None:
    """Merge segments in order with FFmpeg; preserve originals if merging fails."""
    if not segment_paths:
        raise RuntimeError("Không có đoạn audio nào để ghép.")
    for path in segment_paths:
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"Thiếu đoạn audio hoặc tệp rỗng: {path.name}")

    ffmpeg = get_ffmpeg_executable()
    list_path = job_dir / "ffmpeg_concat_list.txt"
    temp_output = output_path.with_name(output_path.stem + ".partial.mp3")
    lines = []
    for path in segment_paths:
        # Paths are relative to the list file's folder and filenames are generated
        # internally, so paths with spaces/non-ASCII project directories are safe.
        relative = path.relative_to(job_dir).as_posix()
        lines.append(f"file '{relative}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    base_cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_path),
    ]
    try:
        # Stream-copy first: quick and avoids a second lossy encode when compatible.
        copy_cmd = base_cmd + ["-c", "copy", str(temp_output)]
        first = subprocess.run(
            copy_cmd, cwd=str(job_dir), capture_output=True, text=True,
            timeout=4 * 60 * 60, check=False,
        )
        if first.returncode != 0 or not temp_output.is_file() or temp_output.stat().st_size == 0:
            temp_output.unlink(missing_ok=True)
            # If the source chunks differ slightly, normalize by re-encoding.
            encode_cmd = base_cmd + ["-vn", "-c:a", "libmp3lame", "-q:a", "3", str(temp_output)]
            second = subprocess.run(
                encode_cmd, cwd=str(job_dir), capture_output=True, text=True,
                timeout=4 * 60 * 60, check=False,
            )
            if second.returncode != 0 or not temp_output.is_file() or temp_output.stat().st_size == 0:
                detail = (second.stderr or first.stderr or "Không có chi tiết từ FFmpeg")[-1800:]
                raise RuntimeError("FFmpeg không ghép được audio: " + detail)
        os.replace(temp_output, output_path)
    finally:
        list_path.unlink(missing_ok=True)
        temp_output.unlink(missing_ok=True)


async def _synthesize_async(text: str, voice: str, rate: str, output_path: Path) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError(
            "Chưa cài edge-tts. Hãy chạy: python -m pip install -r requirements.txt"
        ) from exc

    communicator = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate_to_edge(rate),
    )
    await communicator.save(str(output_path))


def synthesize_chunk(text: str, voice: str, rate: str, output_path: Path) -> None:
    asyncio.run(_synthesize_async(text, voice, rate, output_path))


class JobManager:
    """Single-worker, disk-persisted job queue suitable for a local desktop app."""

    def __init__(self, jobs_dir: Path, outputs_dir: Path, max_retries: int = MAX_RETRIES):
        self.jobs_dir = Path(jobs_dir)
        self.outputs_dir = Path(outputs_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.queue: Queue[str] = Queue()
        self.lock = threading.RLock()
        self.queued: set[str] = set()
        self.cancel_events: dict[str, threading.Event] = {}
        self._recover_jobs()
        self.worker = threading.Thread(target=self._worker_loop, name="tts-job-worker", daemon=True)
        self.worker.start()

    def _job_dir(self, job_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise ValueError("Mã tác vụ không hợp lệ.")
        return self.jobs_dir / job_id

    def _state_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "status.json"

    def _load(self, job_id: str) -> dict[str, Any]:
        state = read_json(self._state_path(job_id))
        if state is None:
            raise FileNotFoundError("Không tìm thấy tác vụ hoặc dữ liệu tác vụ bị lỗi.")
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_json(self._state_path(state["id"]), state)

    def _recover_jobs(self) -> None:
        for directory in self.jobs_dir.iterdir():
            if not directory.is_dir() or not re.fullmatch(r"[a-f0-9]{32}", directory.name):
                continue
            state = read_json(directory / "status.json")
            if not state:
                continue
            previous_status = state.get("status")
            if previous_status == "cancelling":
                # Respect the user's cancel request if the application closed
                # before the current network request had a chance to finish.
                state["status"] = "cancelled"
                state["cancel_requested"] = False
                state["current_chunk"] = None
                state["updated_at"] = now_iso()
                atomic_write_json(directory / "status.json", state)
            elif previous_status in {"queued", "running", "merging", "interrupted"}:
                state["status"] = "queued"
                state["error"] = None
                state["current_chunk"] = None
                state["updated_at"] = now_iso()
                atomic_write_json(directory / "status.json", state)
                self._enqueue(directory.name)

    def create_job(self, title: str, text: str, voice: str, rate: str, chunk_size: int) -> dict[str, Any]:
        if voice not in VOICE_OPTIONS:
            raise ValueError("Giọng đọc không hợp lệ.")
        rate_to_edge(rate)
        if len(text) > 20_000_000:
            raise ValueError("Văn bản vượt quá giới hạn an toàn 20 triệu ký tự cho một tác vụ.")
        chunks = split_text(text, chunk_size)
        if not chunks:
            raise ValueError("Văn bản đang trống.")

        job_id = uuid.uuid4().hex
        job_dir = self._job_dir(job_id)
        (job_dir / "segments").mkdir(parents=True, exist_ok=True)
        (job_dir / "source.txt").write_text(text, encoding="utf-8")

        timestamp = now_iso()
        state: dict[str, Any] = {
            "id": job_id,
            "title": (title or "").strip()[:120] or "Truyện không tên",
            "safe_title": safe_title(title),
            "status": "queued",
            "voice": voice,
            "voice_label": VOICE_OPTIONS[voice],
            "rate": rate,
            "rate_label": RATE_OPTIONS[rate],
            "chunk_size": chunk_size,
            "total_chars": len(text),
            "total_chunks": len(chunks),
            "segments": [
                {"index": i + 1, "status": "pending", "attempts": 0, "error": None}
                for i in range(len(chunks))
            ],
            "completed_chunks": 0,
            "current_chunk": None,
            "output_filename": None,
            "error": None,
            "cancel_requested": False,
            "created_at": timestamp,
            "updated_at": timestamp,
            "completed_at": None,
        }
        self._save(state)
        self._enqueue(job_id)
        return self.public_state(state)

    def _enqueue(self, job_id: str) -> None:
        with self.lock:
            if job_id in self.queued:
                return
            self.queued.add(job_id)
            self.cancel_events[job_id] = threading.Event()
            self.queue.put(job_id)

    def _worker_loop(self) -> None:
        while True:
            job_id = self.queue.get()
            with self.lock:
                self.queued.discard(job_id)
                cancel_event = self.cancel_events.setdefault(job_id, threading.Event())
            try:
                self._process_job(job_id, cancel_event)
            except Exception as exc:  # Keep the worker alive if one job unexpectedly breaks.
                logger.exception("Unexpected error while processing TTS job %s", job_id)
                try:
                    state = self._load(job_id)
                    state["status"] = "failed"
                    state["error"] = str(exc)[:1800]
                    state["updated_at"] = now_iso()
                    self._save(state)
                except Exception:
                    logger.exception("Could not persist failure for job %s", job_id)
            finally:
                with self.lock:
                    self.cancel_events.pop(job_id, None)
                self.queue.task_done()

    def _process_job(self, job_id: str, cancel_event: threading.Event) -> None:
        state = self._load(job_id)
        if state.get("status") == "completed":
            return
        job_dir = self._job_dir(job_id)
        source_path = job_dir / "source.txt"
        if not source_path.is_file():
            self._fail(state, "Không tìm thấy văn bản nguồn để tiếp tục tác vụ.")
            return
        text = source_path.read_text(encoding="utf-8")
        chunks = split_text(text, int(state["chunk_size"]))
        if len(chunks) != int(state["total_chunks"]):
            self._fail(state, "Số đoạn văn bản nguồn không khớp dữ liệu tác vụ. Không tự động ghi đè audio.")
            return

        state["status"] = "running"
        state["error"] = None
        state["cancel_requested"] = False
        state["updated_at"] = now_iso()
        segment_dir = job_dir / "segments"
        segment_dir.mkdir(parents=True, exist_ok=True)

        # Scan persisted files once at startup/resume (O(number of segments)).
        # Avoid re-counting/stat-ing all previous segments after every chunk: a
        # multi-hour book may have thousands of chunks.
        valid_segment_indices: set[int] = set()
        for index, item in enumerate(state["segments"], start=1):
            existing_path = segment_dir / f"{index:06d}.mp3"
            if existing_path.is_file() and existing_path.stat().st_size > 0:
                item["status"] = "completed"
                item["error"] = None
                valid_segment_indices.add(index)
            elif item.get("status") == "completed":
                # A status entry without a valid audio file must be recreated.
                item["status"] = "pending"
        completed_count = len(valid_segment_indices)
        state["completed_chunks"] = completed_count
        self._save(state)

        for index, chunk in enumerate(chunks, start=1):
            if cancel_event.is_set():
                self._mark_cancelled(job_id)
                return

            segment_path = segment_dir / f"{index:06d}.mp3"
            segment = state["segments"][index - 1]
            # Recover a completed segment even if the app stopped before writing status.json.
            if index in valid_segment_indices:
                continue

            segment["status"] = "running"
            segment["error"] = None
            state["current_chunk"] = index
            state["updated_at"] = now_iso()
            self._save(state)

            last_error: str | None = None
            for attempt in range(1, self.max_retries + 1):
                if cancel_event.is_set():
                    self._mark_cancelled(job_id)
                    return
                segment["attempts"] = attempt
                temp_path = segment_dir / f"{index:06d}.partial.mp3"
                temp_path.unlink(missing_ok=True)
                try:
                    synthesize_chunk(chunk, state["voice"], state["rate"], temp_path)
                    if not temp_path.is_file() or temp_path.stat().st_size <= 0:
                        raise RuntimeError("Edge-TTS trả về tệp audio rỗng.")
                    os.replace(temp_path, segment_path)
                    last_error = None
                    break
                except Exception as exc:
                    last_error = str(exc)[:1600]
                    temp_path.unlink(missing_ok=True)
                    logger.warning(
                        "TTS segment %s/%s failed on attempt %s/%s: %s",
                        index, len(chunks), attempt, self.max_retries, last_error,
                    )
                    if attempt < self.max_retries and not cancel_event.is_set():
                        cancel_event.wait(min(2 ** attempt, 12))

            if last_error is not None:
                segment["status"] = "failed"
                segment["error"] = last_error
                state["status"] = "failed"
                state["error"] = f"Đoạn {index}/{len(chunks)} thất bại sau {self.max_retries} lần thử."
                state["current_chunk"] = index
                state["completed_chunks"] = completed_count
                state["updated_at"] = now_iso()
                self._save(state)
                return

            segment["status"] = "completed"
            segment["error"] = None
            completed_count += 1
            valid_segment_indices.add(index)
            state["completed_chunks"] = completed_count
            state["updated_at"] = now_iso()
            self._save(state)

        if cancel_event.is_set():
            self._mark_cancelled(job_id)
            return

        state["status"] = "merging"
        state["current_chunk"] = None
        state["completed_chunks"] = len(chunks)
        state["updated_at"] = now_iso()
        self._save(state)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{state['safe_title']}_{stamp}_{job_id[:8]}.mp3"
        output_path = self.outputs_dir / output_name
        try:
            merge_mp3_segments(
                [segment_dir / f"{i:06d}.mp3" for i in range(1, len(chunks) + 1)],
                job_dir,
                output_path,
            )
        except Exception as exc:
            state["status"] = "failed"
            state["error"] = str(exc)[:2000]
            state["updated_at"] = now_iso()
            self._save(state)
            return

        state["status"] = "completed"
        state["output_filename"] = output_name
        state["error"] = None
        state["current_chunk"] = None
        state["completed_chunks"] = len(chunks)
        state["completed_at"] = now_iso()
        state["updated_at"] = now_iso()
        self._save(state)

    def _fail(self, state: dict[str, Any], message: str) -> None:
        state["status"] = "failed"
        state["error"] = message
        state["updated_at"] = now_iso()
        self._save(state)

    def _mark_cancelled(self, job_id: str) -> None:
        try:
            state = self._load(job_id)
            state["status"] = "cancelled"
            state["cancel_requested"] = False
            state["current_chunk"] = None
            state["error"] = None
            state["updated_at"] = now_iso()
            self._save(state)
        except (OSError, ValueError):
            logger.exception("Could not mark TTS job as cancelled")

    def get_job(self, job_id: str) -> dict[str, Any]:
        # Keep polling inexpensive: the worker persists progress after every
        # generated segment, so the UI does not stat thousands of files every
        # couple of seconds. The worker reconciles on-disk segments on resume.
        state = self._load(job_id)
        return self.public_state(state)

    @staticmethod
    def public_state(state: dict[str, Any]) -> dict[str, Any]:
        state = dict(state)
        total = int(state.get("total_chunks", 0))
        done = int(state.get("completed_chunks", 0))
        status = state.get("status")
        if status == "completed":
            percent = 100
        elif status == "merging":
            percent = 98
        else:
            percent = int((done / total) * 95) if total else 0
        all_segments = list(state.get("segments", []))
        segment_count = len(all_segments)
        # Very long stories may contain thousands of chunks. Return a useful
        # sample instead of a huge response on every progress poll: beginning,
        # end, current position and any failed chunks.
        if segment_count > 120:
            chosen: set[int] = set(range(min(20, segment_count)))
            chosen.update(range(max(0, segment_count - 20), segment_count))
            current = state.get("current_chunk")
            if isinstance(current, int) and current > 0:
                center = current - 1
                chosen.update(range(max(0, center - 30), min(segment_count, center + 31)))
            chosen.update(
                index for index, segment in enumerate(all_segments)
                if segment.get("status") == "failed"
            )
            state["segments"] = [all_segments[index] for index in sorted(chosen)]
            state["segments_truncated"] = len(chosen) < segment_count
        else:
            state["segments"] = all_segments
            state["segments_truncated"] = False
        state["segments_total_count"] = segment_count
        state["segments_displayed_count"] = len(state["segments"])
        state["percent"] = percent
        return state

    def list_jobs(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for directory in self.jobs_dir.iterdir():
            if not directory.is_dir() or not re.fullmatch(r"[a-f0-9]{32}", directory.name):
                continue
            state = read_json(directory / "status.json")
            if state:
                items.append(state)
        items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return [self.public_state(item) for item in items[:100]]

    def cancel(self, job_id: str) -> dict[str, Any]:
        state = self._load(job_id)
        if state.get("status") == "merging":
            raise ValueError("Tác vụ đang ghép MP3; không thể hủy ở giai đoạn này. Hãy để quá trình ghép hoàn tất.")
        if state.get("status") in {"completed", "failed", "cancelled"}:
            raise ValueError("Tác vụ đã kết thúc; không thể hủy ở trạng thái hiện tại.")
        with self.lock:
            event = self.cancel_events.get(job_id)
            if event is None:
                event = threading.Event()
                self.cancel_events[job_id] = event
            event.set()
        state["status"] = "cancelling"
        state["cancel_requested"] = True
        state["updated_at"] = now_iso()
        self._save(state)
        return self.public_state(state)

    def retry(self, job_id: str) -> dict[str, Any]:
        state = self._load(job_id)
        if state.get("status") not in {"failed", "cancelled"}:
            raise ValueError("Chỉ có thể thử lại tác vụ đã lỗi hoặc đã hủy.")
        segment_dir = self._job_dir(job_id) / "segments"
        for item in state.get("segments", []):
            index = int(item["index"])
            path = segment_dir / f"{index:06d}.mp3"
            if path.is_file() and path.stat().st_size > 0:
                item["status"] = "completed"
                item["error"] = None
            else:
                item["status"] = "pending"
                item["error"] = None
        state["completed_chunks"] = sum(
            1 for item in state["segments"] if item.get("status") == "completed"
        )
        state["status"] = "queued"
        state["error"] = None
        state["cancel_requested"] = False
        state["updated_at"] = now_iso()
        self._save(state)
        self._enqueue(job_id)
        return self.public_state(state)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
