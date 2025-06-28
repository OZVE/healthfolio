import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any

import openai
from dotenv import load_dotenv
from .tools import find_professionals, find_professional_by_name
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


# esquema OpenAI tools
FIND_PROF_FN = {
    "type": "function",
    "function": {
        "name": "find_professionals",
        "description": "Devuelve lista de profesionales sanitarios que cubren la ciudad y la especialidad",
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {"type": "string"},
                "city": {"type": "string"},
            },
            "required": ["specialty", "city"],
        },
    },
}

FIND_PROF_BY_NAME_FN = {
    "type": "function",
    "function": {
        "name": "find_professional_by_name",
        "description": "Busca un profesional específico por nombre para obtener sus datos de contacto completos",
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

    response = call_llm(messages, [FIND_PROF_FN, FIND_PROF_BY_NAME_FN])
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
            if tc.function.name == "find_professionals":
                args = json.loads(tc.function.arguments)
                logger.info(f"🏥 Llamando find_professionals con specialty='{args['specialty']}', city='{args['city']}'")
                pros = find_professionals(args["specialty"], args["city"])
                logger.info(f"📋 Encontrados {len(pros)} profesionales en Google Sheet")
                logger.info(f"📋 Datos encontrados: {pros}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(pros),
                })
            elif tc.function.name == "find_professional_by_name":
                args = json.loads(tc.function.arguments)
                logger.info(f"👤 Llamando find_professional_by_name con name='{args['name']}'")
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
    
    messages_to_save = (
        history[-8:] + [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": final_text},
        ]
    )[-20:]
    set_memory(chat_id, messages_to_save)
    logger.info(f"💾 Saved {len(messages_to_save)} messages to memory")
    return final_text