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
    """Obtiene cliente Redis o None si no está configurado."""
    redis_url = os.getenv("REDIS_URL")
    
    if not redis_url:
        logger.info("🔄 Redis no configurado, usando memoria en RAM")
        return None
        
    try:
        client = Redis.from_url(redis_url)
        client.ping()
        logger.info("✅ Redis conectado exitosamente")
        return client
        
    except Exception as e:
        logger.error(f"❌ Error conectando a Redis: {e}")
        logger.info("🔄 Usando memoria en RAM como fallback")
        return None

# Inicializar Redis
redis_client = get_redis_client()
logger.info(f"💾 Sistema de memoria: {'Redis' if redis_client else 'RAM (fallback)'}")


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
    chat_id = remote.split("@")[0]
    logger.info(f"📱 Chat ID extraído de Evolution: '{remote}' -> '{chat_id}'")
    return chat_id


def get_twilio_chat_id(form_data: Dict[str, Any]) -> str:
    """Extrae el número de teléfono del webhook de Twilio."""
    from_number = form_data.get("From", "")
    # Remover el prefijo "whatsapp:" si está presente
    chat_id = from_number.replace("whatsapp:", "").replace("+", "")
    logger.info(f"📱 Chat ID extraído de Twilio: '{from_number}' -> '{chat_id}'")
    return chat_id


def get_memory(chat_id: str) -> List[Dict]:
    key = f"mem:{chat_id}"
    logger.info(f"🔍 Obteniendo memoria para chat_id: '{chat_id}' (key: '{key}')")
    
    if redis_client:
        try:
            data = redis_client.get(key)
            if data:
                history = json.loads(data)
                logger.info(f"✅ Memoria recuperada de Redis: {len(history)} mensajes")
                return history
            else:
                logger.info(f"📭 No hay memoria en Redis para key: '{key}'")
                return []
        except Exception as e:
            logger.error(f"❌ Error obteniendo memoria de Redis: {e}")
            
    # Fallback a memoria en RAM
    history = memory_fallback.get(key, [])
    logger.info(f"🔄 Usando memoria en RAM: {len(history)} mensajes")
    return history


def set_memory(chat_id: str, messages: List[Dict]):
    key = f"mem:{chat_id}"
    logger.info(f"💾 Guardando memoria para chat_id: '{chat_id}' (key: '{key}') - {len(messages)} mensajes")
    
    if redis_client:
        try:
            redis_client.setex(key, 14 * 24 * 3600, json.dumps(messages))
            logger.info(f"✅ Memoria guardada en Redis exitosamente")
            return
        except Exception as e:
            logger.error(f"❌ Error guardando memoria en Redis: {e}")
            
    # Fallback a memoria en RAM
    memory_fallback[key] = messages
    logger.info(f"🔄 Memoria guardada en RAM (total de chats: {len(memory_fallback)})")
    # Limpiar memoria vieja (mantener solo 100 chats)
    if len(memory_fallback) > 100:
        oldest_key = next(iter(memory_fallback))
        del memory_fallback[oldest_key]
        logger.info(f"🧹 Memoria vieja limpiada: {oldest_key}")