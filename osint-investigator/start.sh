#!/bin/bash
set -e

echo "Iniciando Celery worker..."
celery -A app.workers.celery_app worker --loglevel=info -Q investigations -c 2 &
CELERY_PID=$!

echo "Iniciando FastAPI..."
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

# Se o uvicorn encerrar, encerra o celery também
kill $CELERY_PID 2>/dev/null || true
