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

EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_ID = os.getenv("EVOLUTION_INSTANCE_ID")
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "evolution").lower()

# Headers para Evolution API (se configuran dinámicamente en cada request)
HEADERS = {
    "Content-Type": "application/json",
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
            whatsapp_configured = bool(EVO_URL and EVOLUTION_API_KEY and INSTANCE_ID)
        
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
        
        # Debug: Verificar API Key del webhook vs configuración
        webhook_apikey = event_json.get('apikey', '')
        if webhook_apikey:
            logger.info(f"Webhook API Key: {webhook_apikey[:8]}...{webhook_apikey[-4:]}")
            logger.info(f"Config API Key: {EVOLUTION_API_KEY[:8] if EVOLUTION_API_KEY else 'None'}...{EVOLUTION_API_KEY[-4:] if EVOLUTION_API_KEY else ''}")
            logger.info(f"API Keys match: {webhook_apikey == EVOLUTION_API_KEY}")

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
        
        # Usar el API Key del webhook si está disponible
        webhook_apikey = event_json.get('apikey', '')
        await send_whatsapp_message(chat_id, reply_text, webhook_apikey)
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


async def send_whatsapp_message(to_number: str, text: str, webhook_apikey: str = None):
    """Envía mensaje usando el proveedor configurado."""
    if WHATSAPP_PROVIDER == "twilio":
        success = await send_twilio_whatsapp_message(to_number, text)
        if not success:
            raise Exception("Failed to send message via Twilio")
    else:  # evolution
        await send_evolution_message(to_number, text, webhook_apikey)


async def send_evolution_message(to_number: str, text: str, webhook_apikey: str = None):
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
    
    # Endpoints comunes de Evolution API - probar diferentes variaciones
    endpoints_to_try = [
        f"{EVO_URL}/message/sendText/{INSTANCE_ID}",
        f"{EVO_URL}/v1/message/sendText/{INSTANCE_ID}",
        f"{EVO_URL}/api/message/sendText/{INSTANCE_ID}",
        f"{EVO_URL}/message/text/{INSTANCE_ID}",
        f"{EVO_URL}/sendText/{INSTANCE_ID}",
        f"{EVO_URL}/send-text/{INSTANCE_ID}",
        f"{EVO_URL}/chat/send/{INSTANCE_ID}",
        f"{EVO_URL}/instance/sendText/{INSTANCE_ID}",
        f"{EVO_URL}/instance/{INSTANCE_ID}/sendText",
        f"{EVO_URL}/instance/{INSTANCE_ID}/message/sendText",
        f"{EVO_URL}/message/send/{INSTANCE_ID}",
        f"{EVO_URL}/send/{INSTANCE_ID}",
        f"{EVO_URL}/chat/{INSTANCE_ID}/send",
        f"{EVO_URL}/whatsapp/send/{INSTANCE_ID}",
        f"{EVO_URL}/whatsapp/{INSTANCE_ID}/send"
    ]
    
    # Headers correctos para Evolution API v2
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Usar API Key del webhook si está disponible, sino usar el configurado
    api_key_to_use = webhook_apikey if webhook_apikey else EVOLUTION_API_KEY
    
    # Debug: Verificar API Key a usar
    logger.info(f"Webhook API Key available: {bool(webhook_apikey)}")
    logger.info(f"Config API Key available: {bool(EVOLUTION_API_KEY)}")
    logger.info(f"API Key to use: {api_key_to_use[:8] if api_key_to_use else 'None'}...{api_key_to_use[-4:] if api_key_to_use else ''}")
    
    # Agregar Authorization header con Bearer token (formato correcto para Evolution API)
    if api_key_to_use:
        headers["Authorization"] = f"Bearer {api_key_to_use}"
        logger.info("Using Bearer token for Evolution API authentication")
        logger.info(f"Headers with Authorization: {list(headers.keys())}")
    else:
        logger.info("No API Key available, using instance-only authentication")

    # Payload correcto para Evolution API v2 según documentación oficial
    payload: Dict[str, Any] = {
        "number": formatted_number,
        "text": text[:4096],
        "options": {
            "delay": 1200,
            "presence": "composing"
        }
    }
    
    # Payload simple para endpoints que no aceptan options
    simple_payload: Dict[str, Any] = {
        "number": formatted_number,
        "text": text[:4096]
    }

    # Log del payload para debugging
    payload_log = {
        "original_number": to_number,
        "formatted_number": formatted_number,
        "text_length": len(text),
        "text_preview": text[:50] + "..." if len(text) > 50 else text,
        "instance_id": INSTANCE_ID
    }
    logger.info(f"Evolution API payload: {payload_log}")

    # Primero probar endpoints de información para ver qué está disponible
    info_endpoints = [
        f"{EVO_URL}/",
        f"{EVO_URL}/health",
        f"{EVO_URL}/status",
        f"{EVO_URL}/ping",
        f"{EVO_URL}/instance/info/{INSTANCE_ID}",
        f"{EVO_URL}/instance/{INSTANCE_ID}/info",
        f"{EVO_URL}/api/instance/{INSTANCE_ID}",
        f"{EVO_URL}/docs",
        f"{EVO_URL}/swagger",
        f"{EVO_URL}/api-docs",
        f"{EVO_URL}/openapi.json",
        f"{EVO_URL}/api"
    ]
    
    for info_url in info_endpoints:
        try:
            logger.info(f"Testing info endpoint: {info_url}")
            
            async with httpx.AsyncClient(timeout=10) as client:
                info_response = await client.get(info_url, headers=headers)
                logger.info(f"Info endpoint {info_url}: {info_response.status_code} - {info_response.text[:200]}")
                
                if info_response.status_code == 200:
                    logger.info(f"✅ Found working info endpoint: {info_url}")
                    break
        except Exception as e:
            logger.warning(f"Info endpoint {info_url} failed: {e}")
    
    # Probar diferentes endpoints
    last_error = None
    
    for endpoint_index, url in enumerate(endpoints_to_try):
        try:
            logger.info(f"Trying endpoint {endpoint_index + 1}: {url}")
            
            # Probar primero con payload completo
            logger.info(f"Testing with full payload (with options)")
            logger.info(f"  URL: {url}")
            logger.info(f"  Headers: {headers}")
            logger.info(f"  Payload: {payload}")

            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(url, headers=headers, json=payload)
                
                logger.info(f"Evolution API response: Status {r.status_code} for endpoint {endpoint_index + 1}")
                logger.info(f"Response headers: {dict(r.headers)}")
                
                if r.status_code < 400:
                    logger.info(f"✅ Message sent successfully via Evolution API!")
                    logger.info(f"Successful endpoint: {url}")
                    logger.info(f"Response: {r.text}")
                    return  # Éxito, salir de la función
                else:
                    logger.warning(f"❌ Failed with full payload: {r.status_code} - {r.text}")
                    
                    # Si falla con payload completo, probar con payload simple
                    logger.info(f"Trying with simple payload (without options)")
                    logger.info(f"  Payload: {simple_payload}")
                    
                    r_simple = await client.post(url, headers=headers, json=simple_payload)
                    
                    if r_simple.status_code < 400:
                        logger.info(f"✅ Message sent successfully with simple payload!")
                        logger.info(f"Successful endpoint: {url}")
                        logger.info(f"Response: {r_simple.text}")
                        return  # Éxito, salir de la función
                    else:
                        logger.warning(f"❌ Failed with simple payload: {r_simple.status_code} - {r_simple.text}")
                        last_error = r_simple.text
                    
        except Exception as e:
            logger.warning(f"Error with endpoint {url}: {e}")
            last_error = str(e)
            continue
    
    # Si llegamos aquí, todos los endpoints fallaron
    error_details = {
        "endpoints_tried": len(endpoints_to_try),
        "last_error": last_error,
        "original_number": to_number,
        "formatted_number": formatted_number,
        "payload_text_length": len(text),
        "instance_id": INSTANCE_ID,
        "headers_sent": {k: v for k, v in headers.items() if k.lower() != 'authorization'},
        "request_headers_full": headers,
        "request_payload": payload
    }
    logger.error(f"All Evolution API endpoints failed: {error_details}")
    
    if "not-acceptable" in str(last_error).lower():
        raise Exception(f"Evolution API endpoint issue: All endpoints returned 'not-acceptable'. Please check Evolution API documentation.")
    else:
        raise Exception(f"Evolution API error after trying multiple endpoints: {last_error}")