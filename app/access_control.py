import logging
import time
from typing import List, Set
import gspread
from .tools import client, SHEET_ID

# Configurar logging
logger = logging.getLogger(__name__)

# Configuración de caché
CACHE_DURATION = 300  # 5 minutos en segundos
_allowed_users_cache: Set[str] = set()
_last_cache_update = 0

ALLOWED_USERS_TAB = "AllowedUsers"

def get_allowed_users() -> Set[str]:
    """
    Obtiene la lista de usuarios permitidos desde Google Sheets.
    Utiliza caché para evitar exceso de llamadas a la API.
    """
    global _allowed_users_cache, _last_cache_update
    
    current_time = time.time()
    
    # Si el caché es válido, retornarlo
    if current_time - _last_cache_update < CACHE_DURATION and _allowed_users_cache:
        return _allowed_users_cache
        
    logger.info("🔄 Actualizando lista de usuarios permitidos desde Google Sheets...")
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet(ALLOWED_USERS_TAB)
        
        # Asumimos que los números están en la primera columna (A)
        # Obtenemos todos los valores de la columna 1
        numbers = sheet.col_values(1)
        
        # Normalizar números: eliminar espacios, guiones, etc.
        normalized_numbers = set()
        for num in numbers:
            # Limpieza básica
            clean_num = str(num).strip().replace(" ", "").replace("-", "").replace("+", "")
            if clean_num:
                normalized_numbers.add(clean_num)
                
        _allowed_users_cache = normalized_numbers
        _last_cache_update = current_time
        
        logger.info(f"✅ Lista de usuarios actualizada: {len(_allowed_users_cache)} números permitidos")
        return _allowed_users_cache
        
    except gspread.WorksheetNotFound:
        logger.error(f"❌ No se encontró la pestaña '{ALLOWED_USERS_TAB}' en el Google Sheet")
        # Si no existe la pestaña, por seguridad retornamos set vacío (nadie entra)
        # O podríamos retornar el caché anterior si existe
        return _allowed_users_cache
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo usuarios permitidos: {str(e)}")
        return _allowed_users_cache

def check_user_access(phone_number: str) -> bool:
    """
    Verifica si un número de teléfono tiene acceso al sistema.
    
    Args:
        phone_number: Número de teléfono (chat_id)
        
    Returns:
        True si el usuario está permitido, False en caso contrario.
    """
    # Normalizar el número entrante para comparar
    # El chat_id suele venir limpio (ej: 56912345678), pero por si acaso
    clean_number = phone_number.replace("+", "").strip()
    
    allowed_users = get_allowed_users()
    
    is_allowed = clean_number in allowed_users
    
    if not is_allowed:
        logger.warning(f"⛔ Acceso denegado para el usuario: {clean_number}")
    else:
        logger.info(f"✅ Acceso concedido para el usuario: {clean_number}")
        
    return is_allowed
