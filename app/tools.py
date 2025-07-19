import logging
import os
import json
from pathlib import Path
from typing import List, Dict, Any
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
    ACTUALIZADO para manejar las especialidades reales de la base de datos.
    AHORA TAMBIÉN INCLUYE TÉRMINOS PARA BUSCAR EN age_group CUANDO ES RELEVANTE.
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
    # Especialidades reales encontradas: Nutrición clínica, enfermedades crónicas, diabetes, hipertensión, dislipidemia, etc.
    
    specialty_mappings = {
        # Nutrición -> buscar título "Nutricionista" y especialidades relacionadas
        "nutrición": ["nutricionista", "nutrición clínica", "nutrición"],
        "nutricion": ["nutricionista", "nutrición clínica", "nutrición"],
        "nutricionista": ["nutricionista", "nutrición clínica", "nutrición"],
        "nutrologo": ["nutricionista", "nutrición clínica", "nutrición"],
        "nutrologa": ["nutricionista", "nutrición clínica", "nutrición"],
        "dieta": ["nutricionista", "nutrición clínica", "nutrición"],
        "alimentacion": ["nutricionista", "nutrición clínica", "nutrición"],
        
        # Diabetes -> buscar en especialidades
        "diabetes": ["diabetes"],
        "diabetico": ["diabetes"],
        "diabético": ["diabetes"],
        
        # Hipertensión -> buscar en especialidades
        "hipertensión": ["hipertensión"],
        "hipertension": ["hipertensión"],
        "presión alta": ["hipertensión"],
        "presion alta": ["hipertensión"],
        
        # Enfermedades crónicas
        "enfermedades crónicas": ["enfermedades crónicas"],
        "enfermedades cronicas": ["enfermedades crónicas"],
        "crónicas": ["enfermedades crónicas"],
        "cronicas": ["enfermedades crónicas"],
        
        # Dislipidemia
        "dislipidemia": ["dislipidemia"],
        "colesterol": ["dislipidemia"],
        "triglicéridos": ["dislipidemia"],
        "trigliceridos": ["dislipidemia"],
        
        # Enfermedad renal
        "renal": ["enfermedad renal"],
        "riñón": ["enfermedad renal"],
        "riñon": ["enfermedad renal"],
        "nefrología": ["enfermedad renal"],
        "nefrologia": ["enfermedad renal"],
        
        # Enfermedad hepática
        "hepática": ["enfermedad hepática"],
        "hepatica": ["enfermedad hepática"],
        "hígado": ["enfermedad hepática"],
        "higado": ["enfermedad hepática"],
        
        # Cáncer/Oncología
        "cáncer": ["cáncer"],
        "cancer": ["cáncer"],
        "oncología": ["cáncer"],
        "oncologia": ["cáncer"],
        "oncologo": ["cáncer"],
        "oncóloga": ["cáncer"],
        
        # Enfermedades autoinmunes
        "autoinmunes": ["enfermedades autoinmunes"],
        "autoinmune": ["enfermedades autoinmunes"],
        "lupus": ["enfermedades autoinmunes"],
        "artritis": ["enfermedades autoinmunes"],
        
        # Nutrición enteral/parenteral
        "enteral": ["nutrición enteral"],
        "parenteral": ["nutrición parenteral"],
        "sonda": ["nutrición enteral"],
        
        # Colon irritable
        "colon irritable": ["colon irritable"],
        "síndrome del intestino irritable": ["colon irritable"],
        "sindrome del intestino irritable": ["colon irritable"],
        
        # Celiaquía
        "celiaquía": ["celiaquía"],
        "celiaquia": ["celiaquía"],
        "celíaco": ["celiaquía"],
        "celiaco": ["celiaquía"],
        "gluten": ["celiaquía"],
        
        # Embarazo y lactancia
        "embarazo": ["embarazo"],
        "lactancia": ["lactancia"],
        "materno": ["embarazo", "lactancia"],
        "materna": ["embarazo", "lactancia"],
        
        # Trastornos alimentarios
        "anorexia": ["anorexia"],
        "bulimia": ["bulimia"],
        "trastornos alimentarios": ["anorexia", "bulimia"],
        
        # Nutrición vegetariana/vegana
        "vegetariana": ["nutrición vegetariana"],
        "vegetariano": ["nutrición vegetariana"],
        "vegana": ["nutrición vegana"],
        "vegano": ["nutrición vegana"],
        
        # Nutrición bariátrica
        "bariátrica": ["nutrición bariátrica"],
        "bariatrica": ["nutrición bariátrica"],
        "obesidad": ["nutrición bariátrica"],
        "pérdida de peso": ["nutrición bariátrica"],
        "perdida de peso": ["nutrición bariátrica"],
        
        # Títulos profesionales (mantener compatibilidad)
        "kinesiología": ["kinesiólogo"],
        "kinesiologia": ["kinesiólogo"], 
        "kinesiologo": ["kinesiólogo"],
        "kinesiologa": ["kinesiólogo"],
        "kinesiólogo": ["kinesiólogo"],
        "kinesióloga": ["kinesiólogo"],
        "fisioterapia": ["kinesiólogo"],
        "fisioterapeuta": ["kinesiólogo"],
        
        "cardiología": ["cardiología", "médico"],
        "cardiologia": ["cardiología", "médico"],
        "cardiologo": ["cardiología", "médico"],
        "cardióloga": ["cardiología", "médico"],
        "cardiólogo": ["cardiología", "médico"],
        
        # PEDIATRÍA - AHORA TAMBIÉN INCLUYE TÉRMINOS PARA age_group
        "pediatría": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "pediatria": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "pediatra": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "pediatras": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "niños": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "niño": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "niña": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "niñas": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "infantil": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "bebé": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "bebe": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "bebés": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "bebes": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "chico": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "chica": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "chicos": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        "chicas": ["pediatría", "médico", "niños", "pediatría", "infantil"],
        
        "enfermería": ["enfermera", "tens"],
        "enfermeria": ["enfermera", "tens"],
        "enfermera": ["enfermera", "tens"],
        "enfermero": ["enfermera", "tens"],
        "tens": ["tens", "enfermera"],
        
        "medicina general": ["médico"],
        "medico general": ["médico"],
        "medico": ["médico"],
        "médico": ["médico"],
        "doctor": ["médico"],
        "doctora": ["médico"],
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
    Maneja abreviaciones específicas del Google Sheet como "L a V", "Sáb y Dom", etc.
    """
    availability_lower = availability.lower().strip()
    
    # Crear variaciones de disponibilidad
    variations = [availability_lower]
    
    # Mapeo de días de la semana y horarios comunes
    availability_mappings = {
        # Días individuales
        "lunes": ["lunes", "monday", "lun", "l", "l a v", "lunes a viernes", "entre semana", "semana"],
        "martes": ["martes", "tuesday", "mar", "l a v", "lunes a viernes", "entre semana", "semana"],
        "miércoles": ["miércoles", "miercoles", "wednesday", "mié", "mie", "l a v", "lunes a viernes", "entre semana", "semana"],
        "miercoles": ["miércoles", "miercoles", "wednesday", "mié", "mie", "l a v", "lunes a viernes", "entre semana", "semana"],
        "jueves": ["jueves", "thursday", "jue", "l a v", "lunes a viernes", "entre semana", "semana"],
        "viernes": ["viernes", "friday", "vie", "v", "l a v", "lunes a viernes", "entre semana", "semana"],
        "sábado": ["sábado", "sabado", "saturday", "sáb", "sab", "sáb y dom", "sabado y domingo", "fin de semana", "fines de semana", "weekend"],
        "sabado": ["sábado", "sabado", "saturday", "sáb", "sab", "sáb y dom", "sabado y domingo", "fin de semana", "fines de semana", "weekend"],
        "domingo": ["domingo", "sunday", "dom", "sáb y dom", "sabado y domingo", "fin de semana", "fines de semana", "weekend"],
        
        # Grupos de días (formatos del Google Sheet)
        "fin de semana": ["fin de semana", "fines de semana", "weekend", "sáb y dom", "sabado y domingo", "sábado", "sabado", "domingo"],
        "fines de semana": ["fin de semana", "fines de semana", "weekend", "sáb y dom", "sabado y domingo", "sábado", "sabado", "domingo"],
        "weekend": ["fin de semana", "fines de semana", "weekend", "sáb y dom", "sabado y domingo", "sábado", "sabado", "domingo"],
        "entre semana": ["l a v", "lunes a viernes", "entre semana", "semana", "lunes", "martes", "miércoles", "miercoles", "jueves", "viernes"],
        "semana": ["l a v", "lunes a viernes", "entre semana", "semana", "lunes", "martes", "miércoles", "miercoles", "jueves", "viernes"],
        
        # Horarios
        "mañana": ["mañana", "morning", "am", "matutino", "8:00", "9:00", "10:00", "11:00"],
        "tarde": ["tarde", "afternoon", "pm", "vespertino", "14:00", "15:00", "16:00", "17:00", "18:00"],
        "noche": ["noche", "evening", "night", "nocturno", "19:00", "20:00", "21:00", "22:00"],
        "madrugada": ["madrugada", "early morning", "dawn", "6:00", "7:00"],
        
        # Urgencias
        "urgencia": ["urgencia", "emergency", "24 horas", "24/7", "siempre"],
        "emergencia": ["urgencia", "emergency", "24 horas", "24/7", "siempre"],
        "24 horas": ["urgencia", "emergency", "24 horas", "24/7", "siempre"],
        "24/7": ["urgencia", "emergency", "24 horas", "24/7", "siempre"],
    }
    
    # Buscar coincidencias en el mapeo
    for term, mappings in availability_mappings.items():
        if term in availability_lower:
            variations.extend(mappings)
    
    # Mapeo inverso: si el usuario busca un día que está en "L a V", debe encontrar "L a V"
    reverse_mappings = {
        # Si buscan días individuales de semana, también buscar "L a V"
        "lunes": ["l a v", "lunes a viernes"],
        "martes": ["l a v", "lunes a viernes"], 
        "miércoles": ["l a v", "lunes a viernes"],
        "miercoles": ["l a v", "lunes a viernes"],
        "jueves": ["l a v", "lunes a viernes"],
        "viernes": ["l a v", "lunes a viernes"],
        
        # Si buscan días de fin de semana, también buscar "Sáb y Dom"
        "sábado": ["sáb y dom"],
        "sabado": ["sáb y dom"],
        "domingo": ["sáb y dom"],
        "fin de semana": ["sáb y dom"],
        "fines de semana": ["sáb y dom"],
        "weekend": ["sáb y dom"],
    }
    
    # Aplicar mapeo inverso
    for user_term, sheet_terms in reverse_mappings.items():
        if user_term in availability_lower:
            variations.extend(sheet_terms)
    
    # Remover duplicados y mantener orden
    unique_variations = []
    for v in variations:
        if v not in unique_variations:
            unique_variations.append(v)
    
    logger.info(f"🕐 Variaciones de disponibilidad para '{availability}': {unique_variations}")
    return unique_variations

def normalize_age_group_search(age_group: str) -> List[str]:
    """
    Normaliza la búsqueda de grupos etarios para encontrar variaciones.
    Maneja términos como "pediatra", "niños", "adultos", etc.
    AHORA INCLUYE MÁS VARIACIONES PARA PEDIATRÍA.
    """
    age_group_lower = age_group.lower().strip()
    
    # Mapeo de términos de búsqueda a grupos etarios reales
    age_group_mappings = {
        # Pediatría/Niños - MÁS VARIACIONES
        "pediatra": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "pediatras": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "pediatría": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "pediatria": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "pediatrico": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "pediatrica": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "pediátrico": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "pediátrica": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "niños": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "niño": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "niña": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "niñas": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "infantil": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "bebé": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "bebe": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "bebés": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "bebes": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "chico": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "chica": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "chicos": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        "chicas": ["niños", "pediatría", "pediatria", "infantil", "adulto y pediatría"],
        
        # Adultos
        "adulto": ["adulto", "adulto y pediatría"],
        "adultos": ["adulto", "adulto y pediatría"],
        "adulta": ["adulto", "adulto y pediatría"],
        "adultas": ["adulto", "adulto y pediatría"],
        
        # Adultos mayores/Geriatría
        "adulto mayor": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        "adultos mayores": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        "geriatría": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        "geriatria": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        "geriatra": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        "tercera edad": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        "anciano": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        "ancianos": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        "anciana": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        "ancianas": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        "mayor": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        "mayores": ["adulto mayor", "geriatría", "geriatria", "tercera edad"],
        
        # Adolescentes
        "adolescente": ["adolescente"],
        "adolescentes": ["adolescente"],
        "joven": ["adolescente"],
        "jóvenes": ["adolescente"],
        "jovenes": ["adolescente"],
        "teen": ["adolescente"],
        "teenager": ["adolescente"],
        
        # General
        "todas las edades": ["todas las edades", "general"],
        "todas las edades": ["todas las edades", "general"],
        "general": ["todas las edades", "general"],
    }
    
    # Si el término está en el mapeo, usar esas variaciones
    if age_group_lower in age_group_mappings:
        variations = age_group_mappings[age_group_lower]
    else:
        # Si no está en el mapeo, usar el término original
        variations = [age_group_lower]
    
    logger.info(f"👥 Variaciones de grupo etario para '{age_group}': {variations}")
    return variations


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
            
            # Buscar disponibilidad si se especificó (en availability_days y availability_hours)
            availability_match = True  # Por defecto True si no se especifica availability
            if availability:
                availability_days_text = str(r.get("availability_days", "")).lower()
                availability_hours_text = str(r.get("availability_hours", "")).lower()
                
                # Buscar en ambos campos de disponibilidad
                days_match = any(term in availability_days_text for term in availability_terms)
                hours_match = any(term in availability_hours_text for term in availability_terms)
                availability_match = days_match or hours_match
                
                if not availability_match:
                    logger.info(f"🕐 No match de disponibilidad en fila {i+1}: días '{availability_days_text}' y horas '{availability_hours_text}' no contienen ninguno de {availability_terms}")
            
            if professional_match and city_match and availability_match:
                logger.info(f"✅ Match completo encontrado en fila {i+1}: {r}")
                if specialty_match:
                    logger.info(f"✅ Specialty match: '{specialty_text}' contiene alguno de {specialty_terms}")
                if title_match:
                    logger.info(f"✅ Title match: '{title_text}' contiene alguno de {specialty_terms}")
                logger.info(f"✅ City match: '{coverage_area_text}' contiene alguno de {city_terms}")
                if availability:
                    if days_match:
                        logger.info(f"✅ Availability days match: '{availability_days_text}' contiene alguno de {availability_terms}")
                    if hours_match:
                        logger.info(f"✅ Availability hours match: '{availability_hours_text}' contiene alguno de {availability_terms}")
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
                availability_days = r.get("availability_days", "No especificado")
                availability_hours = r.get("availability_hours", "No especificado")
                specialty = r.get("specialty", "No especificada")
                title = r.get("title", "No especificado")
                coverage_area = r.get("coverage_area", "No especificada")
                work_region = r.get("work_region", "No especificada")
                age_group = r.get("age_group", "No especificado")
                sis_number = r.get("sis_number", "No especificado")
                
                logger.info(f"✅ Profesional encontrado en fila {i+1}:")
                logger.info(f"   📋 Nombre: {r.get('name', 'N/A')}")
                logger.info(f"   🆔 Número SIS: {sis_number}")
                logger.info(f"   🏥 Especialidad: {specialty}")
                logger.info(f"   🎓 Título: {title}")
                logger.info(f"   🌍 Región de trabajo: {work_region}")
                logger.info(f"   📍 Área de cobertura: {coverage_area}")
                logger.info(f"   👥 Grupo etario: {age_group}")
                logger.info(f"   📅 Días disponibles: {availability_days}")
                logger.info(f"   🕐 Horarios: {availability_hours}")
                logger.info(f"   📞 Contacto: {r.get('phone', 'N/A')}")
                logger.info(f"   📧 Email: {r.get('email', 'N/A')}")
                
                # Asegurar que los campos de disponibilidad estén incluidos en el resultado
                if 'availability_days' not in r:
                    logger.warning(f"⚠️ Columna 'availability_days' no encontrada en el registro")
                    r['availability_days'] = "No especificado"
                if 'availability_hours' not in r:
                    logger.warning(f"⚠️ Columna 'availability_hours' no encontrada en el registro")
                    r['availability_hours'] = "No especificado"
                
                return r
        
        logger.info(f"❌ No se encontró profesional con nombre: '{name}'")
        return {}
        
    except Exception as e:
        logger.error(f"❌ Error buscando profesional por nombre: {str(e)}")
        return {}


def get_all_professionals_data() -> List[Dict]:
    """
    Devuelve todos los datos de profesionales de la base de datos.
    Permite al agente tener acceso completo a toda la información disponible.
    """
    logger.info(f"📊 Obteniendo todos los datos de profesionales desde Google Sheet")
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
        logger.info(f"✅ Conexión exitosa a Google Sheet")
        
        rows = sheet.get_all_records()
        logger.info(f"📊 Total de registros obtenidos: {len(rows)}")
        
        if len(rows) > 0:
            logger.info(f"📊 Columnas disponibles: {list(rows[0].keys())}")
            logger.info(f"📊 Muestra de datos (primer registro): {rows[0]}")
        
        return rows
        
    except Exception as e:
        logger.error(f"❌ Error accediendo a Google Sheet: {str(e)}")
        return []


def search_professionals_flexible(search_query: str, search_criteria: Dict[str, str] = None) -> List[Dict]:
    """
    Búsqueda flexible de profesionales que permite al agente determinar los criterios de búsqueda.
    MANEJA CORRECTAMENTE campos con múltiples valores separados por punto y coma.
    AHORA TAMBIÉN BUSCA EN age_group para términos relacionados con grupos etarios.
    
    Args:
        search_query: Consulta de búsqueda en lenguaje natural
        search_criteria: Diccionario opcional con criterios específicos de búsqueda
                        Puede incluir cualquier combinación de: name, sis_number, work_region,
                        coverage_area, title, specialty, age_group, phone, email, 
                        availability_days, availability_hours, etc.
    
    Returns:
        Lista de profesionales que coinciden con los criterios
    """
    logger.info(f"🔍 Búsqueda flexible con query: '{search_query}'")
    if search_criteria:
        logger.info(f"🔍 Criterios específicos: {search_criteria}")
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
        rows = sheet.get_all_records()
        logger.info(f"📊 Buscando en {len(rows)} registros...")
        
        if len(rows) > 0:
            logger.info(f"📊 Columnas disponibles para búsqueda: {list(rows[0].keys())}")
        
        matches = []
        
        # Si no se proporcionan criterios específicos, hacer búsqueda en todos los campos
        if not search_criteria:
            search_terms = search_query.lower().split()
            logger.info(f"🔍 Búsqueda general con términos: {search_terms}")
            
            for i, record in enumerate(rows):
                # Buscar en todos los campos de texto del registro
                record_text = ""
                for key, value in record.items():
                    if isinstance(value, str):
                        record_text += f" {value.lower()}"
                
                # Verificar si algún término de búsqueda está en el registro
                match_found = any(term in record_text for term in search_terms)
                
                if match_found:
                    logger.info(f"✅ Match encontrado en registro {i+1}: {record.get('name', 'N/A')}")
                    matches.append(record)
        
        else:
            # Búsqueda con criterios específicos
            logger.info(f"🔍 Búsqueda con criterios específicos")
            
            for i, record in enumerate(rows):
                match_found = True
                
                for criterion_key, criterion_value in search_criteria.items():
                    if criterion_key in record:
                        record_value = str(record[criterion_key]).lower()
                        search_value = criterion_value.lower()
                        
                        # Aplicar normalización inteligente según el tipo de campo
                        if criterion_key in ['specialty', 'title']:
                            search_terms = normalize_specialty_search(criterion_value)
                            field_match = check_multi_value_field(record_value, search_terms)
                        elif criterion_key in ['coverage_area', 'work_region']:
                            search_terms = normalize_city_search(criterion_value)
                            field_match = check_multi_value_field(record_value, search_terms)
                        elif criterion_key in ['availability_days', 'availability_hours']:
                            search_terms = normalize_availability_search(criterion_value)
                            field_match = check_multi_value_field(record_value, search_terms)
                        elif criterion_key == 'age_group':
                            search_terms = normalize_age_group_search(criterion_value)
                            field_match = check_multi_value_field(record_value, search_terms)
                        else:
                            # Búsqueda simple para otros campos (name, sis_number, phone, email)
                            field_match = search_value in record_value
                        
                        if not field_match:
                            match_found = False
                            break
                    else:
                        logger.warning(f"⚠️ Campo '{criterion_key}' no existe en el registro")
                        match_found = False
                        break
                
                if match_found:
                    logger.info(f"✅ Match con criterios específicos en registro {i+1}: {record.get('name', 'N/A')}")
                    matches.append(record)
        
        logger.info(f"📋 Total matches encontrados: {len(matches)}")
        return matches
        
    except Exception as e:
        logger.error(f"❌ Error en búsqueda flexible: {str(e)}")
        return []


def check_multi_value_field(field_value: str, search_terms: List[str]) -> bool:
    """
    Verifica si alguno de los términos de búsqueda está presente en un campo que puede contener múltiples valores.
    Maneja campos separados por punto y coma (;) correctamente.
    AHORA TAMBIÉN MANEJA VARIACIONES CON Y SIN TILDES.
    
    Args:
        field_value: Valor del campo (puede contener múltiples valores separados por ;)
        search_terms: Lista de términos a buscar
    
    Returns:
        True si al menos un término coincide
    """
    # Separar el campo por punto y coma y limpiar espacios
    field_values = [v.strip().lower() for v in field_value.split(';')]
    
    # También considerar el valor completo como una opción
    field_values.append(field_value.lower())
    
    # Normalizar tildes para búsqueda más flexible
    def normalize_text(text: str) -> str:
        """Normaliza texto removiendo tildes para búsqueda más flexible."""
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u', 'ñ': 'n',
            'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 'Ü': 'U', 'Ñ': 'N'
        }
        for accented, plain in replacements.items():
            text = text.replace(accented, plain)
        return text
    
    # Verificar si alguno de los términos de búsqueda está en alguno de los valores del campo
    for search_term in search_terms:
        search_term_normalized = normalize_text(search_term.lower())
        
        for field_val in field_values:
            field_val_normalized = normalize_text(field_val.lower())
            
            # Búsqueda exacta
            if search_term in field_val or field_val in search_term:
                logger.info(f"✅ Match exacto encontrado: '{search_term}' en '{field_val}'")
                return True
            
            # Búsqueda normalizada (sin tildes)
            if search_term_normalized in field_val_normalized or field_val_normalized in search_term_normalized:
                logger.info(f"✅ Match normalizado encontrado: '{search_term}' (normalizado: '{search_term_normalized}') en '{field_val}' (normalizado: '{field_val_normalized}')")
                return True
    
    return False


def get_database_schema() -> Dict[str, Any]:
    """
    Devuelve información sobre la estructura de la base de datos de profesionales.
    Incluye nombres de columnas, tipos de datos y ejemplos.
    """
    logger.info(f"📋 Obteniendo esquema de la base de datos")
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
        rows = sheet.get_all_records()
        
        if len(rows) == 0:
            return {"error": "No hay datos disponibles"}
        
        # Obtener información del esquema
        schema_info = {
            "total_records": len(rows),
            "columns": list(rows[0].keys()),
            "sample_data": rows[0] if len(rows) > 0 else {},
            "column_descriptions": {
                "name": "Nombre completo del profesional de salud",
                "sis_number": "Número identificador en el sistema de salud",
                "work_region": "Región donde trabaja el profesional",
                "coverage_area": "Áreas específicas o ciudades donde brinda servicios",
                "title": "Título profesional (ej: Médico, Enfermera, Kinesiólogo, Nutricionista, TENS, etc.)",
                "specialty": "Especialidad médica específica (ej: Cardiología, Pediatría, Geriatría, etc.)",
                "age_group": "Grupo etario que atiende (ej: Adultos, Niños, Adultos Mayores, etc.)",
                "phone": "Número de teléfono de contacto",
                "email": "Correo electrónico de contacto",
                "availability_days": "Días de la semana en que está disponible",
                "availability_hours": "Horarios de atención específicos"
            }
        }
        
        # Obtener valores únicos para campos categóricos
        unique_values = {}
        categorical_fields = ['title', 'specialty', 'work_region', 'age_group']
        
        for field in categorical_fields:
            if field in rows[0]:
                values = set()
                for record in rows:
                    if record.get(field):
                        values.add(str(record[field]))
                unique_values[field] = sorted(list(values))
        
        schema_info["unique_values"] = unique_values
        
        logger.info(f"📋 Esquema obtenido: {len(schema_info['columns'])} columnas, {schema_info['total_records']} registros")
        return schema_info
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo esquema: {str(e)}")
        return {"error": f"Error accediendo a la base de datos: {str(e)}"}