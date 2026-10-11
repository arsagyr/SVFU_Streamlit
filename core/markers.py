"""Инлайн-маркеры в тексте.

Маркер — это якорь вида ``{{m:ID}}``, который пользователь ставит прямо в
Markdown-тексте. К каждому маркеру можно привязать текстовые и голосовые
заметки. В интерфейсе маркер превращается в кликабельную метку-ссылку.
"""

import re

MARKER_RE = re.compile(r"\{\{\s*m:([A-Za-z0-9_-]+)\s*\}\}")


def find_markers(content: str) -> list[str]:
    """Возвращает идентификаторы маркеров в порядке появления (без повторов)."""
    seen: list[str] = []
    for mid in MARKER_RE.findall(content or ""):
        if mid not in seen:
            seen.append(mid)
    return seen


def new_marker_id(content: str) -> str:
    """Подбирает свободный числовой идентификатор (1, 2, …)."""
    used = set(find_markers(content))
    n = 1
    while str(n) in used:
        n += 1
    return str(n)


def insert_marker(content: str, line: int, marker_id: str | None = None) -> tuple[str, str]:
    """Вставляет маркер после строки ``line`` (1-based).

    Возвращает ``(новый_текст, id_маркера)``.
    """
    marker_id = marker_id or new_marker_id(content)
    lines = (content or "").splitlines()
    line = max(0, min(line, len(lines)))
    lines.insert(line, f"{{{{m:{marker_id}}}}}")
    return "\n".join(lines), marker_id


def remove_marker(content: str, marker_id: str) -> str:
    """Удаляет все вхождения маркера из текста."""
    return MARKER_RE.sub(lambda m: "" if m.group(1) == marker_id else m.group(0), content or "")


def render(content: str, slug: str, counts: dict[str, int] | None = None,
           active: str | None = None) -> str:
    """Заменяет маркеры на кликабельные HTML-метки для ``st.markdown``.

    Ссылка несёт параметры ``doc`` и ``marker`` — по клику открывается панель
    заметок нужного маркера (см. обработку ``st.query_params`` в приложении).
    """
    counts = counts or {}

    def replace(match: re.Match) -> str:
        mid = match.group(1)
        n = counts.get(mid, 0)
        cls = "svfu-marker svfu-marker-active" if mid == active else "svfu-marker"
        label = str(n) if n else "+"
        plural = "заметок"
        return (
            f'<a class="{cls}" href="?doc={slug}&marker={mid}" target="_self" '
            f'title="Маркер {mid}: {n} {plural}">{label}</a>'
        )

    return MARKER_RE.sub(replace, content or "")


def strip(content: str) -> str:
    """Убирает маркеры из текста (для статистики и предпросмотра)."""
    return MARKER_RE.sub("", content or "").strip()
