# Plan de Corrección: Error en Transcripción de Audio - Enfermera vs Nutricionista

## 📋 Resumen del Problema

El cliente reporta que cuando solicita una **enfermera** por audio, el agente devuelve **nutricionistas** en su lugar. 

**IMPORTANTE**: El usuario NO ha probado escribiendo únicamente, por lo que el error podría estar en:
1. **Transcripción de audio** (Whisper malinterpretando "enfermera" como "nutricionista")
2. **Lógica de búsqueda del agente** (el agente buscando mal independientemente del input)
3. **Mapeo de especialidades** (confusión en el sistema de búsqueda)

Necesitamos investigar ambos escenarios antes de implementar correcciones.

## 🔍 Análisis del Problema

### Escenarios Posibles

#### **Escenario A: Error en Transcripción de Audio**
1. **Recepción del Audio**: El webhook recibe el mensaje de voz
2. **Extracción del Audio**: Se extrae la información del audio del evento
3. **Transcripción**: Whisper transcribe "enfermera" como "nutricionista"
4. **Procesamiento**: El texto incorrecto se envía al agente
5. **Búsqueda**: El agente busca correctamente pero con término incorrecto

#### **Escenario B: Error en Lógica de Búsqueda del Agente**
1. **Recepción del Audio**: El webhook recibe el mensaje de voz
2. **Transcripción**: Whisper transcribe correctamente "enfermera"
3. **Procesamiento**: El texto correcto se envía al agente
4. **Búsqueda**: El agente busca mal o confunde especialidades
5. **Resultado**: Devuelve nutricionistas en lugar de enfermeras

### Posibles Causas del Error

#### 1. **Error en la Transcripción (Whisper) - Escenario A**
- El modelo Whisper puede estar transcribiendo incorrectamente "enfermera" como "nutricionista"
- Problemas de acento, ruido de fondo o calidad del audio
- Configuración del modelo de transcripción

#### 2. **Error en la Lógica de Búsqueda - Escenario B**
- Problemas en la función `normalize_specialty_search()`
- Mapeo incorrecto de términos de especialidad
- Confusión entre enfermería y nutrición en el sistema
- Error en la interpretación del prompt del sistema

#### 3. **Error en el Mapeo de Especialidades - Ambos Escenarios**
- Mapeo confuso entre enfermería y nutrición
- Lógica de búsqueda defectuosa
- Problemas en la validación de resultados

## 🛠️ Plan de Corrección

### Fase 0: Diagnóstico Inicial (CRÍTICO)

#### 0.1 Testing Inmediato con Texto
**PRIORIDAD MÁXIMA**: Antes de cualquier corrección, necesitamos probar si el error existe también con texto escrito.

**Acciones Inmediatas:**
1. **Probar con texto escrito**: Solicitar al cliente que pruebe escribiendo "enfermera" en lugar de usar audio
2. **Probar variaciones**: "enfermero", "enfermería", "TENS", "cuidados paliativos"
3. **Comparar resultados**: Ver si el error persiste con texto vs audio

**Comandos de prueba sugeridos:**
```
- "Busco una enfermera en Independencia"
- "Necesito un enfermero para cuidados paliativos"
- "Quiero contactar una enfermera"
- "Busco TENS en mi zona"
```

#### 0.2 Análisis de Logs Existentes
**Archivo**: Revisar logs del sistema para casos anteriores
- Buscar transcripciones de audio que contengan "enfermera"
- Verificar si el agente está recibiendo el texto correcto
- Analizar qué herramientas está usando el agente

#### 0.3 Testing de Herramientas de Búsqueda
**Archivo**: `app/tools.py`
- Probar directamente `search_professionals_flexible("enfermera")`
- Probar `normalize_specialty_search("enfermera")`
- Verificar mapeo de especialidades

### Fase 1: Diagnóstico y Logging Mejorado

#### 1.1 Agregar Logging Detallado de Transcripción
**Archivo**: `app/main.py`
**Líneas**: 213-214

```python
# ANTES
user_text = await transcribe_audio(audio_bytes, filename=filename, mimetype=mt)
logger.info(f"📝 Transcripción obtenida: '{user_text}'")

# DESPUÉS
user_text = await transcribe_audio(audio_bytes, filename=filename, mimetype=mt)
logger.info(f"📝 Transcripción obtenida: '{user_text}'")
logger.info(f"🎙️ Audio original - Tamaño: {len(audio_bytes)} bytes, Tipo: {mt}")
logger.info(f"🔍 Análisis de transcripción: Longitud={len(user_text)}, Palabras={user_text.split()}")
```

#### 1.2 Agregar Logging de Procesamiento del Agente
**Archivo**: `app/mcp_gateway.py`
**Líneas**: 144-150

```python
# ANTES
def process(user_input: str, chat_id: str) -> str:
    logger.info(f"🔍 Processing user input: '{user_input}' for chat_id: {chat_id}")

# DESPUÉS
def process(user_input: str, chat_id: str) -> str:
    logger.info(f"🔍 Processing user input: '{user_input}' for chat_id: {chat_id}")
    logger.info(f"🎯 Tipo de entrada: {'AUDIO' if 'transcripción' in user_input.lower() else 'TEXTO'}")
    logger.info(f"🔍 Palabras clave detectadas: {[word for word in user_input.lower().split() if word in ['enfermera', 'enfermero', 'nutricionista', 'nutrición', 'médico', 'doctor']]}")
```

### Fase 2: Mejoras en la Transcripción

#### 2.1 Configuración Mejorada de Whisper
**Archivo**: `app/main.py`
**Líneas**: 335-354

```python
# ANTES
async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg", mimetype: str = "audio/ogg") -> str:
    try:
        file_io = BytesIO(audio_bytes)
        file_io.name = filename
        result = openai.audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=file_io,
            response_format="json",
        )

# DESPUÉS
async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg", mimetype: str = "audio/ogg") -> str:
    try:
        file_io = BytesIO(audio_bytes)
        file_io.name = filename
        
        # Configuración mejorada para español
        result = openai.audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=file_io,
            response_format="json",
            language="es",  # Forzar español
            temperature=0.0,  # Reducir variabilidad
            prompt="Transcripción de audio en español sobre profesionales de la salud: enfermera, enfermero, médico, doctor, nutricionista, kinesiólogo, etc."
        )
```

#### 2.2 Validación y Corrección de Transcripción
**Archivo**: `app/main.py`
**Nueva función**

```python
def validate_and_correct_transcription(text: str) -> str:
    """
    Valida y corrige errores comunes en transcripciones de audio.
    """
    if not text:
        return text
    
    # Correcciones específicas para términos médicos
    corrections = {
        "nutricionista": "enfermera",  # Solo si el contexto sugiere error
        "nutrición": "enfermería",
        "nutriólogo": "enfermero",
        "nutrióloga": "enfermera",
    }
    
    # Detectar si hay indicios de que se pidió enfermera
    text_lower = text.lower()
    if any(word in text_lower for word in ["enfermera", "enfermero", "enfermería"]):
        # Si ya menciona enfermera, no corregir
        return text
    
    # Aplicar correcciones si es necesario
    corrected_text = text
    for wrong, correct in corrections.items():
        if wrong in text_lower and "enfermera" not in text_lower:
            corrected_text = corrected_text.replace(wrong, correct)
            logger.info(f"🔧 Corrección aplicada: '{wrong}' -> '{correct}'")
    
    return corrected_text
```

### Fase 3: Mejoras en el Mapeo de Especialidades

#### 3.1 Revisar y Corregir Mapeo de Enfermería
**Archivo**: `app/tools.py`
**Líneas**: 209-239

```python
# ANTES
"enfermería": ["enfermera", "tens"],
"enfermeria": ["enfermera", "tens"],
"enfermera": ["enfermera", "tens"],
"enfermero": ["enfermera", "tens"],
"tens": ["tens", "enfermera"],

# DESPUÉS - Mapeo más específico y robusto
"enfermería": ["enfermera", "tens", "enfermero"],
"enfermeria": ["enfermera", "tens", "enfermero"],
"enfermera": ["enfermera", "tens", "enfermero"],
"enfermero": ["enfermera", "tens", "enfermero"],
"tens": ["tens", "enfermera", "enfermero"],
"enfermeras": ["enfermera", "tens", "enfermero"],
"enfermeros": ["enfermera", "tens", "enfermero"],

# Agregar términos específicos de enfermería
"cuidados paliativos": ["enfermera", "enfermero", "tens"],
"cuidados paliativos": ["enfermera", "enfermero", "tens"],
"paliativos": ["enfermera", "enfermero", "tens"],
"cuidados": ["enfermera", "enfermero", "tens"],
```

#### 3.2 Separar Claramente Enfermería de Nutrición
**Archivo**: `app/tools.py`
**Líneas**: 74-82

```python
# ANTES - Mapeo de nutrición
"nutrición": ["nutricionista", "nutrición clínica", "nutrición"],
"nutricion": ["nutricionista", "nutrición clínica", "nutrición"],
"nutricionista": ["nutricionista", "nutrición clínica", "nutrición"],

# DESPUÉS - Mapeo más específico para evitar confusión
"nutrición": ["nutricionista", "nutrición clínica", "nutrición"],
"nutricion": ["nutricionista", "nutrición clínica", "nutrición"],
"nutricionista": ["nutricionista", "nutrición clínica", "nutrición"],
"nutriólogo": ["nutricionista", "nutrición clínica", "nutrición"],
"nutrióloga": ["nutricionista", "nutrición clínica", "nutrición"],

# IMPORTANTE: Asegurar que enfermería NO se mapee a nutrición
# Y viceversa
```

### Fase 4: Mejoras en el Prompt del Sistema

#### 4.1 Actualizar Prompt para Mejor Comprensión
**Archivo**: `app/prompts/system_prompt.txt`
**Líneas**: 156-167

```text
# AGREGAR al prompt existente:

**DIFERENCIACIÓN CRÍTICA ENTRE PROFESIONES:**
- **ENFERMERA/ENFERMERO**: Profesionales de enfermería, TENS, cuidados paliativos, atención directa al paciente
- **NUTRICIONISTA**: Profesionales de nutrición, dietética, alimentación, planes nutricionales
- **MÉDICO/DOCTOR**: Profesionales médicos con especialidades específicas

**REGLA IMPORTANTE**: Si el usuario solicita "enfermera" o "enfermero", NUNCA devuelvas nutricionistas. Si solicitan "nutricionista", NUNCA devuelvas enfermeras.

**VALIDACIÓN DE BÚSQUEDA**: Antes de devolver resultados, verifica que la especialidad solicitada coincida exactamente con los profesionales encontrados.
```

### Fase 5: Sistema de Validación de Resultados

#### 5.1 Función de Validación de Resultados
**Archivo**: `app/tools.py`
**Nueva función**

```python
def validate_search_results(query: str, results: List[Dict]) -> List[Dict]:
    """
    Valida que los resultados de búsqueda coincidan con la consulta del usuario.
    """
    query_lower = query.lower()
    
    # Detectar qué tipo de profesional se solicitó
    requested_profession = None
    if any(word in query_lower for word in ["enfermera", "enfermero", "enfermería"]):
        requested_profession = "enfermera"
    elif any(word in query_lower for word in ["nutricionista", "nutrición", "nutriólogo"]):
        requested_profession = "nutricionista"
    elif any(word in query_lower for word in ["médico", "doctor"]):
        requested_profession = "médico"
    
    if not requested_profession:
        return results
    
    # Filtrar resultados para asegurar que coincidan
    validated_results = []
    for result in results:
        title = str(result.get("title", "")).lower()
        specialty = str(result.get("specialty", "")).lower()
        
        is_valid = False
        if requested_profession == "enfermera":
            is_valid = any(word in title for word in ["enfermera", "enfermero", "tens"])
        elif requested_profession == "nutricionista":
            is_valid = "nutricionista" in title
        elif requested_profession == "médico":
            is_valid = any(word in title for word in ["médico", "doctor"])
        
        if is_valid:
            validated_results.append(result)
        else:
            logger.warning(f"⚠️ Resultado filtrado: {result.get('name', 'N/A')} - {title} no coincide con {requested_profession}")
    
    logger.info(f"✅ Validación completada: {len(results)} -> {len(validated_results)} resultados válidos")
    return validated_results
```

### Fase 6: Testing y Monitoreo

#### 6.1 Endpoint de Testing de Transcripción
**Archivo**: `app/main.py`
**Nueva función**

```python
@app.post("/test/transcription")
async def test_transcription(request: Request):
    """Endpoint para testing de transcripción de audio."""
    try:
        data = await request.json()
        audio_url = data.get("audio_url")
        
        if not audio_url:
            return {"error": "Se requiere audio_url"}
        
        # Descargar y transcribir
        audio_bytes = await download_media(audio_url, provider="evolution")
        transcription = await transcribe_audio(audio_bytes, "test.ogg", "audio/ogg")
        
        return {
            "transcription": transcription,
            "length": len(transcription),
            "words": transcription.split(),
            "medical_terms": [word for word in transcription.lower().split() 
                            if word in ["enfermera", "enfermero", "nutricionista", "médico", "doctor"]]
        }
        
    except Exception as e:
        logger.error(f"Error en test de transcripción: {str(e)}")
        return {"error": str(e)}
```

#### 6.2 Logging de Casos Problemáticos
**Archivo**: `app/main.py`
**Modificar función de procesamiento**

```python
# Agregar al final de process_message_with_batching
async def process_message_with_batching(chat_id: str, user_text: str):
    # ... código existente ...
    
    # Logging de casos problemáticos
    if any(word in user_text.lower() for word in ["enfermera", "enfermero"]):
        logger.info(f"🚨 CASO CRÍTICO: Solicitud de enfermera detectada - '{user_text}'")
        # Aquí se puede agregar alertas o notificaciones especiales
```

## 📊 Cronograma de Implementación

### Día 1-2: Diagnóstico Inicial (CRÍTICO)
- [ ] **Testing inmediato con texto escrito** - Solicitar al cliente que pruebe escribiendo
- [ ] **Análisis de logs existentes** - Revisar casos anteriores
- [ ] **Testing directo de herramientas** - Probar funciones de búsqueda
- [ ] **Determinar el escenario real** - ¿Es transcripción o lógica de búsqueda?

### Semana 1: Diagnóstico Detallado
- [ ] Implementar logging detallado
- [ ] Crear endpoint de testing
- [ ] Recopilar datos de casos problemáticos
- [ ] **Basado en Fase 0**: Enfocar en el escenario correcto

### Semana 2: Correcciones Core
- [ ] **Si es Escenario A**: Mejorar configuración de Whisper
- [ ] **Si es Escenario B**: Corregir lógica de búsqueda del agente
- [ ] Implementar validación de transcripción/búsqueda
- [ ] Actualizar mapeo de especialidades

### Semana 3: Validación y Testing
- [ ] Implementar validación de resultados
- [ ] Actualizar prompt del sistema
- [ ] Testing exhaustivo con casos reales
- [ ] **Testing tanto con audio como con texto**

### Semana 4: Monitoreo y Ajustes
- [ ] Implementar monitoreo continuo
- [ ] Ajustar parámetros basado en feedback
- [ ] Documentar cambios y mejores prácticas

## 🎯 Métricas de Éxito

1. **Precisión de Transcripción**: >95% para términos médicos
2. **Precisión de Búsqueda**: 100% para enfermeras vs nutricionistas
3. **Tiempo de Respuesta**: Mantener <3 segundos
4. **Satisfacción del Cliente**: Reducir reportes de errores a 0

## 🔧 Herramientas de Monitoreo

1. **Dashboard de Logs**: Monitorear transcripciones problemáticas
2. **Alertas Automáticas**: Notificar cuando se detecten errores
3. **Métricas de Calidad**: Tracking de precisión por tipo de consulta
4. **Feedback Loop**: Sistema para reportar y corregir errores

## 📝 Notas Adicionales

- **Backup**: Mantener versión anterior funcionando durante implementación
- **Rollback**: Plan de reversión en caso de problemas
- **Documentación**: Actualizar documentación técnica y de usuario
- **Training**: Capacitar al equipo en las nuevas funcionalidades

## 🚨 Acciones Inmediatas Requeridas

### Para el Cliente:
1. **Probar con texto escrito**: Escribir "enfermera" en lugar de usar audio
2. **Probar variaciones**: "enfermero", "enfermería", "TENS"
3. **Reportar resultados**: ¿El error persiste con texto escrito?

### Para el Equipo de Desarrollo:
1. **Revisar logs**: Buscar casos anteriores de solicitudes de enfermera
2. **Testing directo**: Probar las funciones de búsqueda directamente
3. **Análisis de datos**: Verificar si hay enfermeras en la base de datos

---

**Fecha de Creación**: $(date)
**Responsable**: Equipo de Desarrollo Healtfolio
**Estado**: Pendiente de Testing Inicial
