#!/bin/bash

echo "🚀 Iniciando Healtfolio..."
echo "PORT: ${PORT:-8000}"
echo "Environment variables check:"
echo "- OPENAI_API_KEY: ${OPENAI_API_KEY:+SET}"
echo "- GOOGLE_SERVICE_ACCOUNT_JSON: ${GOOGLE_SERVICE_ACCOUNT_JSON:+SET}"
echo "- SHEET_ID: ${SHEET_ID:+SET}"
echo "- WHATSAPP_PROVIDER: ${WHATSAPP_PROVIDER:-not set}"
echo "- REDIS_URL: ${REDIS_URL:+SET}"

# Iniciar la aplicación
exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 