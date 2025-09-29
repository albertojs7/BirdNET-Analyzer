#!/bin/bash

# Script de inicio completo para BirdNET con MongoDB
# Este script maneja toda la inicialización del sistema

set -e  # Salir si cualquier comando falla

echo "🚀 INICIANDO SISTEMA BIRDNET CON MONGODB"
echo "========================================"

# Función para mostrar ayuda
show_help() {
    echo "Uso: $0 [OPCION]"
    echo ""
    echo "Opciones:"
    echo "  --build          Construir imágenes desde cero"
    echo "  --no-mongodb     Iniciar solo el microservicio (sin MongoDB)"
    echo "  --mongodb-only   Iniciar solo MongoDB y Mongo Express"
    echo "  --logs [servicio] Ver logs de un servicio específico"
    echo "  --stop           Detener todos los servicios"
    echo "  --restart        Reiniciar todos los servicios"
    echo "  --status         Ver estado de los servicios"
    echo "  --help           Mostrar esta ayuda"
    echo ""
    echo "Ejemplos:"
    echo "  $0                    # Inicio normal"
    echo "  $0 --build           # Reconstruir todo"
    echo "  $0 --logs birdnet    # Ver logs del microservicio"
    echo "  $0 --logs mongodb    # Ver logs de MongoDB"
}

# Verificar Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker no está instalado"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose no está instalado"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        echo "❌ Docker no está ejecutándose"
        exit 1
    fi
    
    echo "✅ Docker está disponible"
}

# Verificar archivos necesarios
check_files() {
    local files=("docker-compose.yml" "Dockerfile" "requirements.txt")
    
    for file in "${files[@]}"; do
        if [[ ! -f "$file" ]]; then
            echo "❌ Archivo faltante: $file"
            exit 1
        fi
    done
    
    echo "✅ Archivos de configuración encontrados"
}

# Construir imágenes
build_images() {
    echo "🔨 Construyendo imágenes Docker..."
    docker-compose build --no-cache
    echo "✅ Imágenes construidas"
}

# Iniciar servicios
start_services() {
    local services="$1"
    
    echo "🚀 Iniciando servicios: $services"
    
    if [[ -z "$services" ]]; then
        docker-compose up -d
        services="todos los servicios"
    else
        docker-compose up -d $services
    fi
    
    echo "✅ $services iniciados"
    
    # Esperar a que los servicios estén listos
    echo "⏳ Esperando a que los servicios estén listos..."
    sleep 10
    
    show_status
}

# Mostrar estado
show_status() {
    echo ""
    echo "📊 ESTADO DE LOS SERVICIOS"
    echo "========================="
    docker-compose ps
    
    echo ""
    echo "🔗 ENDPOINTS DISPONIBLES"
    echo "========================"
    echo "• BirdNET API:        http://localhost:8010"
    echo "• BirdNET WebSocket:  ws://localhost:8010/ws"
    echo "• MongoDB:            mongodb://localhost:27018"
    echo "• Mongo Express UI:   http://localhost:8081"
    echo "  - Usuario: admin"
    echo "  - Contraseña: birdnet123"
    
    echo ""
    echo "🧪 EJEMPLOS DE USO"
    echo "=================="
    echo "# Health check"
    echo "curl http://localhost:8010/health"
    echo ""
    echo "# Sesiones recientes"
    echo "curl http://localhost:8010/sessions/recent"
    echo ""
    echo "# Test WebSocket"
    echo "python simple_real_time_client.py"
}

# Ver logs
show_logs() {
    local service="$1"
    
    if [[ -z "$service" ]]; then
        echo "📋 Logs de todos los servicios:"
        docker-compose logs -f --tail=50
    else
        echo "📋 Logs de $service:"
        docker-compose logs -f --tail=50 "$service"
    fi
}

# Detener servicios
stop_services() {
    echo "🛑 Deteniendo servicios..."
    docker-compose down
    echo "✅ Servicios detenidos"
}

# Reiniciar servicios
restart_services() {
    echo "🔄 Reiniciando servicios..."
    docker-compose down
    sleep 2
    docker-compose up -d
    echo "✅ Servicios reiniciados"
    
    sleep 10
    show_status
}

# Limpiar sistema
cleanup() {
    echo "🧹 Limpiando sistema..."
    docker-compose down -v --remove-orphans
    docker system prune -f
    echo "✅ Sistema limpiado"
}

# Main
main() {
    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --build)
            check_docker
            check_files
            build_images
            start_services
            ;;
        --no-mongodb)
            check_docker
            check_files
            start_services "birdnet"
            ;;
        --mongodb-only)
            check_docker
            check_files
            start_services "mongodb mongo-express"
            ;;
        --logs)
            show_logs "$2"
            ;;
        --stop)
            stop_services
            ;;
        --restart)
            restart_services
            ;;
        --status)
            show_status
            ;;
        --cleanup)
            cleanup
            ;;
        "")
            # Inicio normal
            check_docker
            check_files
            start_services
            ;;
        *)
            echo "❌ Opción desconocida: $1"
            show_help
            exit 1
            ;;
    esac
}

# Manejar Ctrl+C
trap 'echo ""; echo "⚠️ Proceso interrumpido"; exit 1' INT

# Ejecutar
main "$@"