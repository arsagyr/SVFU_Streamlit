import os

import streamlit as st

from core import markers, storage

st.set_page_config(
    page_title="Голосовые заметки",
    page_icon="🎙",
    layout="wide",
    initial_sidebar_state="collapsed",
)

storage.init_storage()
storage.seed_sample()

NO_TEXT = "— без привязки —"
NO_MARKER = "— без маркера —"
AUDIO_TYPES = ["wav", "mp3", "m4a", "ogg", "flac", "webm"]

MARKER_CSS = """
<style>
.svfu-marker {
    display: inline-block;
    min-width: 1.45em;
    padding: 0 .4em;
    margin: 0 .2em;
    border-radius: .75em;
    background: #ffd766;
    color: #4a3400 !important;
    font-size: .78em;
    font-weight: 700;
    text-align: center;
    text-decoration: none !important;
    line-height: 1.6;
    vertical-align: middle;
}
.svfu-marker:hover { background: #ffbf2e; }
.svfu-marker-active { background: #ff7a45; color: #ffffff !important; }
</style>
"""


def set_query(**params: str | None) -> None:
    """Синхронизирует параметры URL (без перезапуска скрипта)."""
    for key, value in params.items():
        if value is None:
            if key in st.query_params:
                del st.query_params[key]
        else:
            st.query_params[key] = value


def qp(name: str) -> str | None:
    value = st.query_params.get(name)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def text_label_map() -> dict[str, str]:
    return {f"{t['title']}  ·  заметок: {t['notes_count']}": t["slug"] for t in storage.list_texts()}


def marker_options(slug: str | None) -> list[str]:
    if not slug:
        return []
    doc = storage.get_text(slug)
    return markers.find_markers(doc["content"]) if doc else []


def render_note(note: dict, key_prefix: str) -> None:
    parts = []
    if note.get("marker_id"):
        parts.append(f"🔖 {note['marker_id']}")
    if note.get("text_title"):
        parts.append(f"«{note['text_title']}»")
    tag = " · ".join(parts) if parts else "свободная заметка"

    with st.container(border=True):
        cols = st.columns([4, 1, 1])
        with cols[0]:
            st.caption(f"#{note['id']} · {note['created_at']} · {tag}")
            st.markdown(note["content"])
            if note.get("audio"):
                st.audio(str(storage.audio_abs_path(note["audio"])))
        with cols[1]:
            if st.button("Изменить", key=f"{key_prefix}edit_{note['id']}", use_container_width=True):
                st.session_state["editing_note"] = note["id"]
                st.rerun()
        with cols[2]:
            if st.button("Удалить", key=f"{key_prefix}del_{note['id']}", use_container_width=True):
                storage.delete_note(note["id"])
                st.rerun()

    if st.session_state.get("editing_note") == note["id"]:
        _render_note_edit(note, key_prefix)


def _render_note_edit(note: dict, key_prefix: str) -> None:
    labels = text_label_map()
    options = [NO_TEXT] + list(labels)
    current = NO_TEXT
    for label, slug in labels.items():
        if slug == note.get("text_slug"):
            current = label

    with st.form(f"{key_prefix}edit_form_{note['id']}", border=True):
        new_text = st.text_area("Текст заметки", value=note["content"], height=150)
        new_label = st.selectbox("Текст", options, index=options.index(current))
        new_slug = labels.get(new_label)
        marker_opts = [NO_MARKER] + marker_options(new_slug)
        cur_marker = note.get("marker_id") or NO_MARKER
        idx = marker_opts.index(cur_marker) if cur_marker in marker_opts else 0
        new_marker = st.selectbox("Маркер", marker_opts, index=idx)

        c1, c2, _ = st.columns([1, 1, 3])
        submitted = c1.form_submit_button("Сохранить", use_container_width=True)
        cancelled = c2.form_submit_button("Отмена", use_container_width=True)
        if submitted:
            marker_id = new_marker if new_marker != NO_MARKER else None
            storage.update_note(note["id"], new_text, text_slug=new_slug, marker_id=marker_id)
            st.session_state.pop("editing_note", None)
            st.rerun()
        if cancelled:
            st.session_state.pop("editing_note", None)
            st.rerun()


def audio_note_section(slug: str | None, marker_id: str | None, key_prefix: str) -> None:
    """Запись/загрузка аудио, распознавание речи и сохранение заметки."""
    st.markdown("**🎙 Голосовая заметка**")
    mode = st.radio(
        "Источник звука",
        ["🎙 Микрофон", "📁 Файл"],
        horizontal=True,
        key=f"{key_prefix}mode",
    )

    audio_bytes: bytes | None = None
    audio_ext = "wav"
    if mode == "🎙 Микрофон":
        recorded = st.audio_input("Нажмите, чтобы записать", sample_rate=16000, key=f"{key_prefix}mic")
        if recorded is not None:
            audio_bytes = recorded.getvalue()
            st.audio(audio_bytes, format="audio/wav")
    else:
        uploaded = st.file_uploader("Аудиофайл", type=AUDIO_TYPES, key=f"{key_prefix}file")
        if uploaded is not None:
            audio_bytes = uploaded.getvalue()
            audio_ext = os.path.splitext(uploaded.name)[1].lstrip(".") or "wav"
            st.audio(audio_bytes)

    text_key = f"{key_prefix}recognized"
    if st.button("🔍 Распознать", key=f"{key_prefix}stt", disabled=audio_bytes is None):
        with st.spinner("Распознаю речь… (первый запуск модели может занять время)"):
            try:
                from core.stt import transcribe

                result = transcribe(audio_bytes, suffix=f".{audio_ext}")
            except Exception as exc:
                st.error(f"Ошибка распознавания: {exc}")
            else:
                if not result:
                    st.warning("Речь не обнаружена в записи.")
                else:
                    st.session_state[text_key] = result
                    st.session_state[f"{key_prefix}audio"] = audio_bytes
                    st.session_state[f"{key_prefix}ext"] = audio_ext

    if st.session_state.get(text_key):
        edited = st.text_area(
            "Распознанный текст",
            value=st.session_state[text_key],
            height=140,
            key=f"{key_prefix}edit",
        )
        if st.button("💾 Сохранить заметку", key=f"{key_prefix}save", type="primary"):
            try:
                note_id = storage.add_note(
                    edited,
                    text_slug=slug,
                    marker_id=marker_id,
                    audio_bytes=st.session_state.get(f"{key_prefix}audio"),
                    audio_ext=st.session_state.get(f"{key_prefix}ext", "wav"),
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                for key in (text_key, f"{key_prefix}edit", f"{key_prefix}audio", f"{key_prefix}ext"):
                    st.session_state.pop(key, None)
                st.success(f"Заметка #{note_id} сохранена.")
                st.rerun()


def render_marker_panel(slug: str, marker_id: str) -> None:
    notes = storage.list_notes(text_slug=slug, marker_id=marker_id)
    with st.container(border=True):
        head = st.columns([4, 1])
        with head[0]:
            st.markdown(f"#### 🔖 Маркер `{marker_id}`")
            st.caption(f"Заметок на маркере: {len(notes)}")
        with head[1]:
            if st.button("Закрыть", key=f"close_{slug}_{marker_id}", use_container_width=True):
                set_query(marker=None)
                st.rerun()

        with st.expander("➕ Добавить голосовую заметку", expanded=not notes):
            audio_note_section(slug, marker_id, key_prefix=f"mk_{slug}_{marker_id}_")

        for note in notes:
            render_note(note, key_prefix=f"mk_{slug}_{marker_id}_")


def tab_texts() -> None:
    st.subheader("📄 Тексты")
    texts = storage.list_texts()

    with st.expander("➕ Добавить текст (рассказ, конспект, …)"):
        with st.form("add_text", clear_on_submit=True):
            title = st.text_input("Название")
            content = st.text_area(
                "Текст (Markdown). Маркеры вида {{m:1}}, {{m:2}} …",
                height=200,
            )
            if st.form_submit_button("Сохранить", type="primary"):
                if not title.strip() or not content.strip():
                    st.error("Заполните название и текст.")
                else:
                    slug = storage.create_text(title, content)
                    st.session_state["doc_slug"] = slug
                    set_query(doc=slug, marker=None)
                    st.rerun()

    if not texts:
        st.info("Пока нет текстов. Добавьте первый выше.")
        return

    labels = text_label_map()
    url_doc = qp("doc")
    default_slug = url_doc if url_doc in labels.values() else st.session_state.get("doc_slug")
    if default_slug not in labels.values():
        default_slug = next(iter(labels.values()))
    current_label = next(label for label, slug in labels.items() if slug == default_slug)
    selected = st.selectbox("Выберите текст", list(labels), index=list(labels).index(current_label))
    slug = labels[selected]
    st.session_state["doc_slug"] = slug
    if qp("doc") != slug:
        set_query(doc=slug, marker=None)

    doc = storage.get_text(slug)
    if doc is None:
        st.rerun()
        return

    content = doc["content"]
    counts = storage.count_notes_by_marker(slug)
    available = markers.find_markers(content)
    active = qp("marker")
    if active not in available:
        active = None

    st.markdown(MARKER_CSS, unsafe_allow_html=True)
    st.markdown(markers.render(content, slug, counts=counts, active=active))
    st.caption(
        f"Создан: {doc['created_at']} · маркеров: {len(available)} · "
        "жёлтая метка 🔖 — маркер, к нему можно привязать текстовую или голосовую заметку"
    )

    if available:
        st.markdown("**Маркеры**")
        columns = st.columns(min(len(available), 4) or 1)
        for i, mid in enumerate(available):
            with columns[i % len(columns)]:
                label = f"🔖 {mid} · {counts.get(mid, 0)}"
                if st.button(label, key=f"open_{slug}_{mid}", use_container_width=True):
                    st.session_state["doc_slug"] = slug
                    set_query(doc=slug, marker=mid)
                    st.rerun()

    if active:
        render_marker_panel(slug, active)

    with st.expander("✏️ Редактировать текст и маркеры"):
        lines = content.splitlines()
        c1, c2, _ = st.columns([1, 1, 3])
        line_no = c1.number_input(
            "Вставить маркер после строки",
            min_value=0,
            max_value=len(lines),
            value=len(lines),
            step=1,
        )
        if c2.button("➕ Добавить маркер", use_container_width=True):
            new_content, mid = markers.insert_marker(content, int(line_no))
            storage.update_text(slug, new_content)
            st.session_state["doc_slug"] = slug
            set_query(doc=slug, marker=mid)
            st.rerun()

        with st.form(f"edit_text_{slug}"):
            new_content = st.text_area("Текст (Markdown)", value=content, height=320)
            s1, s2, _ = st.columns([1, 1, 3])
            save = s1.form_submit_button("Сохранить текст")
            delete = s2.form_submit_button("🗑 Удалить текст")
            if save:
                storage.update_text(slug, new_content)
                st.success("Текст сохранён.")
                st.rerun()
            if delete:
                st.session_state["confirm_del_text"] = slug

        if st.session_state.get("confirm_del_text") == slug:
            st.warning("Удалить текст вместе со всеми привязанными заметками и аудио?")
            d1, d2, _ = st.columns([1, 1, 3])
            if d1.button("Да, удалить", key="confirm_del_yes"):
                storage.delete_text(slug)
                st.session_state.pop("confirm_del_text", None)
                st.session_state.pop("doc_slug", None)
                set_query(doc=None, marker=None)
                st.rerun()
            if d2.button("Отмена", key="confirm_del_no"):
                st.session_state.pop("confirm_del_text", None)
                st.rerun()


def tab_recognize() -> None:
    st.subheader("🎙 Голосовая заметка")
    st.caption("Запишите голосом или загрузите аудио — приложение распознает речь в текст.")

    labels = text_label_map()
    options = [NO_TEXT] + list(labels)
    chosen = st.selectbox("Привязать к тексту", options)
    slug = labels.get(chosen)

    marker_id = None
    opts = marker_options(slug)
    if opts:
        chosen_marker = st.selectbox("Привязать к маркеру", [NO_MARKER] + opts)
        marker_id = chosen_marker if chosen_marker != NO_MARKER else None

    st.divider()
    audio_note_section(slug, marker_id, key_prefix="rec_")
    if slug:
        st.caption("Заметка появится во вкладке «Заметки» и на самом маркере в тексте.")


def tab_notes() -> None:
    st.subheader("📝 Заметки")

    texts = storage.list_texts()
    labels = {t["title"]: t["slug"] for t in texts}
    filter_options = ["Все заметки", "Без текста"] + list(labels)
    chosen = st.selectbox("Фильтр", filter_options)

    with st.expander("✏️ Новая текстовая заметка"):
        tlabels = text_label_map()
        topts = [NO_TEXT] + list(tlabels)
        chosen_text = st.selectbox("Текст", topts, key="nt_text")
        slug = tlabels.get(chosen_text)
        mopts = [NO_MARKER] + marker_options(slug)
        chosen_marker = st.selectbox("Маркер", mopts)
        text = st.text_area("Текст заметки", height=150)
        if st.button("Сохранить", type="primary", key="nt_save"):
            marker_id = chosen_marker if chosen_marker != NO_MARKER else None
            try:
                storage.add_note(text, text_slug=slug, marker_id=marker_id)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()

    if chosen == "Без текста":
        notes = [n for n in storage.list_notes() if not n.get("text_slug")]
    elif chosen == "Все заметки":
        notes = storage.list_notes()
    else:
        notes = storage.list_notes(text_slug=labels[chosen])

    if not notes:
        st.info("Заметок нет. Создайте текстовую или запишите голосовую.")
        return

    st.caption(f"Всего: {len(notes)}")
    for note in notes:
        render_note(note, key_prefix="notes_")


def main() -> None:
    st.title("🎙 Голосовые заметки")
    s = storage.stats()
    st.caption(
        f"Текстов: **{s['texts']}** · Заметок: **{s['notes']}** (голосовых: **{s['voiced']}**)"
    )

    tabs = st.tabs(["📄 Тексты", "🎙 Распознавание", "📝 Заметки"])
    with tabs[0]:
        tab_texts()
    with tabs[1]:
        tab_recognize()
    with tabs[2]:
        tab_notes()


main()
