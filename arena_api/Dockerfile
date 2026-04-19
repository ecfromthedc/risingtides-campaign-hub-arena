FROM python:3.12-slim

WORKDIR /app

# Build context is repo root — path files explicitly from arena_api/
COPY arena_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY arena_api/main.py /app/main.py

ENV PORT=8000
EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
