import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

# Cargar variables de entorno
load_dotenv(Path(__file__).parent.parent / ".env")

# Configurar logging
logger = logging.getLogger(__name__)

# Configuración de Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")  # Ej: "whatsapp:+14155238886"

# Inicializar cliente de Twilio
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("✅ Cliente de Twilio inicializado correctamente")
else:
    logger.warning("⚠️ Credenciales de Twilio no configuradas")


def is_twilio_configured() -> bool:
    """Verifica si Twilio está configurado correctamente."""
    return twilio_client is not None and TWILIO_WHATSAPP_NUMBER is not None


async def send_twilio_whatsapp_message(to_number: str, message: str) -> bool:
    """
    Envía un mensaje de WhatsApp usando Twilio.
    
    Args:
        to_number: Número de teléfono del destinatario (formato: +1234567890)
        message: Texto del mensaje a enviar
        
    Returns:
        bool: True si el mensaje se envió correctamente, False en caso contrario
    """
    if not is_twilio_configured():
        logger.error("❌ Twilio no está configurado correctamente")
        return False
    
    try:
        # Asegurar formato correcto del número
        if not to_number.startswith("+"):
            to_number = "+" + to_number
        
        # Enviar mensaje
        message_instance = twilio_client.messages.create(
            body=message[:1600],  # Twilio tiene límite de 1600 caracteres
            from_=TWILIO_WHATSAPP_NUMBER,
            to=f"whatsapp:{to_number}"
        )
        
        logger.info(f"✅ Mensaje enviado vía Twilio. SID: {message_instance.sid}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error enviando mensaje vía Twilio: {str(e)}")
        return False


def create_twilio_response(message: str) -> str:
    """
    Crea una respuesta TwiML para Twilio.
    
    Args:
        message: Texto del mensaje de respuesta
        
    Returns:
        str: Respuesta TwiML formateada
    """
    response = MessagingResponse()
    response.message(message[:1600])  # Límite de caracteres de Twilio
    return str(response)


def validate_twilio_webhook(request_url: str, signature: str, params: dict) -> bool:
    """
    Valida que el webhook viene realmente de Twilio.
    
    Args:
        request_url: URL del webhook
        signature: Firma X-Twilio-Signature del header
        params: Parámetros del webhook
        
    Returns:
        bool: True si la firma es válida
    """
    if not TWILIO_AUTH_TOKEN:
        logger.warning("⚠️ No se puede validar webhook: TWILIO_AUTH_TOKEN no configurado")
        return True  # En desarrollo, permitir sin validación
    
    try:
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        return validator.validate(request_url, params, signature)
    except Exception as e:
        logger.error(f"❌ Error validando webhook de Twilio: {str(e)}")
        return False


# Función helper para logging de configuración
def log_twilio_config():
    """Registra el estado de la configuración de Twilio."""
    logger.info("🔧 Configuración de Twilio:")
    logger.info(f"   ACCOUNT_SID: {'✅ Configurado' if TWILIO_ACCOUNT_SID else '❌ No configurado'}")
    logger.info(f"   AUTH_TOKEN: {'✅ Configurado' if TWILIO_AUTH_TOKEN else '❌ No configurado'}")
    logger.info(f"   WHATSAPP_NUMBER: {TWILIO_WHATSAPP_NUMBER or '❌ No configurado'}")
    logger.info(f"   Cliente inicializado: {'✅ Sí' if twilio_client else '❌ No'}") 