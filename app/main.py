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
    get_twilio_chat_id,
    message_batcher
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


@app.get("/batches")
async def get_batch_status():
    """Endpoint para monitorear el estado de los batches de mensajes."""
    try:
        batches_info = {}
        for chat_id in message_batcher.batches:
            status = message_batcher.get_batch_status(chat_id)
            if status:
                batches_info[chat_id] = status
        
        return {
            "active_batches": len(batches_info),
            "batches": batches_info,
            "config": {
                "batch_timeout": 3.0,
                "max_batch_size": 10
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting batch status: {str(e)}")
        return {"error": str(e)}


@app.post("/batches/{chat_id}/force")
async def force_process_batch(chat_id: str):
    """Fuerza el procesamiento inmediato de un batch específico."""
    try:
        if chat_id not in message_batcher.batches:
            return {"error": f"No hay batch activo para {chat_id}"}
        
        message_batcher.force_process(chat_id)
        return {"success": True, "message": f"Batch forzado para {chat_id}"}
        
    except Exception as e:
        logger.error(f"Error forcing batch for {chat_id}: {str(e)}")
        return {"error": str(e)}


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
        
        await process_message_with_batching(chat_id, user_text)

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
        
        # Para Twilio, necesitamos manejar la respuesta de manera diferente
        # porque no podemos usar async/await en el webhook
        try:
            reply_text = process(user_text, chat_id)
            logger.info(f"Generated reply: {reply_text[:100]}...")
            
            twiml_response = create_twilio_response(reply_text)
            logger.info("Response sent via Twilio TwiML")
            
            return PlainTextResponse(twiml_response, media_type="application/xml")
            
        except Exception as e:
            logger.error(f"❌ Error processing Twilio message: {str(e)}")
            error_response = create_twilio_response("Lo siento, hubo un error procesando tu mensaje. ¿Podrías intentarlo de nuevo?")
            return PlainTextResponse(error_response, media_type="application/xml")
        
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


async def process_message_with_batching(chat_id: str, user_text: str):
    """Procesa un mensaje usando el sistema de batching."""
    
    async def process_combined_message(combined_text: str):
        """Callback que se ejecuta cuando se procesa el batch."""
        logger.info(f"🔄 Procesando mensaje combinado para {chat_id}: '{combined_text[:100]}...'")
        
        try:
            reply_text = process(combined_text, chat_id)
            logger.info(f"💬 Respuesta generada para {chat_id}: {reply_text[:100]}...")
            
            await send_whatsapp_message(chat_id, reply_text)
            logger.info(f"✅ Mensaje enviado exitosamente a {chat_id}")
            
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje combinado para {chat_id}: {str(e)}")
            error_message = "Lo siento, hubo un error procesando tu mensaje. ¿Podrías intentarlo de nuevo?"
            await send_whatsapp_message(chat_id, error_message)
    
    # Agregar mensaje al batch
    was_batched = message_batcher.add_message(chat_id, user_text, process_combined_message)
    
    if was_batched:
        logger.info(f"📦 Mensaje agregado al batch para {chat_id}, esperando más mensajes...")
        # No enviar respuesta inmediata, esperar el batch
    else:
        logger.info(f"🚀 Mensaje procesado inmediatamente para {chat_id}")


async def send_evolution_message(to_number: str, text: str):
    """Envía mensaje usando Evolution API - Código simplificado y directo."""
    if not (EVO_URL and INSTANCE_ID):
        raise Exception("Evolution API not properly configured")
    
    # Formatear número para Evolution API
    formatted_number = to_number
    if not to_number.startswith("+"):
        formatted_number = "+" + to_number
    
    # Endpoint correcto según documentación oficial de Evolution API
    url = f"{EVO_URL}/message/sendText/{INSTANCE_ID}"
    
    # Headers correctos
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    # Payload simple y directo
    payload = {
        "number": formatted_number,
        "text": text[:4096]
    }
    
    logger.info(f"Sending message to Evolution API:")
    logger.info(f"  URL: {url}")
    logger.info(f"  Number: {formatted_number}")
    logger.info(f"  Text length: {len(text)}")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            logger.info(f"Evolution API response: {response.status_code}")
            
            if response.status_code in [200, 201]:
                logger.info("✅ Message sent successfully!")
                return
            else:
                error_msg = f"Evolution API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")
        raise Exception(f"Evolution API request failed: {str(e)}")