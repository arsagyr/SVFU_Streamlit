import os

import streamlit as st

from core import db, storage

st.set_page_config(
    page_title="Голосовые заметки",
    page_icon="🎙",
    layout="wide",
    initial_sidebar_state="collapsed",
)

db.init_db()

DOCUMENT_NONE = "— без привязки —"


def doc_options() -> dict:
    """Словарь {название (с id): id} для selectbox документов."""
    docs = db.list_documents()
    labels = {f"{d['title']}  ·  заметок: {d['notes_count']}": d["id"] for d in docs}
    return labels


def save_note(content: str, doc_label: str | None, audio_bytes: bytes | None = None,
              audio_ext: str = "wav") -> int:
    content = content.strip()
    if not content:
        raise ValueError("Текст заметки пуст.")
    document_id = doc_options().get(doc_label) if doc_label and doc_label != DOCUMENT_NONE else None
    audio_path = storage.save_audio(audio_bytes, audio_ext) if audio_bytes else None
    return db.add_note(content, document_id=document_id, audio_path=audio_path)


def render_note(note: dict, key_prefix: str) -> None:
    tag = f"🎵 «{note['document_title']}»" if note["document_title"] else "свободная заметка"
    with st.container(border=True):
        cols = st.columns([4, 1, 1])
        with cols[0]:
            st.caption(f"#{note['id']} · {note['created_at']} · {tag}")
            st.markdown(note["content"])
            if note["audio_path"]:
                st.audio(str(storage.audio_abs_path(note["audio_path"])))
        edit_key = f"{key_prefix}edit_{note['id']}"
        del_key = f"{key_prefix}del_{note['id']}"

        with cols[1]:
            if st.button("Изменить", key=edit_key, use_container_width=True):
                st.session_state["editing_note"] = note["id"]
                st.rerun()
        with cols[2]:
            if st.button("Удалить", key=del_key, use_container_width=True):
                audio = db.delete_note(note["id"])
                storage.delete_audio(audio)
                st.rerun()

    if st.session_state.get("editing_note") == note["id"]:
        labels = doc_options()
        options = [DOCUMENT_NONE] + list(labels)
        current = DOCUMENT_NONE
        if note["document_title"]:
            for label, doc_id in labels.items():
                if doc_id == note["document_id"]:
                    current = label
        with st.form(f"edit_form_{note['id']}", border=True):
            new_text = st.text_area("Текст заметки", value=note["content"], height=150)
            new_doc = st.selectbox("Документ", options, index=options.index(current))
            c1, c2, _ = st.columns([1, 1, 3])
            submitted = c1.form_submit_button("Сохранить", use_container_width=True)
            cancelled = c2.form_submit_button("Отмена", use_container_width=True)
            if submitted:
                document_id = labels.get(new_doc) if new_doc != DOCUMENT_NONE else None
                db.update_note(note["id"], new_text, document_id=document_id)
                st.session_state.pop("editing_note", None)
                st.rerun()
            if cancelled:
                st.session_state.pop("editing_note", None)
                st.rerun()


def tab_documents() -> None:
    st.subheader("📄 Тексты")
    docs = db.list_documents()

    with st.expander("➕ Добавить текст (рассказ, конспект, …)"):
        with st.form("add_document", clear_on_submit=True):
            title = st.text_input("Название")
            content = st.text_area("Текст (поддерживается Markdown)", height=220)
            if st.form_submit_button("Сохранить", type="primary"):
                if not title.strip() or not content.strip():
                    st.error("Заполните название и текст.")
                else:
                    db.add_document(title, content)
                    st.success(f"Текст «{title}» сохранён.")
                    st.rerun()

    if not docs:
        st.info("Пока нет текстов. Добавьте первый выше.")
        return

    labels = {f"{d['title']}  ·  заметок: {d['notes_count']}": d["id"] for d in docs}
    selected = st.selectbox("Выберите текст", list(labels))
    doc = db.get_document(labels[selected])
    if not doc:
        st.rerun()
        return

    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("🗑 Удалить текст", key="del_doc"):
        st.session_state["confirm_del_doc"] = doc["id"]
    if doc["id"] == st.session_state.get("confirm_del_doc"):
        c2.warning("Удалить вместе с привязанными заметками?")
        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button("Да, удалить", key="confirm_del_yes"):
            for n in db.list_notes(doc["id"]):
                storage.delete_audio(n["audio_path"])
            db.delete_document(doc["id"])
            st.session_state.pop("confirm_del_doc", None)
            st.rerun()
        if b2.button("Отмена", key="confirm_del_no"):
            st.session_state.pop("confirm_del_doc", None)
            st.rerun()

    st.caption(f"Создан: {doc['created_at']}")
    st.markdown(doc["content"])


def tab_recognize() -> None:
    st.subheader("🎙 Голосовая заметка")
    st.caption("Запишите голосом или загрузите аудио — приложение распознает речь в текст.")

    mode = st.radio("Источник звука", ["🎙 Микрофон", "📁 Загрузить файл"], horizontal=True)

    audio_bytes: bytes | None = None
    audio_ext = "wav"
    audio_name = ""

    if mode == "🎙 Микрофон":
        try:
            from audio_recorder_streamlit import audio_recorder

            audio_bytes = audio_recorder(
                text="Нажмите, чтобы записать",
                icon_name="microphone",
                icon_size="2x",
                sample_rate=16000,
                key="mic_recorder",
            )
        except Exception as exc:
            st.error(f"Не удалось запустить запись с микрофона: {exc}")
        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav")
    else:
        uploaded = st.file_uploader("Аудиофайл", type=["wav", "mp3", "m4a", "ogg", "flac", "webm"])
        if uploaded is not None:
            audio_bytes = uploaded.getvalue()
            audio_ext = os.path.splitext(uploaded.name)[1].lstrip(".") or "wav"
            audio_name = uploaded.name
            st.audio(audio_bytes)

    labels = doc_options()
    options = [DOCUMENT_NONE] + list(labels)
    doc_label = st.selectbox("Привязать к документу", options)

    if st.button("🔍 Распознать", type="primary", disabled=audio_bytes is None):
        if not audio_bytes:
            st.warning("Сначала запишите или загрузите аудио.")
            st.stop()
        with st.spinner("Распознаю речь… (первая загрузка модели может занять время)"):
            try:
                from core.stt import transcribe

                text = transcribe(audio_bytes, suffix=f".{audio_ext}")
            except Exception as exc:
                st.error(f"Ошибка распознавания: {exc}")
                st.stop()
        if not text:
            st.warning("Речь не обнаружена в записи.")
            st.stop()
        st.session_state["stt_text"] = text
        st.session_state["stt_doc"] = doc_label
        st.session_state["stt_audio"] = audio_bytes
        st.session_state["stt_ext"] = audio_ext

    if st.session_state.get("stt_text"):
        st.success("Распознавание завершено. При необходимости отредактируйте текст и сохраните.")
        edited = st.text_area(
            "Текст заметки",
            value=st.session_state["stt_text"],
            height=220,
            key="stt_edit",
        )
        st.audio(st.session_state["stt_audio"])
        if st.button("💾 Сохранить заметку", type="primary"):
            try:
                note_id = save_note(
                    edited,
                    st.session_state.get("stt_doc"),
                    st.session_state.get("stt_audio"),
                    st.session_state.get("stt_ext", "wav"),
                )
            except ValueError as exc:
                st.error(str(exc))
                st.stop()
            for key in ("stt_text", "stt_doc", "stt_audio", "stt_ext", "stt_edit"):
                st.session_state.pop(key, None)
            st.success(f"Заметка #{note_id} сохранена. Она во вкладке «Заметки».")
            st.rerun()


def tab_notes() -> None:
    st.subheader("📝 Заметки")

    docs = db.list_documents()
    filter_options = ["Все документы", DOCUMENT_NONE] + [d["title"] for d in docs]
    chosen = st.selectbox("Фильтр", filter_options)

    document_id: int | None = None
    free_only = False
    if chosen == DOCUMENT_NONE:
        free_only = True
    elif chosen != "Все документы":
        document_id = next(d["id"] for d in docs if d["title"] == chosen)

    with st.expander("✏️ Новая текстовая заметка"):
        with st.form("add_text_note", clear_on_submit=True):
            labels = doc_options()
            options = [DOCUMENT_NONE] + list(labels)
            doc_label = st.selectbox("Документ", options)
            text = st.text_area("Текст заметки", height=150)
            if st.form_submit_button("Сохранить", type="primary"):
                try:
                    save_note(text, doc_label)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    notes = db.list_notes(document_id)
    if free_only:
        notes = [n for n in notes if n["document_id"] is None]

    if not notes:
        st.info("Заметок нет. Создайте текстовую или запишите голосовую.")
        return

    st.caption(f"Всего: {len(notes)}")
    for note in notes:
        render_note(note, key_prefix="notes_")


def main() -> None:
    st.title("🎙 Голосовые заметки")
    s = db.stats()
    st.caption(
        f"Текстов: **{s['documents']}** · Заметок: **{s['notes']}** "
        f"(голосовых: **{s['voiced']}**)"
    )

    tabs = st.tabs(["📄 Тексты", "🎙 Распознавание", "📝 Заметки"])
    with tabs[0]:
        tab_documents()
    with tabs[1]:
        tab_recognize()
    with tabs[2]:
        tab_notes()


main()
