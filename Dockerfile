FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    API_HOST=0.0.0.0 \
    API_PORT=8000

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY configs ./configs
COPY src ./src
COPY scripts ./scripts

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import json, os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"API_PORT\", \"8000\")}/health', timeout=3).read()"

CMD ["sh", "-c", "python -m uvicorn android_planner.api:app --host \"$API_HOST\" --port \"$API_PORT\""]
