#!/bin/bash

echo "🚀 Iniciando Healtfolio..."
echo "PORT: ${PORT:-8000}"

# Validaciones críticas - FAIL FAST
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ ERROR: OPENAI_API_KEY es obligatorio"
    exit 1
fi

if [ -z "$SHEET_ID" ]; then
    echo "❌ ERROR: SHEET_ID es obligatorio"
    exit 1
fi

if [ -z "$GOOGLE_SERVICE_ACCOUNT_JSON" ]; then
    echo "❌ ERROR: GOOGLE_SERVICE_ACCOUNT_JSON es obligatorio"
    exit 1
fi

# Validar proveedor de WhatsApp
WHATSAPP_PROVIDER=${WHATSAPP_PROVIDER:-evolution}
if [ "$WHATSAPP_PROVIDER" = "evolution" ]; then
    if [ -z "$EVOLUTION_BASE_URL" ] || [ -z "$EVOLUTION_API_KEY" ] || [ -z "$EVOLUTION_INSTANCE_ID" ]; then
        echo "❌ ERROR: Evolution API no configurado correctamente"
        echo "   Necesitas: EVOLUTION_BASE_URL, EVOLUTION_API_KEY, EVOLUTION_INSTANCE_ID"
        exit 1
    fi
elif [ "$WHATSAPP_PROVIDER" = "twilio" ]; then
    if [ -z "$TWILIO_ACCOUNT_SID" ] || [ -z "$TWILIO_AUTH_TOKEN" ] || [ -z "$TWILIO_WHATSAPP_NUMBER" ]; then
        echo "❌ ERROR: Twilio no configurado correctamente"
        echo "   Necesitas: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER"
        exit 1
    fi
else
    echo "❌ ERROR: WHATSAPP_PROVIDER debe ser 'evolution' o 'twilio'"
    exit 1
fi

echo "✅ Todas las variables críticas están configuradas"
echo "🚀 Iniciando aplicación..."

exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 