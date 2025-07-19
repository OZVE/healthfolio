import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any

import openai
from dotenv import load_dotenv
from .tools import find_professionals, find_professional_by_name, get_all_professionals_data, search_professionals_flexible, get_database_schema
from .utils import get_memory, set_memory

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv(Path(__file__).parent.parent / ".env")

# Configurar OpenAI con validación
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("❌ OPENAI_API_KEY no está configurado!")
    raise ValueError("OPENAI_API_KEY es obligatorio")

openai.api_key = OPENAI_API_KEY
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
logger.info(f"🤖 OpenAI configurado con modelo: {MODEL}")

SYSTEM_PROMPT = Path(__file__).parent / "prompts" / "system_prompt.txt"
SYSTEM_TEXT = SYSTEM_PROMPT.read_text(encoding='utf-8')


# esquema OpenAI tools - Nuevas herramientas flexibles
GET_DATABASE_SCHEMA_FN = {
    "type": "function",
    "function": {
        "name": "get_database_schema",
        "description": "Obtiene información completa sobre la estructura de la base de datos de profesionales de salud, incluyendo todas las columnas disponibles, tipos de datos, valores únicos y ejemplos. Útil para entender qué información está disponible antes de hacer búsquedas.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

GET_ALL_DATA_FN = {
    "type": "function",
    "function": {
        "name": "get_all_professionals_data",
        "description": "Obtiene todos los datos completos de todos los profesionales de salud en la base de datos. Permite acceso total a toda la información disponible sin filtros. Útil cuando necesitas analizar toda la información disponible o hacer búsquedas complejas.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

SEARCH_FLEXIBLE_FN = {
    "type": "function",
    "function": {
        "name": "search_professionals_flexible",
        "description": "Búsqueda inteligente y flexible de profesionales de salud. Puedes usar lenguaje natural o especificar criterios específicos. El sistema determinará automáticamente los mejores parámetros de búsqueda según el contexto.",
        "parameters": {
            "type": "object",
            "properties": {
                "search_query": {
                    "type": "string", 
                    "description": "Consulta de búsqueda en lenguaje natural (ej: 'cardiólogo en Santiago', 'enfermera disponible fines de semana', 'kinesióloga en Las Condes')"
                },
                "search_criteria": {
                    "type": "object",
                    "description": "Criterios específicos de búsqueda (opcional). Puede incluir cualquier combinación de campos: name, sis_number, work_region, coverage_area, title, specialty, age_group, phone, email, availability_days, availability_hours, etc.",
                    "properties": {
                        "name": {"type": "string", "description": "Nombre del profesional"},
                        "sis_number": {"type": "string", "description": "Número identificador en el sistema de salud"},
                        "work_region": {"type": "string", "description": "Región donde trabaja"},
                        "coverage_area": {"type": "string", "description": "Área de cobertura o ciudad específica"},
                        "title": {"type": "string", "description": "Título profesional (Médico, Enfermera, Kinesiólogo, etc.)"},
                        "specialty": {"type": "string", "description": "Especialidad médica específica"},
                        "age_group": {"type": "string", "description": "Grupo etario que atiende"},
                        "phone": {"type": "string", "description": "Teléfono de contacto"},
                        "email": {"type": "string", "description": "Email de contacto"},
                        "availability_days": {"type": "string", "description": "Días de la semana disponibles"},
                        "availability_hours": {"type": "string", "description": "Horarios específicos de atención"}
                    }
                }
            },
            "required": ["search_query"],
        },
    },
}

# Herramientas legacy (mantener por compatibilidad)
FIND_PROF_FN = {
    "type": "function",
    "function": {
        "name": "find_professionals",
        "description": "Búsqueda tradicional de profesionales por especialidad, ciudad y disponibilidad (legacy - se recomienda usar search_professionals_flexible)",
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {"type": "string", "description": "Especialidad médica o título profesional"},
                "city": {"type": "string", "description": "Ciudad o área donde se necesita el servicio"},
                "availability": {"type": "string", "description": "Día de la semana o horario específico (ej: lunes, martes, fines de semana, etc.). Opcional."}
            },
            "required": ["specialty", "city"],
        },
    },
}

FIND_PROF_BY_NAME_FN = {
    "type": "function",
    "function": {
        "name": "find_professional_by_name",
        "description": "Busca un profesional específico por nombre (legacy - se recomienda usar search_professionals_flexible con criterio 'name')",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        },
    },
}


def build_messages(system: str, history: List[Dict[str, str]], user_input: str):
    messages = [{"role": "system", "content": system}] + history
    messages.append({"role": "user", "content": user_input})
    return messages


def call_llm(messages: List[Dict[str, str]], tools: List[Dict[str, Any]]):
    return openai.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0.2,
    )


def process(user_input: str, chat_id: str) -> str:
    logger.info(f"🔍 Processing user input: '{user_input}' for chat_id: {chat_id}")
    history = get_memory(chat_id)
    logger.info(f"📚 Retrieved {len(history)} messages from memory")
    messages = build_messages(SYSTEM_TEXT, history, user_input)

    response = call_llm(messages, [GET_DATABASE_SCHEMA_FN, GET_ALL_DATA_FN, SEARCH_FLEXIBLE_FN, FIND_PROF_FN, FIND_PROF_BY_NAME_FN])
    choice = response.choices[0]
    logger.info(f"🤖 OpenAI finish_reason: {choice.finish_reason}")

    if choice.finish_reason == "tool_calls":
        logger.info(f"🔧 OpenAI decidió usar herramientas (tool_calls)")
        # Agregar el mensaje del asistente con tool_calls
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in choice.message.tool_calls
            ]
        })
        
        for tc in choice.message.tool_calls:
            if tc.function.name == "get_database_schema":
                logger.info(f"📋 Llamando get_database_schema")
                schema = get_database_schema()
                logger.info(f"📋 Esquema obtenido: {schema}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(schema),
                })
            elif tc.function.name == "get_all_professionals_data":
                logger.info(f"📊 Llamando get_all_professionals_data")
                all_data = get_all_professionals_data()
                logger.info(f"📊 Obtenidos {len(all_data)} registros completos")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(all_data),
                })
            elif tc.function.name == "search_professionals_flexible":
                args = json.loads(tc.function.arguments)
                search_query = args["search_query"]
                search_criteria = args.get("search_criteria")
                if search_criteria:
                    logger.info(f"🔍 Llamando search_professionals_flexible con query='{search_query}' y criterios='{search_criteria}'")
                    results = search_professionals_flexible(search_query, search_criteria)
                else:
                    logger.info(f"🔍 Llamando search_professionals_flexible con query='{search_query}'")
                    results = search_professionals_flexible(search_query)
                logger.info(f"📋 Encontrados {len(results)} profesionales con búsqueda flexible")
                logger.info(f"📋 Resultados: {results}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(results),
                })
            elif tc.function.name == "find_professionals":
                args = json.loads(tc.function.arguments)
                availability = args.get("availability")
                if availability:
                    logger.info(f"🏥 Llamando find_professionals (legacy) con specialty='{args['specialty']}', city='{args['city']}', availability='{availability}'")
                    pros = find_professionals(args["specialty"], args["city"], availability)
                else:
                    logger.info(f"🏥 Llamando find_professionals (legacy) con specialty='{args['specialty']}', city='{args['city']}'")
                    pros = find_professionals(args["specialty"], args["city"])
                logger.info(f"📋 Encontrados {len(pros)} profesionales con búsqueda legacy")
                logger.info(f"📋 Datos encontrados: {pros}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(pros),
                })
            elif tc.function.name == "find_professional_by_name":
                args = json.loads(tc.function.arguments)
                logger.info(f"👤 Llamando find_professional_by_name (legacy) con name='{args['name']}'")
                pro = find_professional_by_name(args["name"])
                logger.info(f"📋 Profesional encontrado: {pro}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(pro),
                })
                
        response = call_llm(messages, [])

    final_text = response.choices[0].message.content
    logger.info(f"💬 Final response length: {len(final_text)} characters")
    logger.info(f"💬 Final response preview: {final_text[:200]}...")
    
    # Preparar mensajes para guardar en memoria
    messages_to_save = (
        history[-8:] + [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": final_text},
        ]
    )[-20:]
    
    logger.info(f"📝 Preparando mensajes para memoria:")
    logger.info(f"   - Historia anterior: {len(history)} mensajes")
    logger.info(f"   - Mensaje del usuario: '{user_input[:50]}...'")
    logger.info(f"   - Respuesta del asistente: '{final_text[:50]}...'")
    logger.info(f"   - Total a guardar: {len(messages_to_save)} mensajes")
    
    set_memory(chat_id, messages_to_save)
    logger.info(f"💾 Memoria actualizada para chat_id: {chat_id}")
    return final_text