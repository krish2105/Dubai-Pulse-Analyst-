# DubaiPulse Analyst — backend image
FROM python:3.12-slim

# System deps kept minimal; wheels cover duckdb/pandas/pyarrow/numpy.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Application code + processed data (raw CSVs are excluded via .dockerignore;
# only the DuckDB-ready parquet files are needed at runtime).
COPY app ./app
COPY data/processed ./data/processed
COPY data/data_dictionary.md ./data/data_dictionary.md
COPY data/market_events.json ./data/market_events.json

EXPOSE 8000

# Hosts (Railway/Render) inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
