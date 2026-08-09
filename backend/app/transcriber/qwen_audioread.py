from __future__ import annotations

import mimetypes
import os
import re
import time
from pathlib import Path
from typing import Any

import ffmpeg
import requests

from app.decorators.timeit import timeit
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.transcriber.base import Transcriber
from app.utils.logger import get_logger


logger = get_logger(__name__)

_TIMESTAMP = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:\.\d{1,3})?"
_TIMESTAMP_RE = re.compile(
    rf"(?P<start>{_TIMESTAMP})(?:\s*(?:-->|-|~|至|–|—)\s*(?P<end>{_TIMESTAMP}))?"
)


def _timestamp_seconds(value: str) -> float:
    parts = [float(part) for part in value.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError(f"Unsupported timestamp: {value}")


def _clean_markdown_line(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^\s*(?:#{1,6}|>|[-+*]|\d+[.)])\s*", "", text)
    text = re.sub(r"!\[[^]]*]\([^)]*\)", "", text)
    text = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip(" -|：:")


def _fallback_segments(markdown: str, duration: float) -> list[TranscriptSegment]:
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", markdown):
        lines = [_clean_markdown_line(line) for line in block.splitlines()]
        text = " ".join(line for line in lines if line and line != "---").strip()
        if text:
            paragraphs.append(text)

    if not paragraphs:
        raise RuntimeError("AudioRead returned empty Markdown")

    total_duration = duration if duration > 0 else max(30.0, len(paragraphs) * 30.0)
    weights = [max(1, len(text)) for text in paragraphs]
    total_weight = sum(weights)
    cursor = 0.0
    segments: list[TranscriptSegment] = []
    for index, (text, weight) in enumerate(zip(paragraphs, weights)):
        end = total_duration if index == len(paragraphs) - 1 else cursor + total_duration * weight / total_weight
        segments.append(TranscriptSegment(start=cursor, end=max(cursor, end), text=text))
        cursor = end
    return segments


def parse_audioread_markdown(markdown: str, duration: float = 0.0) -> tuple[list[TranscriptSegment], str]:
    pending: dict[str, Any] | None = None
    parsed: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal pending
        if pending is None:
            return
        text = " ".join(pending["lines"]).strip()
        if text:
            parsed.append({**pending, "text": text})
        pending = None

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line or line == "---":
            continue
        match = _TIMESTAMP_RE.search(line)
        if match:
            flush()
            remainder = _clean_markdown_line(line[match.end() :])
            pending = {
                "start": _timestamp_seconds(match.group("start")),
                "end": _timestamp_seconds(match.group("end")) if match.group("end") else None,
                "lines": [remainder] if remainder else [],
            }
        elif pending is not None:
            cleaned = _clean_markdown_line(line)
            if cleaned:
                pending["lines"].append(cleaned)
    flush()

    if not parsed:
        return _fallback_segments(markdown, duration), "paragraph-fallback"

    segments: list[TranscriptSegment] = []
    for index, item in enumerate(parsed):
        start = float(item["start"])
        explicit_end = item["end"]
        next_start = float(parsed[index + 1]["start"]) if index + 1 < len(parsed) else None
        if explicit_end is not None and float(explicit_end) >= start:
            end = float(explicit_end)
        elif next_start is not None and next_start >= start:
            end = next_start
        elif duration > start:
            end = duration
        else:
            end = start + 30.0
        segments.append(TranscriptSegment(start=start, end=end, text=item["text"]))
    return segments, "timestamp"


def _probe_duration(file_path: str) -> float:
    try:
        return float(ffmpeg.probe(file_path)["format"]["duration"])
    except Exception:
        return 0.0


class QwenAudioReadTranscriber(Transcriber):
    def __init__(self, session: requests.Session | None = None):
        self.base_url = os.getenv("QWEN_AUDIOREAD_BASE_URL", "http://qwen-audioread-api:8000").rstrip("/")
        self.api_key = os.getenv("QWEN_AUDIOREAD_API_KEY", "").strip()
        self.poll_interval = max(5, int(os.getenv("QWEN_AUDIOREAD_POLL_INTERVAL_SECONDS", "15")))
        self.poll_timeout = max(60, int(os.getenv("QWEN_AUDIOREAD_POLL_TIMEOUT_SECONDS", "1800")))
        self.upload_timeout = max(60, int(os.getenv("QWEN_AUDIOREAD_UPLOAD_TIMEOUT_SECONDS", "1800")))
        self.session = session or requests.Session()
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    @staticmethod
    def _response_json(response: requests.Response, label: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception as error:
            raise RuntimeError(f"AudioRead {label} returned invalid JSON: HTTP {response.status_code}") from error
        if not response.ok:
            detail = payload.get("detail") if isinstance(payload, dict) else payload
            raise RuntimeError(f"AudioRead {label} failed: HTTP {response.status_code} detail={detail}")
        if not isinstance(payload, dict):
            raise RuntimeError(f"AudioRead {label} returned an invalid payload")
        return payload

    @timeit
    def transcript(self, file_path: str) -> TranscriptResult:
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: {path}")
        if not self.api_key:
            raise RuntimeError("QWEN_AUDIOREAD_API_KEY is not configured")

        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        logger.info("提交 AudioRead 转写任务: %s", path.name)
        with path.open("rb") as source:
            response = self.session.post(
                f"{self.base_url}/api/v1/transcriptions/async",
                files={"file": (path.name, source, mime_type)},
                data={"format": "md", "delete_remote": "true"},
                timeout=(10, self.upload_timeout),
            )
        job = self._response_json(response, "submit")
        job_id = str(job.get("job_id") or "").strip()
        if not job_id:
            raise RuntimeError(f"AudioRead submit response missing job_id: {job}")

        deadline = time.monotonic() + self.poll_timeout
        while time.monotonic() < deadline:
            response = self.session.get(f"{self.base_url}/api/v1/jobs/{job_id}", timeout=(10, 30))
            job = self._response_json(response, "poll")
            status = str(job.get("status") or "")
            if status == "failed":
                error = job.get("error") or {}
                raise RuntimeError(
                    f"AudioRead transcription failed: code={error.get('code')} message={error.get('message')}"
                )
            if status == "succeeded":
                break
            time.sleep(self.poll_interval)
        else:
            raise RuntimeError(f"AudioRead polling timed out after {self.poll_timeout}s: job_id={job_id}")

        file_response = self.session.get(f"{self.base_url}/api/v1/jobs/{job_id}/file", timeout=(10, 120))
        if not file_response.ok:
            raise RuntimeError(f"AudioRead download failed: HTTP {file_response.status_code}")
        markdown = file_response.text
        segments, parser_mode = parse_audioread_markdown(markdown, _probe_duration(str(path)))
        full_text = " ".join(segment.text for segment in segments).strip()
        logger.info("AudioRead 转写完成: job_id=%s, segments=%s, parser=%s", job_id, len(segments), parser_mode)
        return TranscriptResult(
            language="zh",
            full_text=full_text,
            segments=segments,
            raw={
                "provider": "qwen-audioread",
                "job_id": job_id,
                "markdown_filename": job.get("markdown_filename"),
                "parser_mode": parser_mode,
            },
        )
