import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv
from redis import Redis

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv(Path(__file__).parent.parent / ".env")

# Memoria en RAM como fallback
memory_fallback = {}

def get_redis_client():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    logger.info(f"🔌 Intentando conectar a Redis: {redis_url[:20]}...")
    
    try:
        # Si la URL no tiene esquema, agregarle redis://
        if redis_url and not redis_url.startswith(('redis://', 'rediss://', 'unix://')):
            logger.info(f"🔧 Agregando esquema redis:// a URL: {redis_url}")
            redis_url = f"redis://{redis_url}"
        
        client = Redis.from_url(redis_url)
        # Probar conexión
        client.ping()
        logger.info("✅ Redis conectado exitosamente")
        return client
        
    except Exception as e:
        logger.error(f"❌ Error conectando a Redis: {e}")
        logger.info("🔄 Usando memoria en RAM como fallback")
        return None

redis_client = get_redis_client()


def extract_text_from_event(event: Dict[str, Any]) -> str | None:
    """Intenta obtener el texto del mensaje entrante."""
    data = event.get("data", {})
    msg_obj = data.get("message", {})
    # Formatos posibles: conversation (texto plano) o extendedTextMessage
    if "conversation" in msg_obj:
        return msg_obj["conversation"]
    if "extendedTextMessage" in msg_obj:
        return msg_obj["extendedTextMessage"].get("text")
    return None


def extract_text_from_twilio_event(form_data: Dict[str, Any]) -> str | None:
    """Extrae el texto del mensaje de un webhook de Twilio."""
    return form_data.get("Body")


def get_chat_id(event: Dict[str, Any]) -> str:
    """Extrae el número E164 de remoteJid."""
    remote = event.get("data", {}).get("key", {}).get("remoteJid", "")
    return remote.split("@")[0]


def get_twilio_chat_id(form_data: Dict[str, Any]) -> str:
    """Extrae el número de teléfono del webhook de Twilio."""
    from_number = form_data.get("From", "")
    # Remover el prefijo "whatsapp:" si está presente
    return from_number.replace("whatsapp:", "").replace("+", "")


def get_memory(chat_id: str) -> List[Dict]:
    key = f"mem:{chat_id}"
    
    if redis_client:
        try:
            data = redis_client.get(key)
            return json.loads(data) if data else []
        except Exception as e:
            logger.error(f"Error obteniendo memoria de Redis: {e}")
            
    # Fallback a memoria en RAM
    return memory_fallback.get(key, [])


def set_memory(chat_id: str, messages: List[Dict]):
    key = f"mem:{chat_id}"
    
    if redis_client:
        try:
            redis_client.setex(key, 14 * 24 * 3600, json.dumps(messages))
            return
        except Exception as e:
            logger.error(f"Error guardando memoria en Redis: {e}")
            
    # Fallback a memoria en RAM
    memory_fallback[key] = messages
    # Limpiar memoria vieja (mantener solo 100 chats)
    if len(memory_fallback) > 100:
        oldest_key = next(iter(memory_fallback))
        del memory_fallback[oldest_key]