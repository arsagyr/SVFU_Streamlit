import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("APP_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DB_PATH = DATA_DIR / "notes.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER,
    content TEXT NOT NULL,
    audio_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE SET NULL
);
"""


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.executescript(SCHEMA)


@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys = ON")
        yield con
        con.commit()
    finally:
        con.close()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def list_documents() -> list[dict]:
    with connect() as con:
        rows = con.execute(
            """
            SELECT d.*, COUNT(n.id) AS notes_count
            FROM documents d
            LEFT JOIN notes n ON n.document_id = d.id
            GROUP BY d.id
            ORDER BY d.created_at DESC, d.id DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_document(doc_id: int) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return dict(row) if row else None


def add_document(title: str, content: str) -> int:
    with connect() as con:
        cur = con.execute(
            "INSERT INTO documents (title, content, created_at) VALUES (?, ?, ?)",
            (title.strip(), content, _now()),
        )
        return cur.lastrowid


def delete_document(doc_id: int) -> None:
    with connect() as con:
        con.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


def list_notes(document_id: int | None = None) -> list[dict]:
    query = """
        SELECT n.*, d.title AS document_title
        FROM notes n
        LEFT JOIN documents d ON d.id = n.document_id
    """
    params: tuple = ()
    if document_id is not None:
        query += " WHERE n.document_id = ?"
        params = (document_id,)
    query += " ORDER BY n.created_at DESC, n.id DESC"
    with connect() as con:
        rows = con.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_note(note_id: int) -> dict | None:
    with connect() as con:
        row = con.execute(
            """
            SELECT n.*, d.title AS document_title
            FROM notes n
            LEFT JOIN documents d ON d.id = n.document_id
            WHERE n.id = ?
            """,
            (note_id,),
        ).fetchone()
    return dict(row) if row else None


def add_note(content: str, document_id: int | None = None, audio_path: str | None = None) -> int:
    with connect() as con:
        cur = con.execute(
            "INSERT INTO notes (document_id, content, audio_path, created_at) VALUES (?, ?, ?, ?)",
            (document_id, content, audio_path, _now()),
        )
        return cur.lastrowid


def update_note(note_id: int, content: str, document_id: int | None = None) -> None:
    with connect() as con:
        con.execute(
            "UPDATE notes SET content = ?, document_id = ? WHERE id = ?",
            (content, document_id, note_id),
        )


def delete_note(note_id: int) -> str | None:
    with connect() as con:
        row = con.execute("SELECT audio_path FROM notes WHERE id = ?", (note_id,)).fetchone()
        con.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return row["audio_path"] if row else None


def stats() -> dict:
    with connect() as con:
        docs = con.execute("SELECT COUNT(*) AS c FROM documents").fetchone()["c"]
        notes = con.execute("SELECT COUNT(*) AS c FROM notes").fetchone()["c"]
        voiced = con.execute(
            "SELECT COUNT(*) AS c FROM notes WHERE audio_path IS NOT NULL"
        ).fetchone()["c"]
    return {"documents": docs, "notes": notes, "voiced": voiced}
