import uuid
from pathlib import Path

from core.db import DATA_DIR

AUDIO_DIR = DATA_DIR / "audio"


def save_audio(data: bytes, ext: str = "wav") -> str:
    """Сохраняет аудио и возвращает путь относительно DATA_DIR."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext.lstrip('.').lower() or 'wav'}"
    (AUDIO_DIR / name).write_bytes(data)
    return f"audio/{name}"


def audio_abs_path(rel_path: str) -> Path:
    return DATA_DIR / rel_path


def delete_audio(rel_path: str | None) -> None:
    if rel_path:
        audio_abs_path(rel_path).unlink(missing_ok=True)
