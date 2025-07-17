import json
import logging
import os
from pathlib import Path
from typing import Dict, Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, Header
from fastapi.responses import PlainTextResponse

from .mcp_gateway import process
from .utils import (
    extract_text_from_event, 
    get_chat_id, 
    extract_text_from_twilio_event, 
    get_twilio_chat_id
)
from .twilio_client import (
    send_twilio_whatsapp_message, 
    create_twilio_response, 
    validate_twilio_webhook,
    is_twilio_configured
)

# Cargar variables de entorno
load_dotenv(Path(__file__).parent.parent / ".env")

app = FastAPI()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("🚀 Iniciando aplicación Healtfolio...")

# Configuración Evolution API
EVO_URL = os.getenv("EVOLUTION_BASE_URL")
if EVO_URL:
    EVO_URL = EVO_URL.rstrip("/")

API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_ID = os.getenv("EVOLUTION_INSTANCE_ID")
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "evolution").lower()

# Headers mejorados para Evolution API
HEADERS = {
    "Content-Type": "application/json",
    "apikey": API_KEY,  # Este debería ser el API Key real, no el Instance ID
    "Accept": "application/json"
}

logger.info(f"📱 Proveedor de WhatsApp: {WHATSAPP_PROVIDER}")


@app.get("/ping")
async def ping():
    """Endpoint simple para testing de conectividad."""
    return {"message": "pong"}


@app.get("/health")
async def health_check():
    """Health check endpoint para monitoring."""
    try:
        # Verificar configuración básica
        openai_configured = bool(os.getenv("OPENAI_API_KEY"))
        sheets_configured = bool(os.getenv("SHEET_ID") and os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
        
        if WHATSAPP_PROVIDER == "twilio":
            whatsapp_configured = is_twilio_configured()
        else:  # evolution
            whatsapp_configured = bool(EVO_URL and API_KEY and INSTANCE_ID)
        
        health_status = {
            "status": "healthy",
            "checks": {
                "openai": "ok" if openai_configured else "error",
                "google_sheets": "ok" if sheets_configured else "error", 
                "whatsapp": "ok" if whatsapp_configured else "error"
            },
            "provider": WHATSAPP_PROVIDER
        }
        
        # Si algún check falla, cambiar status general
        if any(status == "error" for status in health_status["checks"].values()):
            health_status["status"] = "degraded"
            
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.get("/")
async def root():
    """Endpoint raíz con información del estado del servicio."""
    return {
        "service": "Healtfolio WhatsApp Bot",
        "version": "1.0.0",
        "status": "active",
        "provider": WHATSAPP_PROVIDER
    }


@app.post("/webhook", status_code=200)
async def webhook_evolution(request: Request):
    """Webhook para Evolution API."""
    try:
        event_json = await request.json()
        logger.info(f"Received Evolution webhook: {event_json}")

        # Solo reaccionamos a MESSAGES_UPSERT
        event_name = event_json.get("event", "").upper().replace(".", "_")
        if event_name != "MESSAGES_UPSERT":
            logger.info(f"Event ignored (not MESSAGES_UPSERT): {event_json.get('event', '')}")
            return {"status": "ignored"}

        user_text = extract_text_from_event(event_json)
        if not user_text:
            logger.info("No text found in message")
            return {"status": "no_text"}

        chat_id = get_chat_id(event_json)
        logger.info(f"Processing message: '{user_text}' from {chat_id}")
        
        reply_text = process(user_text, chat_id)
        logger.info(f"Generated reply: {reply_text[:100]}...")
        
        await send_whatsapp_message(chat_id, reply_text)
        logger.info("Message sent successfully")

        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Evolution webhook error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/webhook/twilio")
async def webhook_twilio(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    MessageSid: str = Form(...),
    x_twilio_signature: str = Header(None, alias="X-Twilio-Signature")
):
    """Webhook para Twilio WhatsApp."""
    try:
        form_data = {
            "Body": Body,
            "From": From,
            "To": To,
            "MessageSid": MessageSid
        }
        
        logger.info(f"Received Twilio webhook: {form_data}")
        
        # Validar webhook en producción
        request_url = str(request.url)
        # Temporalmente deshabilitado para Railway
        # if x_twilio_signature and not validate_twilio_webhook(request_url, x_twilio_signature, form_data):
        #     logger.warning("Invalid Twilio webhook signature")
        #     return PlainTextResponse("Unauthorized", status_code=401)
        logger.info("⚠️ Webhook signature validation temporarily disabled")
        
        user_text = extract_text_from_twilio_event(form_data)
        if not user_text:
            logger.info("No text found in Twilio message")
            return PlainTextResponse("OK")
        
        chat_id = get_twilio_chat_id(form_data)
        logger.info(f"Processing Twilio message: '{user_text}' from {chat_id}")
        
        reply_text = process(user_text, chat_id)
        logger.info(f"Generated reply: {reply_text[:100]}...")
        
        twiml_response = create_twilio_response(reply_text)
        logger.info("Response sent via Twilio TwiML")
        
        return PlainTextResponse(twiml_response, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Twilio webhook error: {str(e)}", exc_info=True)
        return PlainTextResponse("Error", status_code=500)


async def send_whatsapp_message(to_number: str, text: str):
    """Envía mensaje usando el proveedor configurado."""
    if WHATSAPP_PROVIDER == "twilio":
        success = await send_twilio_whatsapp_message(to_number, text)
        if not success:
            raise Exception("Failed to send message via Twilio")
    else:  # evolution
        await send_evolution_message(to_number, text)


async def send_evolution_message(to_number: str, text: str):
    """Envía mensaje usando Evolution API."""
    if not (EVO_URL and INSTANCE_ID):
        raise Exception("Evolution API not properly configured")
        
    # Formatear número para Evolution API (agregar código de país si no está)
    formatted_number = to_number
    if not to_number.startswith("+"):
        # Asumir código de país +54 para Argentina si no está presente
        if len(to_number) == 11 and to_number.startswith("9"):
            formatted_number = "+54" + to_number
        elif len(to_number) == 10 and to_number.startswith("11"):
            formatted_number = "+54" + to_number
        else:
            formatted_number = "+" + to_number
    
    # Formato correcto según documentación oficial de Evolution API
    url = f"{EVO_URL}/message/sendText/{INSTANCE_ID}"
    logger.info(f"Sending message to Evolution API: {url}")

    # Payload correcto para Evolution API v2
    payload: Dict[str, Any] = {
        "number": formatted_number,
        "text": text[:4096]
    }

    # Headers correctos para Evolution API - Incluir API Key si está disponible
    headers = {
        "Content-Type": "application/json"
    }
    
    # Debug: Verificar si API_KEY está configurado
    logger.info(f"API_KEY configured: {bool(API_KEY)}")
    logger.info(f"API_KEY length: {len(API_KEY) if API_KEY else 0}")
    
    # Agregar API Key si está configurado (para compatibilidad)
    if API_KEY:
        headers["apikey"] = API_KEY
        logger.info("Using API Key for Evolution API authentication")
    else:
        logger.info("No API Key configured, using instance-only authentication")

    # Log del payload para debugging
    payload_log = {
        "original_number": to_number,
        "formatted_number": formatted_number,
        "text_length": len(text),
        "text_preview": text[:50] + "..." if len(text) > 50 else text,
        "instance_id": INSTANCE_ID
    }
    logger.info(f"Evolution API payload: {payload_log}")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, headers=headers, json=payload)
            
            logger.info(f"Evolution API response: Status {r.status_code}")
            
            if r.status_code >= 400:
                error_details = {
                    "status_code": r.status_code,
                    "response_text": r.text,
                    "url": url,
                    "original_number": to_number,
                    "formatted_number": formatted_number,
                    "payload_text_length": len(text),
                    "instance_id": INSTANCE_ID,
                    "headers_sent": {k: v for k, v in headers.items() if k.lower() != 'apikey'}
                }
                logger.error(f"Evolution API error details: {error_details}")
                
                if r.status_code == 400:
                    raise Exception(f"Evolution API Bad Request (400): {r.text}")
                elif r.status_code == 401:
                    raise Exception(f"Evolution API Unauthorized (401): Check instance connection or API key")
                elif r.status_code == 403:
                    raise Exception(f"Evolution API Forbidden (403): Check permissions")
                elif r.status_code == 404:
                    raise Exception(f"Evolution API Not Found (404): Check instance ID '{INSTANCE_ID}'")
                else:
                    raise Exception(f"Evolution API error: {r.status_code} - {r.text}")
            else:
                logger.info(f"✅ Message sent successfully via Evolution API!")
                logger.info(f"Response: {r.text}")
                
    except httpx.TimeoutException:
        logger.error("Evolution API request timed out")
        raise Exception("Evolution API request timed out")
    except httpx.RequestError as e:
        logger.error(f"Evolution API request error: {e}")
        raise Exception(f"Evolution API connection error: {e}")
    except Exception as e:
        if "Evolution API" in str(e):
            raise  # Re-raise our custom exceptions
        else:
            logger.error(f"Unexpected error in send_evolution_message: {e}", exc_info=True)
            raise Exception(f"Unexpected error sending message: {e}")