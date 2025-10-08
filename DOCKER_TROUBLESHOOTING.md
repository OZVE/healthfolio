# 🐳 GUÍA DE SOLUCIÓN DE PROBLEMAS DOCKER - HEALTFOLIO

## ❌ ERROR: 502 Bad Gateway - Docker Hub

### **Problema:**
```
ERROR: failed to build: failed to solve: python:3.12-slim: failed to resolve source metadata for docker.io/library/python:3.12-slim: failed to copy: httpReadSeeker: failed open: unexpected status code https://registry-1.docker.io/v2/library/python/manifests/sha256:0b29ab9e420820f53d1cd5ce0157dfe07bea8a7cff5b4754d6d95c07b0e5bc47: 502 Bad Gateway
```

### **Causas:**
1. **Problemas temporales de Docker Hub** (502 Bad Gateway)
2. **Rate limiting** de Docker Hub para usuarios no autenticados
3. **Problemas de conectividad** de red
4. **Imagen corrupta** en cache local
5. **Problemas de DNS** o firewall

---

## 🔧 SOLUCIONES PASO A PASO

### **1. Solución Rápida - Cambiar Imagen Base**

```bash
# Cambiar de python:3.12-slim a python:3.11-slim
FROM python:3.11-slim
```

**Ya aplicado en el Dockerfile principal**

### **2. Limpiar Cache de Docker**

```bash
# Limpiar todo el cache de Docker
docker system prune -a

# Limpiar solo imágenes
docker image prune -a

# Limpiar solo contenedores
docker container prune

# Limpiar volúmenes
docker volume prune

# Limpiar redes
docker network prune
```

### **3. Usar Script de Build con Retry**

```bash
# Hacer ejecutable el script
chmod +x build-with-retry.sh

# Ejecutar build con retry automático
./build-with-retry.sh
```

### **4. Build Manual con Imágenes Alternativas**

```bash
# Opción 1: Python 3.11
docker build -t healtfolio:latest .

# Opción 2: Python 3.10
sed 's/python:3.11-slim/python:3.10-slim/' Dockerfile > Dockerfile.310
docker build -f Dockerfile.310 -t healtfolio:latest .

# Opción 3: Alpine (más liviano)
sed 's/python:3.11-slim/python:3.11-alpine/' Dockerfile > Dockerfile.alpine
docker build -f Dockerfile.alpine -t healtfolio:latest .
```

### **5. Autenticación en Docker Hub**

```bash
# Login en Docker Hub (opcional, puede ayudar con rate limits)
docker login

# Usar token de acceso personal
echo "tu_token_aqui" | docker login --username tu_usuario --password-stdin
```

### **6. Usar Registry Alternativo**

```bash
# Usar registry de Google
FROM gcr.io/distroless/python3-debian11

# O usar registry de Microsoft
FROM mcr.microsoft.com/vscode/devcontainers/python:3.11
```

---

## 🚀 SOLUCIONES PARA PRODUCCIÓN

### **1. Dockerfile Optimizado para Producción**

```bash
# Usar el Dockerfile optimizado
cp Dockerfile.prod Dockerfile
docker build -t healtfolio:prod .
```

### **2. Multi-stage Build (Recomendado)**

```dockerfile
# Stage 1: Build
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY ./app ./app
COPY start.sh ./start.sh
RUN chmod +x start.sh
CMD ["./start.sh"]
```

### **3. Usar .dockerignore**

```bash
# Crear .dockerignore para optimizar build
cat > .dockerignore << EOF
.git
.gitignore
README.md
Dockerfile*
.dockerignore
node_modules
npm-debug.log
.venv
venv
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
pip-log.txt
pip-delete-this-directory.txt
.tox
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.DS_Store
.vscode
.idea
EOF
```

---

## 🔍 DIAGNÓSTICO AVANZADO

### **1. Verificar Conectividad a Docker Hub**

```bash
# Test de conectividad
curl -I https://registry-1.docker.io/v2/

# Test de DNS
nslookup registry-1.docker.io

# Test de descarga de imagen
docker pull hello-world
```

### **2. Verificar Rate Limits**

```bash
# Verificar límites actuales
curl -I https://registry-1.docker.io/v2/

# Headers importantes:
# X-RateLimit-Limit: 100
# X-RateLimit-Remaining: 99
```

### **3. Logs Detallados de Docker**

```bash
# Build con logs detallados
docker build --progress=plain --no-cache -t healtfolio:latest .

# Ver logs del daemon de Docker
docker system events

# Ver información del sistema
docker system df
```

---

## 🛠️ COMANDOS DE EMERGENCIA

### **Si todo falla:**

```bash
# 1. Reset completo de Docker
sudo systemctl stop docker
sudo rm -rf /var/lib/docker
sudo systemctl start docker

# 2. Usar Podman como alternativa
podman build -t healtfolio:latest .

# 3. Build local sin Docker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

---

## 📋 CHECKLIST DE SOLUCIÓN

- [ ] ✅ Cambiar imagen base a `python:3.11-slim`
- [ ] 🔄 Limpiar cache de Docker
- [ ] 🚀 Usar script de build con retry
- [ ] 🔐 Configurar autenticación Docker Hub
- [ ] 📦 Usar .dockerignore
- [ ] 🏗️ Implementar multi-stage build
- [ ] 🔍 Verificar conectividad de red
- [ ] 📊 Monitorear rate limits

---

## 🎯 PREVENCIÓN FUTURA

### **1. Usar Imágenes Estables**
- Evitar versiones `latest` o muy nuevas
- Usar versiones LTS (Long Term Support)
- Probar builds localmente antes de producción

### **2. Implementar CI/CD Robusto**
```yaml
# .github/workflows/docker.yml
name: Docker Build
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker image
        run: |
          for attempt in {1..3}; do
            if docker build -t healtfolio:latest .; then
              break
            fi
            echo "Attempt $attempt failed, retrying..."
            sleep 30
          done
```

### **3. Monitoreo de Docker Hub**
- Configurar alertas para problemas de Docker Hub
- Usar mirrors locales cuando sea posible
- Implementar fallbacks automáticos

---

## 📞 CONTACTO Y SOPORTE

Si los problemas persisten:

1. **Verificar estado de Docker Hub**: https://status.docker.com/
2. **Revisar logs del sistema**: `journalctl -u docker`
3. **Contactar soporte técnico** con logs detallados
4. **Considerar alternativas**: Podman, Buildah, o build local

---

*Última actualización: $(date)*
