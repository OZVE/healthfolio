#!/bin/bash

# Script para construir Docker con retry automático
# Soluciona problemas temporales de Docker Hub

echo "🐳 Iniciando build de Docker con retry automático..."

# Configuración
MAX_ATTEMPTS=3
ATTEMPT=1
SUCCESS=false

# Lista de imágenes base a probar en orden de preferencia
IMAGES=(
    "python:3.11-slim"
    "python:3.10-slim" 
    "python:3.11-alpine"
    "python:3.10-alpine"
    "ubuntu:22.04"
)

while [ $ATTEMPT -le $MAX_ATTEMPTS ] && [ "$SUCCESS" = false ]; do
    echo "🔄 Intento $ATTEMPT de $MAX_ATTEMPTS"
    
    # Probar cada imagen base
    for IMAGE in "${IMAGES[@]}"; do
        echo "📦 Probando imagen: $IMAGE"
        
        # Crear Dockerfile temporal
        cat > Dockerfile.temp << EOF
FROM $IMAGE

# Instalar dependencias del sistema (solo para Ubuntu)
RUN if [ "\$BASE_IMAGE" = "ubuntu" ]; then \
        apt-get update && apt-get install -y python3.11 python3-pip; \
    fi

# Configurar directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY ./app ./app
COPY start.sh ./start.sh

# Hacer ejecutable el script
RUN chmod +x start.sh

# Crear usuario no-root para seguridad
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser

# Exponer puerto
EXPOSE 8000

# Comando para ejecutar la aplicación  
CMD ["./start.sh"]
EOF
        
        # Intentar build
        if docker build -f Dockerfile.temp -t healtfolio:latest .; then
            echo "✅ Build exitoso con imagen: $IMAGE"
            SUCCESS=true
            
            # Copiar Dockerfile temporal al original
            cp Dockerfile.temp Dockerfile
            rm Dockerfile.temp
            break
        else
            echo "❌ Falló con imagen: $IMAGE"
            rm Dockerfile.temp
        fi
    done
    
    if [ "$SUCCESS" = false ]; then
        echo "⏳ Esperando 30 segundos antes del siguiente intento..."
        sleep 30
        ATTEMPT=$((ATTEMPT + 1))
    fi
done

if [ "$SUCCESS" = true ]; then
    echo "🎉 Build completado exitosamente!"
    echo "📦 Imagen creada: healtfolio:latest"
else
    echo "💥 Falló después de $MAX_ATTEMPTS intentos"
    echo "🔧 Soluciones adicionales:"
    echo "   1. Verificar conectividad a Docker Hub"
    echo "   2. Limpiar cache de Docker: docker system prune -a"
    echo "   3. Usar VPN si hay problemas de red"
    echo "   4. Probar en horarios de menor tráfico"
    exit 1
fi
