# 🚀 Guía de Deployment en Producción - Healtfolio

## 📋 **Pre-requisitos**

### **1. Servicios Externos Necesarios**
- ✅ **OpenAI API Key** (GPT-4/GPT-3.5)
- ✅ **Google Cloud Service Account** (Google Sheets API)
- ✅ **WhatsApp Provider**:
  - Evolution API (gratuito, menos estable)
  - Twilio WhatsApp (pago, más estable)
- ✅ **Redis** (incluido en la mayoría de plataformas)

### **2. Cuentas de Plataforma (Elige una)**
- **Railway.app** (Recomendado - más fácil)
- **Render.com** (Alternativa sólida)
- **DigitalOcean** (VPS tradicional)

---

## 🎯 **Opción 1: Railway.app (Recomendado)**

### **Paso 1: Preparar Repositorio**
```bash
# 1. Subir código a GitHub
git add .
git commit -m "Preparar para producción"
git push origin main
```

### **Paso 2: Deploy en Railway**
1. Ir a [railway.app](https://railway.app)
2. Conectar con GitHub
3. Importar repositorio `Healtfolio`
4. Railway detectará automáticamente el `Dockerfile`

### **Paso 3: Configurar Variables de Entorno**
En Railway Dashboard > Variables:
```bash
# OpenAI
OPENAI_API_KEY=sk-tu-key-aqui
OPENAI_MODEL=gpt-4o-mini

# Google Sheets
SHEET_ID=tu-google-sheet-id
SHEET_TAB=directory
GOOGLE_SERVICE_ACCOUNT_JSON=./service-account.json

# WhatsApp (Evolution API)
WHATSAPP_PROVIDER=evolution
EVOLUTION_BASE_URL=https://evolution-db.onrender.com
EVOLUTION_API_KEY=tu-api-key
EVOLUTION_INSTANCE_ID=tu-instance-id

# WhatsApp (Alternativa Twilio)
# WHATSAPP_PROVIDER=twilio
# TWILIO_ACCOUNT_SID=tu-account-sid
# TWILIO_AUTH_TOKEN=tu-auth-token
# TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Redis (Railway lo provee automáticamente)
REDIS_URL=${REDIS_URL}
```

### **Paso 4: Agregar Redis**
1. En Railway Dashboard: `+ New Service`
2. Seleccionar `Redis`
3. La variable `REDIS_URL` se conecta automáticamente

### **Paso 5: Configurar Webhook**
```bash
# URL de producción (ejemplo)
https://tu-app.railway.app/webhook

# Configurar en Evolution API o Twilio
```

**💰 Costo Railway**: ~$5-10/mes

---

## 🎯 **Opción 2: Render.com**

### **Configuración rápida**
1. Conectar repo en [render.com](https://render.com)
2. Usar el archivo `render.yaml` incluido
3. Configurar variables de entorno
4. Deploy automático

**💰 Costo Render**: ~$7-15/mes

---

## 🎯 **Opción 3: DigitalOcean VPS**

### **Configuración en VPS**
```bash
# 1. Crear Droplet Ubuntu 22.04 ($5/mes)
# 2. Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 3. Clonar repositorio
git clone https://github.com/tu-usuario/Healtfolio.git
cd Healtfolio

# 4. Crear archivo .env con variables de producción
cp env_example.txt .env
# Editar .env con valores reales

# 5. Ejecutar con Docker Compose
docker-compose up -d

# 6. Configurar nginx como reverse proxy
sudo apt install nginx
# Configurar nginx para redireccionar a puerto 8000
```

**💰 Costo DigitalOcean**: $5-10/mes + dominio

---

## 🔧 **Configuración Post-Deployment**

### **1. Verificar Servicios**
```bash
# Verificar que la app responde
curl https://tu-dominio.com/

# Debería retornar:
{
  "service": "Healtfolio WhatsApp Bot",
  "status": "active",
  "providers": {...}
}
```

### **2. Configurar Webhook WhatsApp**

#### **Para Evolution API:**
```bash
# Actualizar configure_webhook.py con nueva URL
WEBHOOK_URL = "https://tu-dominio.com/webhook"
python configure_webhook.py
```

#### **Para Twilio:**
1. Ir a [Twilio Console](https://console.twilio.com/)
2. Messaging > Settings > WhatsApp sandbox
3. Webhook URL: `https://tu-dominio.com/webhook/twilio`

### **3. Configurar Dominio Personalizado** (Opcional)
- Comprar dominio en Namecheap/GoDaddy
- Configurar DNS en la plataforma elegida
- Ejemplo: `https://healtfolio-bot.com`

### **4. Configurar Monitoreo** (Opcional)
- **Logs**: Usar logs nativos de la plataforma
- **Uptime**: UptimeRobot (gratuito)
- **Errores**: Sentry (opcional)

---

## 💰 **Costos Totales Mensuales**

### **Configuración Mínima (Railway)**
- Railway: $5-10/mes
- OpenAI API: $5-20/mes (según uso)
- **Total: $10-30/mes**

### **Configuración Premium (Twilio + Dominio)**
- Hosting: $7-15/mes
- OpenAI API: $10-50/mes
- Twilio WhatsApp: $5-20/mes
- Dominio: $10-15/año
- **Total: $25-80/mes**

---

## 🚨 **Checklist Pre-Producción**

### **Seguridad**
- ✅ Variables de entorno seguras
- ✅ API keys no hardcodeadas
- ✅ HTTPS habilitado
- ✅ Validación de webhooks habilitada (Twilio)

### **Performance**
- ✅ Redis configurado para memoria
- ✅ Límites de rate limiting (si necesario)
- ✅ Logs configurados
- ✅ Health checks funcionando

### **Backup**
- ✅ Google Sheets como backup de datos
- ✅ Variables de entorno documentadas
- ✅ Código en repositorio Git

---

## 🔄 **Mantenimiento Continuo**

### **Actualizaciones**
```bash
# 1. Actualizar código
git pull origin main

# 2. Rebuild automático (Railway/Render)
# O manual rebuild en plataforma

# 3. Verificar funcionamiento
curl https://tu-dominio.com/
```

### **Monitoreo**
- Revisar logs diariamente
- Monitorear uso de OpenAI API
- Verificar uptime del bot
- Actualizar base de datos en Google Sheets

### **Escalabilidad**
- Aumentar RAM/CPU si es necesario
- Considerar múltiples workers de uvicorn
- Implementar load balancing si el tráfico crece

---

## 📞 **URLs de Webhook Finales**

Una vez deployado, tus webhooks serán:
- **Evolution API**: `https://tu-dominio.com/webhook`
- **Twilio**: `https://tu-dominio.com/webhook/twilio`
- **Status**: `https://tu-dominio.com/` 