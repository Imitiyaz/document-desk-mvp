# Application runtime; a single API worker owns the local document workspace.
FROM python:3.12-slim-bookworm
ENV PYTHONPATH=/app/backend PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1 \
    HF_HOME=/app/cache/huggingface CHROMA_PERSIST_DIR=/app/data/chroma \
    UPLOAD_TEMP_DIR=/app/data/uploads ANONYMIZED_TELEMETRY=False \
    OTEL_SDK_DISABLED=true DO_NOT_TRACK=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
COPY backend/requirements*.txt ./backend/
RUN python -m pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app ./backend/app
COPY LICENSE THIRD_PARTY_NOTICES.md ./
RUN mkdir -p /app/data/chroma /app/data/uploads /app/cache/huggingface \
    && chown -R app:app /app/data /app/cache
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=300s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
