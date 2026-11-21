FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "set -e; if [ \"${RUN_MIGRATIONS:-false}\" = \"true\" ]; then alembic upgrade head; fi; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
