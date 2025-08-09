import json
import logging
import os
import asyncio
from pathlib import Path
from typing import Dict, Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, Header
from fastapi.responses import PlainTextResponse

from .mcp_gateway import process
from .utils import (
    extract_text_from_event,
    extract_audio_from_event,
    get_chat_id,
    extract_text_from_twilio_event,
    extract_audio_from_twilio_event,
    get_twilio_chat_id,
    message_batcher,
)
import openai
from io import BytesIO
from .twilio_client import (
    send_twilio_whatsapp_message, 
    send_typing_indicator,
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
TRANSCRIPTION_MODEL = os.getenv("AUDIO_TRANSCRIPTION_MODEL", "whisper-1")



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
                "batch_timeout": 20.0,
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


@app.post("/test/typing")
async def test_typing_indicator(request: Request):
    """Endpoint de prueba para testing del typing indicator."""
    try:
        data = await request.json()
        to_number = data.get("number")
        message = data.get("message", "Mensaje de prueba")
        
        if not to_number:
            return {"error": "Se requiere el número de teléfono"}
        
        logger.info(f"🧪 Testing typing indicator para {to_number}")
        
        if WHATSAPP_PROVIDER == "evolution":
            await send_evolution_typing_indicator(to_number, message)
            return {"success": True, "message": "Typing indicator enviado (Evolution API)"}
        else:
            await send_typing_indicator(to_number, 3)
            return {"success": True, "message": "Typing indicator enviado (Twilio)"}
            
    except Exception as e:
        logger.error(f"Error en test typing: {str(e)}")
        return {"error": str(e)}


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

        # Si no hay texto, intentar extraer audio y transcribirlo
        if not user_text:
            audio_info = extract_audio_from_event(event_json)
            if audio_info:
                logger.info(f"🎙️ Audio detectado (Evolution): {audio_info}")
                try:
                    if "base64" in audio_info:
                        import base64
                        audio_bytes = base64.b64decode(audio_info["base64"])  # Ya decodificado
                    else:
                        audio_bytes = await download_media(audio_info["url"], provider="evolution")
                    # Elegir extensión adecuada a partir del mimetype
                    mt = audio_info.get("mimetype", "audio/ogg")
                    ext = "ogg"
                    if "/" in mt:
                        ext = mt.split("/")[-1]
                        if ";" in ext:
                            ext = ext.split(";")[0]
                    filename = f"note.{ext or 'ogg'}"
                    user_text = await transcribe_audio(audio_bytes, filename=filename, mimetype=mt)
                    logger.info(f"📝 Transcripción obtenida: '{user_text}'")
                except Exception as e:
                    logger.error(f"❌ Error transcribiendo audio Evolution: {str(e)}")
                    user_text = None
        
        if not user_text:
            logger.info("No text or audio to process")
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
    Body: str = Form(None),
    From: str = Form(None),
    To: str = Form(None),
    MessageSid: str = Form(None),
    x_twilio_signature: str = Header(None, alias="X-Twilio-Signature")
):
    """Webhook para Twilio WhatsApp."""
    try:
        form = await request.form()
        form_data = {k: v for k, v in form.items()}
        # Asegurar claves principales si FastAPI no las mapeó
        if Body is not None:
            form_data.setdefault("Body", Body)
        if From is not None:
            form_data.setdefault("From", From)
        if To is not None:
            form_data.setdefault("To", To)
        if MessageSid is not None:
            form_data.setdefault("MessageSid", MessageSid)

        logger.info(f"Received Twilio webhook: {form_data}")
        
        # Validar webhook en producción
        request_url = str(request.url)
        # Temporalmente deshabilitado para Railway
        # if x_twilio_signature and not validate_twilio_webhook(request_url, x_twilio_signature, form_data):
        #     logger.warning("Invalid Twilio webhook signature")
        #     return PlainTextResponse("Unauthorized", status_code=401)
        logger.info("⚠️ Webhook signature validation temporarily disabled")
        
        user_text = extract_text_from_twilio_event(form_data)
        # Si no hay texto, intentar transcribir audio
        if not user_text:
            audio_info = extract_audio_from_twilio_event(form_data)
            if audio_info:
                logger.info(f"🎙️ Audio detectado (Twilio): {audio_info}")
                try:
                    audio_bytes = await download_media(audio_info["url"], provider="twilio")
                    mt = audio_info.get("mimetype", "audio/ogg")
                    ext = "ogg"
                    if "/" in mt:
                        ext = mt.split("/")[-1]
                        if ";" in ext:
                            ext = ext.split(";")[0]
                    filename = f"note.{ext or 'ogg'}"
                    user_text = await transcribe_audio(audio_bytes, filename=filename, mimetype=mt)
                    logger.info(f"📝 Transcripción obtenida (Twilio): '{user_text}'")
                except Exception as e:
                    logger.error(f"❌ Error transcribiendo audio Twilio: {str(e)}")
                    user_text = None
        if not user_text:
            logger.info("No text or audio found in Twilio message")
            return PlainTextResponse("OK")
        
        chat_id = get_twilio_chat_id(form_data)
        logger.info(f"Processing Twilio message: '{user_text}' from {chat_id}")
        
        # Para Twilio, respondemos con TwiML
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


async def download_media(url: str, provider: str = "evolution") -> bytes:
    """Descarga bytes de un media URL, manejando autenticación por proveedor."""
    try:
        headers = {}
        auth = None
        if provider == "evolution":
            headers["apikey"] = EVOLUTION_API_KEY or ""
        elif provider == "twilio":
            # Twilio media requiere auth básica con SID y TOKEN
            from .twilio_client import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
            auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url, headers=headers, auth=auth)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        raise Exception(f"Error descargando media: {str(e)}")


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg", mimetype: str = "audio/ogg") -> str:
    """Transcribe audio a texto usando OpenAI Whisper (o modelo configurado)."""
    try:
        # OpenAI requiere archivo con nombre válido
        file_io = BytesIO(audio_bytes)
        file_io.name = filename  # Establece nombre de archivo para el multipart

        # API de transcripciones
        result = openai.audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=file_io,
            response_format="json",
        )

        text = getattr(result, "text", None)
        if not text:
            raise Exception("Respuesta de transcripción sin texto")
        return text.strip()
    except Exception as e:
        raise Exception(f"Error en transcripción: {str(e)}")


async def send_whatsapp_message(to_number: str, text: str, show_typing: bool = False):
    """Envía mensaje usando el proveedor configurado."""
    if WHATSAPP_PROVIDER == "twilio":
        success = await send_twilio_whatsapp_message(to_number, text, show_typing)
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
    
    # Verificar si es el primer mensaje del batch (para mostrar typing inmediatamente)
    is_first_message = chat_id not in message_batcher.batches
    
    # Agregar mensaje al batch
    was_batched = message_batcher.add_message(chat_id, user_text, process_combined_message)
    
    if was_batched:
        logger.info(f"📦 Mensaje agregado al batch para {chat_id}, esperando más mensajes...")
        
        # Si es el primer mensaje, mostrar indicador de typing inmediatamente
        if is_first_message:
            logger.info(f"⌨️ Mostrando indicador de typing inmediatamente para {chat_id}")
            try:
                # Enviar indicador visual de typing (sin esperar respuesta de IA)
                if WHATSAPP_PROVIDER == "evolution":
                    await send_evolution_typing_indicator(chat_id, "Procesando tu mensaje...")
                else:
                    await send_typing_indicator(chat_id, 3)
                logger.info(f"✅ Indicador de typing enviado para {chat_id}")
            except Exception as e:
                logger.error(f"❌ Error enviando indicador de typing: {str(e)}")
    else:
        logger.info(f"🚀 Mensaje procesado inmediatamente para {chat_id}")


async def send_evolution_message(to_number: str, text: str, show_typing: bool = False):
    """Envía mensaje usando Evolution API - Código simplificado y directo."""
    if not (EVO_URL and INSTANCE_ID):
        raise Exception("Evolution API not properly configured")
    
    # Formatear número para Evolution API
    formatted_number = to_number
    if not to_number.startswith("+"):
        formatted_number = "+" + to_number
    
    # NOTA: show_typing ahora es False por defecto porque el indicador se envía inmediatamente
    # cuando llega el primer mensaje, no cuando se procesa la respuesta
    
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


async def send_evolution_typing_indicator(to_number: str, message: str):
    """Envía el indicador de 'escribiendo...' usando Evolution API."""
    if not (EVO_URL and INSTANCE_ID):
        logger.error("❌ Evolution API no está configurado correctamente")
        return
    
    try:
        # Calcular duración basada en la longitud del mensaje (aproximadamente 150 palabras por minuto)
        words = len(message.split())
        typing_duration = min(max(words / 2.5, 1), 5)  # Entre 1 y 5 segundos
        
        logger.info(f"⌨️ Enviando indicador visual de 'escribiendo...' a {to_number} por {typing_duration} segundos")
        
        # Evolution API no tiene endpoints de typing indicator nativos
        # Implementamos una solución visual: enviar un mensaje temporal
        typing_message = "escribiendo..."
        
        # Enviar mensaje de typing
        await send_evolution_message_internal(to_number, typing_message, show_typing=False)
        
        # Esperar el tiempo calculado
        await asyncio.sleep(typing_duration)
        
        # NOTA: No enviamos mensaje vacío para "borrar" - el mensaje de typing permanece
        # y será reemplazado por la respuesta real del bot
        
        logger.info("✅ Indicador visual de typing completado")
                
    except Exception as e:
        logger.error(f"❌ Error en indicador visual de typing: {str(e)}")
        # Simular el tiempo de escritura de todas formas
        words = len(message.split())
        typing_duration = min(max(words / 2.5, 1), 5)
        await asyncio.sleep(typing_duration)


async def send_evolution_message_internal(to_number: str, text: str, show_typing: bool = False):
    """Envía mensaje usando Evolution API (función interna sin typing)."""
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
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Mensaje interno enviado: {text[:50]}...")
                return
            else:
                error_msg = f"Evolution API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
    except Exception as e:
        logger.error(f"Failed to send internal message: {str(e)}")
        raise Exception(f"Evolution API request failed: {str(e)}")


