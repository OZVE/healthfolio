import json
import logging
import os
from pathlib import Path
from typing import Dict, Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, Header
from fastapi.responses import PlainTextResponse

# Cargar variables de entorno desde el archivo .env en la raíz del proyecto
load_dotenv(Path(__file__).parent.parent / ".env")

app = FastAPI()

# Configurar logging PRIMERO
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Importaciones con manejo de errores (DESPUÉS de definir logger)
try:
    from .mcp_gateway import process
    logger.info("✅ MCP Gateway importado correctamente")
except ImportError as e:
    logger.error(f"❌ Error importando MCP Gateway: {e}")
    def process(text, chat_id):
        return "Error: Sistema de IA no disponible temporalmente"

try:
    from .utils import extract_text_from_event, get_chat_id, extract_text_from_twilio_event, get_twilio_chat_id
    logger.info("✅ Utils importado correctamente")
except ImportError as e:
    logger.error(f"❌ Error importando Utils: {e}")

try:
    from .twilio_client import (
        send_twilio_whatsapp_message, 
        create_twilio_response, 
        validate_twilio_webhook,
        is_twilio_configured,
        log_twilio_config
    )
    logger.info("✅ Twilio Client importado correctamente")
except ImportError as e:
    logger.error(f"❌ Error importando Twilio Client: {e}")
    def is_twilio_configured():
        return False
    def log_twilio_config():
        pass

# Log de inicio para debugging
logger.info("🚀 Iniciando aplicación Healtfolio...")
logger.info(f"Python version: {os.sys.version}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")

# Verificar imports críticos
try:
    import openai
    logger.info("✅ OpenAI importado correctamente")
except ImportError as e:
    logger.error(f"❌ Error importando OpenAI: {e}")

try:
    import redis
    logger.info("✅ Redis importado correctamente")
except ImportError as e:
    logger.error(f"❌ Error importando Redis: {e}")

try:
    import gspread
    logger.info("✅ GSpread importado correctamente")
except ImportError as e:
    logger.error(f"❌ Error importando GSpread: {e}")

logger.info("📦 Todos los imports completados")

# Configuración Evolution API con manejo de errores
try:
    EVO_URL = os.getenv("EVOLUTION_BASE_URL")
    if EVO_URL:
        EVO_URL = EVO_URL.rstrip("/")
    else:
        logger.warning("EVOLUTION_BASE_URL not found in environment variables!")

    API_KEY = os.getenv("EVOLUTION_API_KEY")
    INSTANCE_ID = os.getenv("EVOLUTION_INSTANCE_ID")

    # Debug: print loaded variables
    logger.info(f"Loaded environment variables:")
    logger.info(f"EVO_URL: {EVO_URL}")
    logger.info(f"API_KEY: {'***' if API_KEY else 'NOT SET'}")
    logger.info(f"INSTANCE_ID: {INSTANCE_ID}")

    # Log configuración de Twilio
    log_twilio_config()

    HEADERS = {
        "Content-Type": "application/json",
        "apikey": API_KEY,
    }

    # Configurar proveedor de WhatsApp
    WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "evolution").lower()  # "evolution" o "twilio"
    logger.info(f"📱 Proveedor de WhatsApp configurado: {WHATSAPP_PROVIDER}")
    
except Exception as e:
    logger.error(f"Error en configuración inicial: {e}")
    EVO_URL = None
    API_KEY = None
    INSTANCE_ID = None
    WHATSAPP_PROVIDER = "twilio"
    HEADERS = {"Content-Type": "application/json"}


@app.get("/ping")
async def ping():
    """Endpoint simple para testing de conectividad."""
    return {"message": "pong", "timestamp": "2024-01-01T00:00:00Z"}

@app.get("/status")
async def simple_status():
    """Status endpoint simplificado sin dependencias externas."""
    return {
        "service": "Healtfolio",
        "status": "online",
        "port": os.getenv("PORT", "8000")
    }

@app.get("/")
async def root():
    """Endpoint raíz con información del estado del servicio."""
    try:
        return {
            "service": "Healtfolio WhatsApp Bot",
            "version": "1.0.0",
            "status": "active",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "port": os.getenv("PORT", "8000"),
            "providers": {
                "evolution": {
                    "configured": bool(EVO_URL and API_KEY and INSTANCE_ID),
                    "active": WHATSAPP_PROVIDER == "evolution"
                },
                "twilio": {
                    "configured": bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN")),
                    "active": WHATSAPP_PROVIDER == "twilio"
                }
            }
        }
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        return {
            "service": "Healtfolio WhatsApp Bot", 
            "status": "error",
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    """Health check endpoint para monitoring."""
    try:
        # Verificar configuración básica sin dependencias externas
        openai_configured = bool(os.getenv("OPENAI_API_KEY"))
        sheets_configured = bool(os.getenv("SHEET_ID"))
        twilio_configured = bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))
        evolution_configured = bool(EVO_URL and API_KEY and INSTANCE_ID)
        whatsapp_configured = twilio_configured or evolution_configured
        
        # Test Redis connection
        redis_status = "ok"
        try:
            from .utils import get_memory
            get_memory("health_check")
        except Exception:
            redis_status = "degraded"
        
        health_status = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "checks": {
                "redis": redis_status,
                "openai": "ok" if openai_configured else "error",
                "google_sheets": "ok" if sheets_configured else "error", 
                "whatsapp": "ok" if whatsapp_configured else "error"
            }
        }
        
        # Si algún check falla, cambiar status general
        if any(status == "error" for status in health_status["checks"].values()):
            health_status["status"] = "degraded"
            
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2024-01-01T00:00:00Z"
        }


@app.post("/webhook", status_code=200)
async def webhook_evolution(request: Request):
    """Webhook para Evolution API (formato original)."""
    try:
        event_json = await request.json()
        logger.info(f"Received Evolution webhook: {event_json}")

        # Solo reaccionamos a MESSAGES_UPSERT o messages.upsert
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
        
        # Enviar respuesta usando Evolution API
        await send_whatsapp_message(chat_id, reply_text)
        logger.info("Message sent successfully via Evolution API")

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
        # Obtener datos del formulario
        form_data = {
            "Body": Body,
            "From": From,
            "To": To,
            "MessageSid": MessageSid
        }
        
        logger.info(f"Received Twilio webhook: {form_data}")
        
        # Validar webhook (deshabilitado para desarrollo/testing)
        # request_url = str(request.url)
        # if x_twilio_signature and not validate_twilio_webhook(request_url, x_twilio_signature, form_data):
        #     logger.warning("⚠️ Webhook de Twilio no válido")
        #     return PlainTextResponse("Unauthorized", status_code=401)
        logger.info("🔧 Validación de webhook omitida para desarrollo")
        
        # Extraer texto y chat_id
        user_text = extract_text_from_twilio_event(form_data)
        if not user_text:
            logger.info("No text found in Twilio message")
            return PlainTextResponse("OK")
        
        chat_id = get_twilio_chat_id(form_data)
        logger.info(f"Processing Twilio message: '{user_text}' from {chat_id}")
        
        # Procesar mensaje
        reply_text = process(user_text, chat_id)
        logger.info(f"Generated reply: {reply_text[:100]}...")
        
        # Responder usando TwiML
        twiml_response = create_twilio_response(reply_text)
        logger.info("Response sent via Twilio TwiML")
        
        return PlainTextResponse(twiml_response, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Twilio webhook error: {str(e)}", exc_info=True)
        return PlainTextResponse("Error", status_code=500)


async def send_whatsapp_message(to_number: str, text: str):
    """Envía mensaje usando el proveedor configurado."""
    if WHATSAPP_PROVIDER == "twilio" and is_twilio_configured():
        success = await send_twilio_whatsapp_message(to_number, text)
        if not success:
            logger.error("Failed to send via Twilio, falling back to Evolution API")
            await send_evolution_message(to_number, text)
    else:
        await send_evolution_message(to_number, text)


async def send_evolution_message(to_number: str, text: str):
    """Envía mensaje usando Evolution API."""
    url = f"{EVO_URL}/message/sendText/{INSTANCE_ID}"
    logger.info(f"Sending message to URL: {url}")
    logger.info(f"EVO_URL: {EVO_URL}")
    logger.info(f"INSTANCE_ID: {INSTANCE_ID}")

    payload: Dict[str, Any] = {
        "number": to_number,
        "text": text[:4096],
        "options": {"delay": 1200, "presence": "composing"},
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=HEADERS, json=payload)
        if r.status_code >= 400:
            logger.error("Evolution send error %s %s", r.status_code, r.text)