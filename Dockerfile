FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/home/app/.cache/huggingface \
    APP_DATA_DIR=/app/data

WORKDIR /app

RUN useradd -m -u 1000 app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Предзагрузка модели распознавания речи, чтобы контейнер работал офлайн
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')" \
    && chown -R app:app /home/app

COPY --chown=app:app . .
RUN mkdir -p /app/data && chown -R app:app /app

USER app
EXPOSE 8501

VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py"]
