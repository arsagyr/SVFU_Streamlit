import os
import tempfile
from functools import lru_cache
from pathlib import Path

MODEL_SIZE = os.environ.get("WHISPER_MODEL", "small")
LANGUAGE = os.environ.get("WHISPER_LANGUAGE") or None


@lru_cache(maxsize=1)
def get_model():
    from faster_whisper import WhisperModel

    return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe(audio_bytes: bytes, suffix: str = ".wav") -> str:
    """Распознаёт аудио (bytes) в текст."""
    model = get_model()
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(audio_bytes)
        tmp.close()
        segments, _info = model.transcribe(
            tmp.name,
            language=LANGUAGE,
            vad_filter=True,
            beam_size=5,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        Path(tmp.name).unlink(missing_ok=True)
