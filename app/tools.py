import logging
import os
import json
from pathlib import Path
from typing import List, Dict
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv(Path(__file__).parent.parent / ".env")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

def load_google_credentials():
    """Carga credenciales de Google Cloud desde variable de entorno."""
    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    
    if not service_account_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON es obligatorio")
    
    if service_account_json.startswith("{"):
        # Es JSON directo en variable de entorno
        logger.info("🔐 Cargando credenciales desde variable de entorno")
        try:
            service_account_info = json.loads(service_account_json)
            return Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        except json.JSONDecodeError as e:
            raise ValueError(f"GOOGLE_SERVICE_ACCOUNT_JSON no es un JSON válido: {e}")
    else:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON debe contener el JSON completo de las credenciales")

# Inicializar cliente de Google Sheets
creds = load_google_credentials()
client = gspread.authorize(creds)

SHEET_ID = os.getenv("SHEET_ID")
if not SHEET_ID:
    raise ValueError("SHEET_ID es obligatorio")

SHEET_TAB = os.getenv("SHEET_TAB", "directory")

def normalize_specialty_search(specialty: str) -> List[str]:
    """
    Genera variaciones comunes de especialidades médicas.
    Esto complementa las instrucciones del system prompt.
    """
    specialty_lower = specialty.lower().strip()
    
    # Mapeo básico de especialidades comunes
    variations = [specialty_lower]
    
    # Generar variaciones automáticas basadas en patrones comunes
    if "ía" in specialty_lower:
        # kinesiología -> kinesiologo, kinesiologa
        base = specialty_lower.replace("ía", "")
        variations.extend([base + "ologo", base + "ologa", base + "ologo", base + "ologa"])
    
    if "logia" in specialty_lower:
        # cardiologia -> cardiologo, cardióloga  
        base = specialty_lower.replace("logia", "")
        variations.extend([base + "logo", base + "loga", base + "ólogo", base + "óloga"])
    
    # Mapeo basado en los datos REALES de la base de datos
    # Títulos reales: Enfermera, Kinesiólogo, Médico, Nutricionista, TENS
    # Especialidades reales: Atención Domiciliaria, Cardiología, Cuidados Intensivos, Geriatría, Oncología, Pediatría, Salud Mental, Traumatología, Urgencias
    
    specialty_mappings = {
        # Kinesiología/Fisioterapia -> buscar título "Kinesiólogo"
        "kinesiología": ["kinesiólogo"],
        "kinesiologia": ["kinesiólogo"], 
        "kinesiologo": ["kinesiólogo"],
        "kinesiologa": ["kinesiólogo"],
        "kinesiólogo": ["kinesiólogo"],
        "kinesióloga": ["kinesiólogo"],
        "kinesiologos": ["kinesiólogo"],
        "kinesiólogos": ["kinesiólogo"],
        "fisioterapia": ["kinesiólogo"],
        "fisioterapeuta": ["kinesiólogo"],
        "rehabilitacion": ["kinesiólogo"],
        
        # Cardiología -> especialidad "Cardiología" + título "Médico"
        "cardiología": ["cardiología", "médico"],
        "cardiologia": ["cardiología", "médico"],
        "cardiologo": ["cardiología", "médico"],
        "cardióloga": ["cardiología", "médico"],
        "cardiólogo": ["cardiología", "médico"],
        "corazón": ["cardiología", "médico"],
        
        # Pediatría -> especialidad "Pediatría" + título "Médico"  
        "pediatría": ["pediatría", "médico"],
        "pediatria": ["pediatría", "médico"],
        "pediatra": ["pediatría", "médico"],
        "pediatras": ["pediatría", "médico"],
        "niños": ["pediatría", "médico"],
        "niño": ["pediatría", "médico"],
        
        # Nutrición -> título "Nutricionista"
        "nutrición": ["nutricionista"],
        "nutricion": ["nutricionista"],
        "nutricionista": ["nutricionista"],
        "nutrologo": ["nutricionista"],
        "nutrologa": ["nutricionista"],
        "dieta": ["nutricionista"],
        "alimentacion": ["nutricionista"],
        
        # Enfermería -> título "Enfermera" + "TENS"
        "enfermería": ["enfermera", "tens"],
        "enfermeria": ["enfermera", "tens"],
        "enfermera": ["enfermera", "tens"],
        "enfermero": ["enfermera", "tens"],
        "tens": ["tens", "enfermera"],
        
        # Medicina General -> título "Médico"
        "medicina general": ["médico"],
        "medico general": ["médico"],
        "medico": ["médico"],
        "médico": ["médico"],
        "doctor": ["médico"],
        "doctora": ["médico"],
        
        # Geriatría -> especialidad "Geriatría"
        "geriatría": ["geriatría"],
        "geriatria": ["geriatría"], 
        "adulto mayor": ["geriatría"],
        "tercera edad": ["geriatría"],
        
        # Traumatología -> especialidad "Traumatología"
        "traumatología": ["traumatología"],
        "traumatologia": ["traumatología"],
        "traumatologo": ["traumatología"],
        "traumatóloga": ["traumatología"],
        "huesos": ["traumatología"],
        "fracturas": ["traumatología"],
        
        # Oncología -> especialidad "Oncología"
        "oncología": ["oncología"],
        "oncologia": ["oncología"],
        "oncologo": ["oncología"],
        "oncóloga": ["oncología"],
        "cancer": ["oncología"],
        "cáncer": ["oncología"],
        
        # Salud Mental -> especialidad "Salud Mental"
        "salud mental": ["salud mental"],
        "psicología": ["salud mental"],
        "psicologia": ["salud mental"],
        "psicologo": ["salud mental"],
        "psicologa": ["salud mental"],
        "psiquiatra": ["salud mental"],
        "depresion": ["salud mental"],
        "ansiedad": ["salud mental"],
        
        # Urgencias -> especialidad "Urgencias"
        "urgencias": ["urgencias"],
        "urgencia": ["urgencias"],
        "emergencia": ["urgencias"],
        "emergencias": ["urgencias"],
        
        # Cuidados Intensivos -> especialidad "Cuidados Intensivos"
        "cuidados intensivos": ["cuidados intensivos"],
        "uci": ["cuidados intensivos"],
        "intensivos": ["cuidados intensivos"],
        
        # Atención Domiciliaria -> especialidad "Atención Domiciliaria"
        "atención domiciliaria": ["atención domiciliaria"],
        "atencion domiciliaria": ["atención domiciliaria"],
        "domiciliaria": ["atención domiciliaria"],
        "domicilio": ["atención domiciliaria"],
        "casa": ["atención domiciliaria"],
    }
    
    if specialty_lower in specialty_mappings:
        variations.extend(specialty_mappings[specialty_lower])
    
    # Remover duplicados y mantener orden
    unique_variations = []
    for v in variations:
        if v not in unique_variations:
            unique_variations.append(v)
    
    logger.info(f"🔍 Variaciones de '{specialty}': {unique_variations}")
    return unique_variations

def normalize_city_search(city: str) -> List[str]:
    """
    Normaliza la búsqueda de ciudad para encontrar variaciones.
    """
    city_lower = city.lower().strip()
    
    # Crear variaciones de la ciudad
    variations = [city_lower]
    
    # Si contiene "los" o "las", también buscar sin esos artículos
    if city_lower.startswith("los "):
        variations.append(city_lower.replace("los ", ""))
    elif city_lower.startswith("las "):
        variations.append(city_lower.replace("las ", ""))
    elif city_lower.startswith("la "):
        variations.append(city_lower.replace("la ", ""))
    elif city_lower.startswith("el "):
        variations.append(city_lower.replace("el ", ""))
    
    # También buscar si alguien busca solo la palabra principal
    # Por ejemplo "lagos" debería encontrar "los lagos"
    if not any(article in city_lower for article in ["los ", "las ", "la ", "el "]):
        variations.extend([f"los {city_lower}", f"las {city_lower}", f"la {city_lower}", f"el {city_lower}"])
    
    logger.info(f"🏙️ Variaciones de ciudad para '{city}': {variations}")
    return variations

def normalize_availability_search(availability: str) -> List[str]:
    """
    Normaliza la búsqueda de disponibilidad para encontrar variaciones de días y horarios.
    """
    availability_lower = availability.lower().strip()
    
    # Crear variaciones de disponibilidad
    variations = [availability_lower]
    
    # Mapeo de días de la semana y horarios comunes
    availability_mappings = {
        # Días de la semana
        "lunes": ["lunes", "monday", "lun"],
        "martes": ["martes", "tuesday", "mar"],
        "miércoles": ["miércoles", "miercoles", "wednesday", "mié", "mie"],
        "miercoles": ["miércoles", "miercoles", "wednesday", "mié", "mie"],
        "jueves": ["jueves", "thursday", "jue"],
        "viernes": ["viernes", "friday", "vie"],
        "sábado": ["sábado", "sabado", "saturday", "sáb", "sab"],
        "sabado": ["sábado", "sabado", "saturday", "sáb", "sab"],
        "domingo": ["domingo", "sunday", "dom"],
        
        # Grupos de días
        "fin de semana": ["fin de semana", "fines de semana", "weekend", "sábado", "sabado", "domingo"],
        "fines de semana": ["fin de semana", "fines de semana", "weekend", "sábado", "sabado", "domingo"],
        "weekend": ["fin de semana", "fines de semana", "weekend", "sábado", "sabado", "domingo"],
        "entre semana": ["lunes", "martes", "miércoles", "miercoles", "jueves", "viernes"],
        "semana": ["lunes", "martes", "miércoles", "miercoles", "jueves", "viernes"],
        
        # Horarios
        "mañana": ["mañana", "morning", "am", "matutino"],
        "tarde": ["tarde", "afternoon", "pm", "vespertino"],
        "noche": ["noche", "evening", "night", "nocturno"],
        "madrugada": ["madrugada", "early morning", "dawn"],
        
        # Urgencias
        "urgencia": ["urgencia", "emergency", "24 horas", "24/7", "siempre"],
        "emergencia": ["urgencia", "emergency", "24 horas", "24/7", "siempre"],
        "24 horas": ["urgencia", "emergency", "24 horas", "24/7", "siempre"],
        "24/7": ["urgencia", "emergency", "24 horas", "24/7", "siempre"],
    }
    
    if availability_lower in availability_mappings:
        variations.extend(availability_mappings[availability_lower])
    
    # Remover duplicados y mantener orden
    unique_variations = []
    for v in variations:
        if v not in unique_variations:
            unique_variations.append(v)
    
    logger.info(f"🕐 Variaciones de disponibilidad para '{availability}': {unique_variations}")
    return unique_variations

def find_professionals(specialty: str, city: str, availability: str = None) -> List[Dict]:
    """Busca filas que coincidan con especialidad, ciudad y opcionalmente disponibilidad."""
    logger.info(f"📊 Conectando a Google Sheet ID: {SHEET_ID[:10]}...")
    logger.info(f"📊 Pestaña: {SHEET_TAB}")
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
        logger.info(f"✅ Conexión exitosa a Google Sheet")
        
        rows = sheet.get_all_records()
        logger.info(f"📊 Total de registros en el sheet: {len(rows)}")
        
        if len(rows) > 0:
            logger.info(f"📊 Columnas disponibles: {list(rows[0].keys())}")
            logger.info(f"📊 Primer registro como ejemplo: {rows[0]}")
        
        # Buscar coincidencias con mapeo inteligente
        search_params = f"specialty='{specialty}', city='{city}'"
        if availability:
            search_params += f", availability='{availability}'"
        logger.info(f"🔍 Buscando con parámetros: {search_params}")
        
        specialty_terms = normalize_specialty_search(specialty)
        city_terms = normalize_city_search(city)
        availability_terms = normalize_availability_search(availability) if availability else []
        
        matches = []
        
        for i, r in enumerate(rows):
            # Buscar cualquiera de los términos de especialidad en specialty y title
            specialty_text = str(r.get("specialty", "")).lower()
            title_text = str(r.get("title", "")).lower()
            
            # Buscar cualquier variación en specialty O en title
            specialty_match = any(term in specialty_text for term in specialty_terms)
            title_match = any(term in title_text for term in specialty_terms)
            
            # Combinar ambas búsquedas
            professional_match = specialty_match or title_match
            
            # Buscar cualquiera de los términos de ciudad
            coverage_area_text = str(r.get("coverage_area", "")).lower()
            city_match = any(term in coverage_area_text for term in city_terms)
            
            # Buscar disponibilidad si se especificó
            availability_match = True  # Por defecto True si no se especifica availability
            if availability:
                availability_text = str(r.get("availability", "")).lower()
                availability_match = any(term in availability_text for term in availability_terms)
                
                if not availability_match:
                    logger.info(f"🕐 No match de disponibilidad en fila {i+1}: '{availability_text}' no contiene ninguno de {availability_terms}")
            
            if professional_match and city_match and availability_match:
                logger.info(f"✅ Match completo encontrado en fila {i+1}: {r}")
                if specialty_match:
                    logger.info(f"✅ Specialty match: '{specialty_text}' contiene alguno de {specialty_terms}")
                if title_match:
                    logger.info(f"✅ Title match: '{title_text}' contiene alguno de {specialty_terms}")
                logger.info(f"✅ City match: '{coverage_area_text}' contiene alguno de {city_terms}")
                if availability:
                    logger.info(f"✅ Availability match: '{availability_text}' contiene alguno de {availability_terms}")
                matches.append(r)
            elif professional_match and city_match:
                logger.info(f"🔍 Professional y city match (pero no availability) en fila {i+1}: {r}")
            elif professional_match:
                logger.info(f"🔍 Professional match (pero no city/availability) en fila {i+1}: {r}")
            elif city_match:
                logger.info(f"🔍 City match (pero no professional/availability) en fila {i+1}: {r}")
        
        logger.info(f"📋 Total matches encontrados: {len(matches)}")
        return matches
        
    except Exception as e:
        logger.error(f"❌ Error accediendo a Google Sheet: {str(e)}")
        return []


def find_professional_by_name(name: str) -> Dict:
    """Busca un profesional específico por nombre para obtener sus datos de contacto y disponibilidad."""
    logger.info(f"👤 Buscando profesional específico por nombre: '{name}'")
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
        rows = sheet.get_all_records()
        
        logger.info(f"🔍 Buscando en {len(rows)} registros...")
        
        for i, r in enumerate(rows):
            professional_name = str(r.get("name", "")).lower()
            if name.lower() in professional_name or professional_name in name.lower():
                # Extraer información específica del profesional
                availability = r.get("availability", "No especificada")
                specialty = r.get("specialty", "No especificada")
                title = r.get("title", "No especificado")
                coverage_area = r.get("coverage_area", "No especificada")
                
                logger.info(f"✅ Profesional encontrado en fila {i+1}:")
                logger.info(f"   📋 Nombre: {r.get('name', 'N/A')}")
                logger.info(f"   🏥 Especialidad: {specialty}")
                logger.info(f"   🎓 Título: {title}")
                logger.info(f"   📍 Área de cobertura: {coverage_area}")
                logger.info(f"   📅 Disponibilidad: {availability}")
                logger.info(f"   📞 Contacto: {r.get('phone', 'N/A')}")
                logger.info(f"   📧 Email: {r.get('email', 'N/A')}")
                
                # Asegurar que availability esté incluida en el resultado
                if 'availability' not in r:
                    logger.warning(f"⚠️ Columna 'availability' no encontrada en el registro")
                    r['availability'] = "No especificada"
                
                return r
        
        logger.info(f"❌ No se encontró profesional con nombre: '{name}'")
        return {}
        
    except Exception as e:
        logger.error(f"❌ Error buscando profesional por nombre: {str(e)}")
        return {}