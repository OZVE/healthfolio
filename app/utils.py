import json
import os
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv
from redis import Redis

# Cargar variables de entorno
load_dotenv(Path(__file__).parent.parent / ".env")

redis_client = Redis.from_url(os.getenv("REDIS_URL") or "redis://localhost:6379/0")


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
    data = redis_client.get(key)
    return json.loads(data) if data else []


def set_memory(chat_id: str, messages: List[Dict]):
    key = f"mem:{chat_id}"
    redis_client.setex(key, 14 * 24 * 3600, json.dumps(messages))