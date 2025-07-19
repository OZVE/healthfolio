# Health‑Pro Agent (Multi-Provider WhatsApp Edition)

Agente de IA con Model‑Context Protocol que opera en WhatsApp mediante **Evolution API** o **Twilio** y consulta un Google Sheet de profesionales de la salud.

## 🆕 **Nuevas Características**

- ✅ **Dual Provider Support**: Evolution API + Twilio WhatsApp
- ✅ **Configuración Flexible**: Cambio fácil entre proveedores
- ✅ **Diagnóstico Avanzado**: Herramientas mejoradas de debugging
- ✅ **Webhooks Separados**: Endpoints específicos por proveedor

## ⚡ Ejecución Rápida

### 1️⃣ **Verificar y iniciar Redis**
```bash
# Verificar si está corriendo
docker ps | findstr redis

# Iniciar Redis existente
docker start redis-healtfolio

# O crear nuevo contenedor
docker run -d -p 6379:6379 --name redis-healtfolio redis:7
```

### 2️⃣ **Instalar dependencias actualizadas**
```bash
# Ir al directorio del proyecto
cd C:\dev\Healtfolio

# Activar entorno virtual
.\venv\Scripts\Activate.ps1

# Instalar nuevas dependencias (incluye Twilio)
pip install -r requirements.txt
```

### 3️⃣ **Ejecutar aplicación**
```bash
# Ejecutar aplicación
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4️⃣ **Exponer con ngrok (Nueva terminal)**
```bash
# Agregar ngrok al PATH (primera vez en sesión)
$env:PATH += ";C:\Users\Osman\Downloads\ngrok-v3-stable-windows-amd64"

# Ejecutar ngrok
ngrok http 8000

# Obtener URL pública
curl http://localhost:4040/api/tunnels
```

## 🔧 Configuración

### **Variables de Entorno (.env)**

```bash
# === CONFIGURACIÓN GENERAL ===
WHATSAPP_PROVIDER=evolution  # "evolution" o "twilio"

# === EVOLUTION API ===
EVOLUTION_BASE_URL=https://evolution-db.onrender.com
EVOLUTION_API_KEY=tu_api_key_aqui
EVOLUTION_INSTANCE_ID=tu_instance_id_aqui

# === TWILIO WHATSAPP ===
TWILIO_ACCOUNT_SID=tu_account_sid_aqui
TWILIO_AUTH_TOKEN=tu_auth_token_aqui
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# === OPENAI ===
OPENAI_API_KEY=sk-tu_openai_key_aqui
OPENAI_MODEL=gpt-4o-mini

# === GOOGLE SHEETS ===
GOOGLE_SERVICE_ACCOUNT_JSON=./service-account.json
SHEET_ID=tu_google_sheet_id_aqui
SHEET_TAB=directory

# === REDIS ===
REDIS_URL=redis://localhost:6379/0
```

## 📱 **Configuración por Proveedor**

### **Opción A: Evolution API (Existente)**

1. **Configurar webhook Evolution API:**
```bash
# Actualizar configure_webhook.py con nueva URL ngrok
python configure_webhook.py
```

2. **Webhook endpoint:** `/webhook`

### **Opción B: Twilio WhatsApp (Nuevo)**

1. **Obtener credenciales de Twilio:**
   - Ir a [Twilio Console](https://console.twilio.com/)
   - Copiar Account SID y Auth Token
   - Configurar WhatsApp Sandbox

2. **Configurar webhook de Twilio:**
```bash
# Configurar automáticamente
python configure_twilio_webhook.py

# O manualmente en Twilio Console:
# Messaging > Settings > WhatsApp sandbox settings
# When a message comes in: https://tu-ngrok-url.ngrok-free.app/webhook/twilio
```

3. **Webhook endpoint:** `/webhook/twilio`

4. **Cambiar proveedor en .env:**
```bash
WHATSAPP_PROVIDER=twilio
```

## 🔍 **Diagnóstico y Testing**

### **Diagnóstico completo:**
```bash
python debug_webhook.py
```

### **Probar específicamente Twilio:**
```bash
python test_twilio_webhook.py
```

### **Verificar estado del servidor:**
```bash
# Ir a http://localhost:8000/ para ver estado de ambos proveedores
curl http://localhost:8000/
```

## 📡 **Endpoints Disponibles**

| Endpoint | Proveedor | Descripción |
|----------|-----------|-------------|
| `GET /` | Ambos | Estado del servicio y proveedores |
| `GET /health` | Ambos | Health check detallado |
| `GET /batches` | Ambos | Estado de batches de mensajes |
| `POST /batches/{chat_id}/force` | Ambos | Forzar procesamiento de batch |
| `POST /webhook` | Evolution API | Webhook para Evolution API |
| `POST /webhook/twilio` | Twilio | Webhook para Twilio WhatsApp |

## 🔀 **Cambio Entre Proveedores**

Para cambiar de proveedor, simplemente actualiza la variable de entorno:

```bash
# Para usar Evolution API
WHATSAPP_PROVIDER=evolution

# Para usar Twilio
WHATSAPP_PROVIDER=twilio
```

El sistema automáticamente:
- ✅ Detecta el proveedor configurado
- ✅ Usa el endpoint correcto
- ✅ Aplica el formato de mensaje apropiado
- ✅ Mantiene fallback a Evolution API si Twilio falla

## 🛠️ **Instalación Inicial Completa**

### **1. Crear entorno virtual**
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### **2. Configurar Google Sheets**
1. Crear service account en Google Cloud Console
2. Descargar `service-account.json`
3. Compartir Google Sheet con email del service account
4. Crear pestaña "directory" con columnas:
   - name, specialty, coverage_area, phone, email

### **3. Configurar Redis**
```bash
docker run -d -p 6379:6379 --name redis-healtfolio redis:7
```

### **4. Configurar WhatsApp Provider**

**Para Evolution API:**
- Configurar variables EVOLUTION_*
- Ejecutar `python configure_webhook.py`

**Para Twilio:**
- Crear cuenta en Twilio
- Configurar WhatsApp Sandbox
- Configurar variables TWILIO_*
- Ejecutar `python configure_twilio_webhook.py`

## 🎯 **Uso del Bot**

### **Comandos de ejemplo:**
- "Hola"
- "Necesito un cardiólogo en Madrid"
- "Busco un dermatólogo en Barcelona"
- "¿Podrías darme el contacto del Dr. García?"

### **Flujo de conversación:**
1. Usuario solicita especialista
2. Bot busca en Google Sheets
3. Bot muestra lista de profesionales
4. Usuario elige uno específico
5. Bot proporciona datos de contacto completos

## 📊 **Arquitectura Actualizada**

```
┌─────────────────┐    ┌─────────────────┐
│   WhatsApp      │    │   WhatsApp      │
│   (Evolution)   │    │   (Twilio)      │
└─────────┬───────┘    └─────────┬───────┘
          │                      │
          ▼                      ▼
┌─────────────────────────────────────────┐
│         FastAPI Server                  │
│  ┌─────────────┐ ┌─────────────────────┐│
│  │ /webhook    │ │ /webhook/twilio     ││
│  │ (Evolution) │ │ (Twilio)           ││
│  └─────────────┘ └─────────────────────┘│
└─────────┬───────────────────────────────┘
          ▼
┌─────────────────────────────────────────┐
│         MCP Gateway                     │
│  ┌─────────────┐ ┌─────────────────────┐│
│  │ OpenAI GPT  │ │ Google Sheets      ││
│  │ Processing  │ │ Professional DB    ││
│  └─────────────┘ └─────────────────────┘│
└─────────┬───────────────────────────────┘
          ▼
┌─────────────────────────────────────────┐
│            Redis Memory                 │
│        (Conversation History)           │
└─────────────────────────────────────────┘
```

## 🆘 **Solución de Problemas**

### **Error: "Twilio no configurado"**
```bash
# Verificar variables de entorno
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('SID:', os.getenv('TWILIO_ACCOUNT_SID')); print('Token:', '***' if os.getenv('TWILIO_AUTH_TOKEN') else 'No configurado')"
```

### **Error: "Webhook no válido"**
- Verificar que la URL de ngrok esté actualizada
- Comprobar que el servidor esté corriendo en puerto 8000
- Validar configuración en Twilio Console

### **Error: "No se puede conectar a Redis"**
```bash
docker ps | findstr redis
docker start redis-healtfolio
```

### **Logs detallados:**
```bash
# Ver logs en tiempo real
uvicorn app.main:app --reload --log-level debug
```

## 📖 **Documentación Adicional**

- [Twilio WhatsApp API](https://www.twilio.com/docs/whatsapp)
- [Evolution API Docs](https://doc.evolution-api.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenAI API Reference](https://platform.openai.com/docs/)

## ✨ **Características Avanzadas**

- 🔄 **Auto-fallback**: Si Twilio falla, automáticamente usa Evolution API
- 🛡️ **Webhook Validation**: Validación de firmas para seguridad
- 📊 **Status Monitoring**: Endpoint de estado para monitoreo
- 🧪 **Comprehensive Testing**: Suite completa de pruebas
- 📱 **Multi-format Support**: Soporte para diferentes formatos de mensaje
- 💾 **Persistent Memory**: Memoria conversacional con Redis
- 🔍 **Smart Search**: Búsqueda inteligente con mapeo de especialidades
- 📦 **Message Batching**: Agrupa mensajes consecutivos para conversaciones naturales

## 📦 **Sistema de Batching de Mensajes**

El sistema implementa un mecanismo inteligente de agrupación de mensajes que mejora significativamente la experiencia de conversación:

### **¿Cómo Funciona?**

1. **Agrupación Automática**: Cuando un usuario envía múltiples mensajes seguidos, el sistema los agrupa automáticamente
2. **Timeout Inteligente**: Espera 3 segundos después del último mensaje antes de procesar
3. **Combinación Inteligente**: Une los mensajes de manera natural (saludos + solicitudes, frases incompletas, etc.)
4. **Procesamiento Único**: Procesa todos los mensajes como una sola conversación

### **Ejemplo de Funcionamiento**

**Antes (sin batching):**
```
Usuario: "Hola"
Bot: "¡Hola! ¿En qué puedo ayudarte?"

Usuario: "Necesito un"
Bot: "¿Podrías completar tu mensaje?"

Usuario: "cardiólogo"
Bot: "Entiendo que buscas un cardiólogo..."

Usuario: "en Santiago"
Bot: "Perfecto, buscaré cardiólogos en Santiago..."
```

**Después (con batching):**
```
Usuario: "Hola"
Usuario: "Necesito un"
Usuario: "cardiólogo"
Usuario: "en Santiago"
[20 segundos de espera]
Bot: "¡Hola! Te ayudo a encontrar cardiólogos en Santiago..."
```

### **Configuración**

- **Timeout**: 20 segundos (configurable)
- **Tamaño máximo**: 10 mensajes por batch
- **Combinación inteligente**: Detecta saludos, frases incompletas, etc.

### **Monitoreo**

```bash
# Ver estado de batches activos
curl http://localhost:8000/batches

# Forzar procesamiento de un batch específico
curl -X POST http://localhost:8000/batches/123456789/force
```

## 📋 **Proceso Paso a Paso para tu Número**

### **Método Automático (Recomendado):**

```bash
# 1. Configurar credenciales de Twilio en .env
# 2. Ejecutar el configurador interactivo:
python setup_twilio_sandbox.py
```

### **Método Manual:**

#### **1. Ir al Sandbox de Twilio:**
🔗 https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn

#### **2. Encontrar tu código único:**
En la pantalla verás algo como:
```
To use the Sandbox for WhatsApp, send this code via WhatsApp:
join clever-tiger
```
⚠️ **IMPORTANTE:** Cada cuenta tiene un código diferente

#### **3. Desde tu WhatsApp:**
- 📱 Abre WhatsApp en tu teléfono
- 📞 Envía mensaje a: **+1 415 523 8886**
- 💬 Escribe exactamente: `join tu-codigo-unico`
- 📨 Ejemplo: `join clever-tiger`

#### **4. Confirmación:**
Recibirás un mensaje como:
```
✅ Joined sandbox! You can now send/receive messages.
Reply 'sandbox' to see sandbox participants.
Reply 'stop' to leave the sandbox.
```

#### **5. Configurar Webhook:**
En la misma pantalla del sandbox:
```
When a message comes in: https://tu-ngrok-url.ngrok-free.app/webhook/twilio
HTTP Method: POST
```

## 🔧 **Configuración en tu .env:**

```bash
# Cambiar proveedor a Twilio
WHATSAPP_PROVIDER=twilio

# Configurar Twilio (obtener de console.twilio.com)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=tu_auth_token_aqui
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

## ⚠️ **Puntos Importantes:**

1. **El sandbox es gratuito** pero tiene limitaciones:
   - Solo números que se unieron pueden enviar/recibir mensajes
   - Expira cada 3 días de inactividad
   - Para producción necesitas WhatsApp Business API

2. **Tu número específico:**
   - Solo tu número podrá interactuar con el bot
   - Si quieres que otros usen el bot, deben unirse al sandbox también

3. **Renovación:**
   - Si el sandbox expira, simplemente repite el proceso `join codigo`

## 🧪 **Probar que Funciona:**

```bash
# 1. Verificar configuración
python debug_webhook.py

# 2. Iniciar servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. Configurar ngrok
ngrok http 8000

# 4. Enviar 'Hola' desde tu WhatsApp al +1 415 523 8886
```

¿Quieres que ejecutemos el configurador interactivo o prefieres hacerlo manualmente paso a paso?