import json
import logging
import os
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv
from redis import Redis

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv(Path(__file__).parent.parent / ".env")

# Memoria en RAM como fallback
memory_fallback = {}

# Sistema de batching de mensajes
message_batches = {}  # chat_id -> {messages: [], last_update: timestamp, task: asyncio.Task}
BATCH_TIMEOUT = 20.0  # segundos de espera antes de procesar
MAX_BATCH_SIZE = 10  # máximo número de mensajes por batch

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


def extract_audio_from_event(event: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Intenta obtener información de audio (nota de voz) del mensaje Evolution.

    Retorna un dict con al menos: {"url": str, "mimetype": str} si encuentra audio.
    """
    try:
        data = event.get("data", {})
        msg_obj = data.get("message", {})

        # Casos comunes: audioMessage, voiceMessage, ptt (push-to-talk)
        for key in ["audioMessage", "voiceMessage", "ptt", "audio", "media"]:
            if key in msg_obj and isinstance(msg_obj[key], dict):
                audio_obj = msg_obj[key]
                url = audio_obj.get("url") or audio_obj.get("directPath") or audio_obj.get("mediaUrl")
                mimetype = audio_obj.get("mimetype") or audio_obj.get("mimeType") or "audio/ogg"
                if url:
                    return {"url": url, "mimetype": mimetype}

        # Búsqueda profunda de una URL de audio
        def _walk_and_find(obj: Any) -> Optional[Tuple[str, str]]:
            try:
                if isinstance(obj, dict):
                    # Si tiene mimetype de audio y url
                    mt = obj.get("mimetype") or obj.get("mimeType")
                    u = obj.get("url") or obj.get("mediaUrl") or obj.get("directPath")
                    if u and (mt and str(mt).startswith("audio/")):
                        return str(u), str(mt)
                    # Buscar recursivamente
                    for v in obj.values():
                        found = _walk_and_find(v)
                        if found:
                            return found
                elif isinstance(obj, list):
                    for v in obj:
                        found = _walk_and_find(v)
                        if found:
                            return found
            except Exception:
                return None
            return None

        found = _walk_and_find(msg_obj)
        if found:
            url, mimetype = found
            return {"url": url, "mimetype": mimetype}
    except Exception:
        pass
    return None


def extract_text_from_twilio_event(form_data: Dict[str, Any]) -> str | None:
    """Extrae el texto del mensaje de un webhook de Twilio."""
    return form_data.get("Body")


def extract_audio_from_twilio_event(form_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Obtiene datos de audio (nota de voz) desde el webhook de Twilio.

    Twilio envía: NumMedia, MediaUrl{N}, MediaContentType{N}
    Retorna {"url": str, "mimetype": str} si encuentra audio.
    """
    try:
        num_media = int(form_data.get("NumMedia", "0"))
    except Exception:
        num_media = 0

    if num_media <= 0:
        return None

    # Revisar el primer media que sea audio
    for i in range(num_media):
        url_key = f"MediaUrl{i}"
        type_key = f"MediaContentType{i}"
        url = form_data.get(url_key)
        ctype = form_data.get(type_key, "")
        if url and str(ctype).startswith("audio/"):
            return {"url": url, "mimetype": ctype}

    return None


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


class MessageBatcher:
    """Sistema de batching de mensajes para agrupar mensajes consecutivos."""
    
    def __init__(self):
        self.batches = {}  # chat_id -> {messages: [], last_update: timestamp, task: Optional[asyncio.Task]}
        self.processing_callbacks = {}  # chat_id -> callback function
    
    def add_message(self, chat_id: str, message: str, callback) -> bool:
        """
        Agrega un mensaje al batch y programa su procesamiento.
        
        Args:
            chat_id: ID del chat
            message: Mensaje del usuario
            callback: Función a llamar cuando se procese el batch
            
        Returns:
            True si el mensaje se agregó al batch, False si se procesó inmediatamente
        """
        current_time = time.time()
        
        # Si no hay batch activo para este chat, crear uno nuevo
        if chat_id not in self.batches:
            self.batches[chat_id] = {
                "messages": [],
                "last_update": current_time,
                "task": None
            }
            self.processing_callbacks[chat_id] = callback
        
        batch = self.batches[chat_id]
        batch["messages"].append(message)
        batch["last_update"] = current_time
        
        logger.info(f"📦 Mensaje agregado al batch para {chat_id}: '{message[:50]}...' (total: {len(batch['messages'])})")
        
        # Si alcanzamos el tamaño máximo, procesar inmediatamente
        if len(batch["messages"]) >= MAX_BATCH_SIZE:
            logger.info(f"🚀 Batch completo para {chat_id}, procesando inmediatamente")
            self._process_batch(chat_id)
            return False
        
        # Cancelar tarea anterior si existe
        if batch["task"] and not batch["task"].done():
            batch["task"].cancel()
            logger.debug(f"🔄 Tarea anterior cancelada para {chat_id}")
        
        # Programar nueva tarea
        batch["task"] = asyncio.create_task(self._schedule_batch_processing(chat_id))
        logger.debug(f"⏰ Tarea programada para {chat_id} en {BATCH_TIMEOUT} segundos")
        
        return True
    
    async def _schedule_batch_processing(self, chat_id: str):
        """Espera el timeout y luego procesa el batch."""
        try:
            await asyncio.sleep(BATCH_TIMEOUT)
            
            # Verificar si el batch aún existe y no ha sido procesado
            if chat_id in self.batches:
                batch = self.batches[chat_id]
                current_time = time.time()
                
                # Solo procesar si han pasado suficientes segundos desde el último mensaje
                if current_time - batch["last_update"] >= BATCH_TIMEOUT:
                    logger.info(f"⏰ Timeout alcanzado para {chat_id}, procesando batch")
                    self._process_batch(chat_id)
                else:
                    logger.debug(f"⏰ Timeout alcanzado pero batch actualizado recientemente para {chat_id}")
                    
        except asyncio.CancelledError:
            logger.debug(f"🔄 Tarea cancelada para {chat_id}")
        except Exception as e:
            logger.error(f"❌ Error en schedule_batch_processing para {chat_id}: {e}")
    
    def _process_batch(self, chat_id: str):
        """Procesa el batch de mensajes."""
        if chat_id not in self.batches:
            logger.warning(f"⚠️ No se encontró batch para {chat_id}")
            return
        
        batch = self.batches[chat_id]
        callback = self.processing_callbacks.get(chat_id)
        
        if not callback:
            logger.error(f"❌ No se encontró callback para {chat_id}")
            return
        
        # Combinar todos los mensajes en uno solo
        combined_message = self._combine_messages(batch["messages"])
        logger.info(f"🔄 Procesando batch para {chat_id}: {len(batch['messages'])} mensajes combinados")
        logger.debug(f"📝 Mensaje combinado: '{combined_message[:100]}...'")
        
        # Limpiar batch
        del self.batches[chat_id]
        if chat_id in self.processing_callbacks:
            del self.processing_callbacks[chat_id]
        
        # Procesar el mensaje combinado
        try:
            # Crear una tarea asíncrona para ejecutar el callback
            asyncio.create_task(self._execute_callback(callback, combined_message))
        except Exception as e:
            logger.error(f"❌ Error procesando batch para {chat_id}: {e}")
    
    async def _execute_callback(self, callback, combined_message):
        """Ejecuta el callback de manera asíncrona."""
        try:
            await callback(combined_message)
        except Exception as e:
            logger.error(f"❌ Error ejecutando callback: {e}")
    
    def _combine_messages(self, messages: List[str]) -> str:
        """
        Combina múltiples mensajes en uno solo de manera inteligente.
        
        Estrategias:
        1. Si son saludos + solicitud, combinar naturalmente
        2. Si son frases incompletas, unirlas
        3. Si son mensajes completos, separar con espacios
        """
        if len(messages) == 1:
            return messages[0]
        
        combined = []
        current_phrase = []
        
        for i, message in enumerate(messages):
            message = message.strip()
            
            # Detectar saludos
            if message.lower() in ["hola", "buenos días", "buenas", "buenas tardes", "buenas noches", "muchas gracias", "gracias"]:
                if current_phrase:
                    combined.append(" ".join(current_phrase))
                    current_phrase = []
                combined.append(message)
                continue
            
            # Detectar frases incompletas (terminan con preposiciones, artículos, etc.)
            incomplete_endings = ["de", "en", "con", "para", "por", "sin", "sobre", "entre", "hacia", "hasta", "desde", "durante", "mediante", "según", "un", "una", "el", "la", "los", "las", "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas", "aquel", "aquella", "aquellos", "aquellas"]
            
            if any(message.lower().endswith(f" {ending}") for ending in incomplete_endings):
                current_phrase.append(message)
            else:
                current_phrase.append(message)
                if current_phrase:
                    combined.append(" ".join(current_phrase))
                    current_phrase = []
        
        # Agregar cualquier frase pendiente
        if current_phrase:
            combined.append(" ".join(current_phrase))
        
        result = " ".join(combined)
        logger.debug(f"🔗 Mensajes combinados: {messages} -> '{result}'")
        return result
    
    def get_batch_status(self, chat_id: str) -> Optional[Dict]:
        """Obtiene el estado actual del batch para un chat."""
        if chat_id not in self.batches:
            return None
        
        batch = self.batches[chat_id]
        return {
            "message_count": len(batch["messages"]),
            "last_update": batch["last_update"],
            "time_since_last": time.time() - batch["last_update"],
            "messages": batch["messages"]
        }
    
    def force_process(self, chat_id: str):
        """Fuerza el procesamiento inmediato del batch."""
        if chat_id in self.batches:
            logger.info(f"⚡ Forzando procesamiento de batch para {chat_id}")
            self._process_batch(chat_id)


# Instancia global del batcher
message_batcher = MessageBatcher()