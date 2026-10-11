"""Файловое хранилище без БД.

Структура каталога данных (по умолчанию ``./data``, переопределяется
переменной окружения ``APP_DATA_DIR``)::

    data/
    ├── texts/   # тексты в формате Markdown (папка с текстами)
    ├── notes/   # заметки (метаданные в JSON, папка с записями заметок)
    └── audio/   # аудиозаписи голосовых заметок

Тексты хранят заголовок и дату создания в YAML-подобном front matter.
Заметки — отдельные JSON-файлы, связанные с текстом и/или маркером.
"""

import json
import os
import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("APP_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
TEXTS_DIR = DATA_DIR / "texts"
NOTES_DIR = DATA_DIR / "notes"
AUDIO_DIR = DATA_DIR / "audio"

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_ALL = object()


SAMPLE_TEXT = """# Добро пожаловать 👋

Это пример текста. Ниже стоит маркер {{m:1}} — жёлтая метка в интерфейсе.

К маркеру можно привязать **голосовую** или **текстовую** заметку:
нажмите на метку, продиктуйте заметку и сохраните — речь распознается в текст.

Добавляйте свои маркеры кнопкой «➕ Добавить маркер» или вручную так: {{m:2}}.
"""


def init_storage() -> None:
    for directory in (TEXTS_DIR, NOTES_DIR, AUDIO_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def seed_sample() -> None:
    """Один раз создаёт пример текста, чтобы папка с текстами не была пустой."""
    flag = DATA_DIR / ".initialized"
    if flag.exists():
        return
    flag.write_text("ok", encoding="utf-8")
    if not list(TEXTS_DIR.glob("*.md")):
        create_text("Пример текста", SAMPLE_TEXT)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(title: str) -> str:
    """Порождает читаемый ASCII-слаг из заголовка (транслит кириллицы)."""
    text = (title or "").strip().lower()
    text = "".join(_TRANSLIT.get(ch, ch) for ch in text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:60] or "text"


def _unique_slug(title: str) -> str:
    base = slugify(title)
    slug = base
    n = 2
    while (TEXTS_DIR / f"{slug}.md").exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


# --- Тексты -----------------------------------------------------------------

def _parse_text(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    match = _FRONT_MATTER_RE.match(raw)
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
        body = raw[match.end():]
    else:
        body = raw
    stat = path.stat()
    return {
        "slug": path.stem,
        "title": meta.get("title") or path.stem,
        "created_at": meta.get("created_at") or datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "content": body.rstrip("\n"),
    }


def list_texts() -> list[dict]:
    texts = [_parse_text(p) for p in TEXTS_DIR.glob("*.md")]
    texts.sort(key=lambda t: (t["created_at"], t["slug"]), reverse=True)
    for text in texts:
        text["notes_count"] = len(list_notes(text_slug=text["slug"]))
    return texts


def get_text(slug: str) -> dict | None:
    path = TEXTS_DIR / f"{slug}.md"
    return _parse_text(path) if path.exists() else None


def create_text(title: str, content: str) -> str:
    slug = _unique_slug(title)
    _write_text(slug, title, content, _now())
    return slug


def update_text(slug: str, content: str, title: str | None = None) -> None:
    existing = get_text(slug)
    if existing is None:
        raise FileNotFoundError(slug)
    _write_text(slug, title or existing["title"], content, existing["created_at"])


def _write_text(slug: str, title: str, content: str, created_at: str) -> None:
    body = content.strip("\n")
    raw = f"---\ntitle: {title}\ncreated_at: {created_at}\n---\n\n{body}\n"
    (TEXTS_DIR / f"{slug}.md").write_text(raw, encoding="utf-8")


def delete_text(slug: str, delete_notes: bool = True) -> None:
    if delete_notes:
        for note in list_notes(text_slug=slug):
            delete_note(note["id"])
    (TEXTS_DIR / f"{slug}.md").unlink(missing_ok=True)


# --- Заметки ----------------------------------------------------------------

def _note_path(note_id: str) -> Path:
    return NOTES_DIR / f"{note_id}.json"


def _load_note(path: Path) -> dict | None:
    try:
        note = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    note.setdefault("id", path.stem)
    return note


def list_notes(text_slug=_ALL, marker_id=_ALL) -> list[dict]:
    notes: list[dict] = []
    for path in NOTES_DIR.glob("*.json"):
        note = _load_note(path)
        if note is None:
            continue
        if text_slug is not _ALL and note.get("text_slug") != text_slug:
            continue
        if marker_id is not _ALL and note.get("marker_id") != marker_id:
            continue
        notes.append(note)
    notes.sort(key=lambda n: (n.get("created_at", ""), n.get("id", "")), reverse=True)
    for note in notes:
        text = get_text(note["text_slug"]) if note.get("text_slug") else None
        note["text_title"] = text["title"] if text else None
    return notes


def get_note(note_id: str) -> dict | None:
    path = _note_path(note_id)
    if not path.exists():
        return None
    note = _load_note(path)
    if note is None:
        return None
    text = get_text(note["text_slug"]) if note.get("text_slug") else None
    note["text_title"] = text["title"] if text else None
    return note


def count_notes_by_marker(text_slug: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for note in list_notes(text_slug=text_slug):
        mid = note.get("marker_id")
        if mid:
            counts[mid] = counts.get(mid, 0) + 1
    return counts


def add_note(content: str, text_slug: str | None = None, marker_id: str | None = None,
             audio_bytes: bytes | None = None, audio_ext: str = "wav") -> str:
    content = (content or "").strip()
    if not content:
        raise ValueError("Текст заметки пуст.")
    note_id = uuid.uuid4().hex[:12]
    note = {
        "id": note_id,
        "content": content,
        "text_slug": text_slug,
        "marker_id": marker_id,
        "audio": save_audio(audio_bytes, audio_ext) if audio_bytes else None,
        "created_at": _now(),
    }
    _note_path(note_id).write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")
    return note_id


def update_note(note_id: str, content: str, text_slug: str | None = None,
                marker_id: str | None = None) -> None:
    note = get_note(note_id)
    if note is None:
        raise FileNotFoundError(note_id)
    note["content"] = (content or "").strip()
    note["text_slug"] = text_slug
    note["marker_id"] = marker_id
    note.pop("text_title", None)
    _note_path(note_id).write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_note(note_id: str) -> str | None:
    path = _note_path(note_id)
    note = _load_note(path) if path.exists() else None
    path.unlink(missing_ok=True)
    if note:
        delete_audio(note.get("audio"))
        return note.get("audio")
    return None


def stats() -> dict:
    notes = list_notes()
    voiced = sum(1 for n in notes if n.get("audio"))
    return {"texts": len(list(TEXTS_DIR.glob("*.md"))), "notes": len(notes), "voiced": voiced}


# --- Аудио ------------------------------------------------------------------

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
