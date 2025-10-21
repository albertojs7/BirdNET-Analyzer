# BirdNET Microservice con MongoDB

Microservicio FastAPI con WebSockets que implementa arquitectura limpia para análisis de aves con soporte para análisis en tiempo real y persistencia en base de datos NoSQL.

## Características

- **Análisis en tiempo real**: Stream de audio con detecciones instantáneas usando WebSockets
- **Persistencia MongoDB**: Almacenamiento de sesiones y detecciones en base de datos NoSQL
- **API REST**: Endpoints para integración con otros microservicios (Pokedex)
- **Arquitectura limpia**: Código organizado y mantenible siguiendo principios SOLID
- **Docker Compose**: Orquestación completa con MongoDB, Mongo Express y microservicio
- **Plugin BirdNET**: Integración real con modelos de análisis de aves

## Inicio Rápido

```bash
# Clonar y navegar al directorio
cd microservice/

# Iniciar todo el sistema (MongoDB + BirdNET)
./start.sh

# Solo el microservicio (sin base de datos)
./start.sh --no-mongodb

# Reconstruir imágenes desde cero
./start.sh --build
```

## Requisitos

- **Docker** y **Docker Compose**
- **Python 3.10+** (para desarrollo local)
- **Puertos disponibles**: 8000, 27017, 8081

## Servicios Disponibles

- **BirdNET API**: http://localhost:8000
- **BirdNET WebSocket**: ws://localhost:8000/ws
- **MongoDB**: mongodb://localhost:27017
- **Mongo Express UI**: http://localhost:8081
  - Usuario: admin
  - Contraseña: birdnet123

## Arquitectura del Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Expo/React    │    │  Pokedex API    │    │   BirdNET API   │
│   Mobile App    │    │  Microservice   │    │  Microservice   │
│                 │    │                 │    │                 │
│ • Audio capture │    │ • Species data  │    │ • Real-time     │
│ • WebSocket     │◄──►│ • User profiles │◄──►│   analysis      │
│ • Real-time UI  │    │ • Integration   │    │ • Session mgmt  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  PostgreSQL/    │    │    MongoDB      │
                       │   Local DB      │    │   (Sessions &   │
                       │                 │    │   Detections)   │
                       └─────────────────┘    └─────────────────┘
```

### Conexiones

- **Comunicación HTTP/REST**: Para datos batch (resúmenes de sesiones)
- **WebSocket directo**: Para tiempo real (Expo ↔ BirdNET)

## Estructura del Proyecto

```
microservice/
├── application/              # Capa de Aplicación
├── domain/                   # Capa de Dominio
├── infrastructure/           # Capa de Infraestructura
│   ├── adapters/            # Adaptadores externos
│   │   └── birdnet_adapter.py
│   ├── database/            # Adaptadores de BD
│   │   └── mongodb_adapter.py
│   └── repositories/        # Repositorios
├── interfaces/              # Capa de Interfaces
│   ├── websocket_controller.py # WebSocket tiempo real
│   └── sessions_api.py      # API REST para microservicios
├── plugin/                  # Plugin BirdNET
│   └── birdnet_plugin.py
├── docker-compose.yml       # Orquestación Docker
├── Dockerfile              # Imagen del microservicio
├── requirements.txt        # Dependencias Python
├── start.sh               # Script de inicio
├── config.py              # Configuración
├── main.py                # Punto de entrada
├── simple_real_time_client.py # Cliente de prueba
└── README.md              # Este archivo
```

## Base de Datos MongoDB

### Servicios Docker

```yaml
# docker-compose.yml
services:
  birdnet-service:      # Microservicio principal
    ports: ["8000:8000"]
    volumes:
      - ../:/birdnet_root     # Todo el proyecto BirdNET
      - ./:/app              # Código del microservicio (hot reload)
    
  mongodb:              # Base de datos NoSQL
    ports: ["27017:27017"]
    
  mongo-express:        # UI para MongoDB
    ports: ["8081:8081"]
```

### Variables de Entorno

```bash
# MongoDB
MONGODB_URL=mongodb://admin:birdnet123@mongodb:27017/birdnet_db?authSource=admin

# BirdNET
PYTHONPATH=/birdnet_root:/app
LOG_LEVEL=INFO
```

### Estructura de Documentos

**Colección: sessions**
```json
{
  "_id": "ObjectId",
  "session_id": "uuid-generado",
  "status": "active|completed",
  "created_at": "ISODate",
  "ended_at": "ISODate",
  "total_chunks": 150,
  "total_detections": 25,
  "unique_species": 8,
  "metadata": {
    "session_type": "real_time",
    "client_info": {}
  }
}
```

**Colección: detections**
```json
{
  "_id": "ObjectId",
  "session_id": "uuid-de-sesion",
  "species_name": "Northern Cardinal",
  "species_code": "norcad",
  "confidence": 0.89,
  "start_time": 12.5,
  "end_time": 15.2,
  "detected_at": "ISODate",
  "chunk_timestamp": 1672531200000,
  "processing_info": {
    "processing_time": 1.23,
    "chunk_sequence": 45,
    "is_new_species": true
  }
}
```

## API Endpoints

### WebSocket (Tiempo Real)

```javascript
// Conectar al WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');

// Iniciar sesión de tiempo real
ws.send(JSON.stringify({
    "type": "start_real_time_listening"
}));

// Enviar chunk de audio
ws.send(JSON.stringify({
    "type": "send_real_time_audio",
    "session_id": "uuid-de-sesion",
    "audio": "base64-encoded-audio",
    "timestamp": Date.now()
}));

// Finalizar sesión
ws.send(JSON.stringify({
    "type": "stop_real_time_listening",
    "session_id": "uuid-de-sesion"
}));
```

### REST API (Integración entre Microservicios)

```bash
# Health check
curl http://localhost:8000/health

# Sesiones recientes (para Pokedex)
curl http://localhost:8000/sessions/recent?limit=10

# Resumen de sesión específica
curl http://localhost:8000/sessions/{session_id}/summary

# Detecciones de una sesión
curl http://localhost:8000/sessions/{session_id}/detections

# Especies detectadas en una sesión
curl http://localhost:8000/sessions/{session_id}/species

# Marcar sesión como procesada
curl -X POST http://localhost:8000/sessions/{session_id}/mark-processed
```

## Integración con Pokedex Microservice

### Flujo de Datos

1. **Usuario graba audio** en Expo app
2. **Expo envía chunks** via WebSocket a BirdNET
3. **BirdNET analiza** y guarda detecciones en MongoDB
4. **BirdNET responde** con detecciones en tiempo real
5. **Usuario termina sesión** en Expo
6. **Pokedex consulta** resumen de sesión via REST API
7. **Pokedex integra** datos con información local de especies

## Testing

### 🧪 Pruebas Unitarias

La suite incluye **29 pruebas unitarias** organizadas en 4 niveles:

#### Instalar dependencias
```bash
pip install pytest pytest-asyncio pytest-mock pytest-cov
```

#### Ejecutar pruebas
```bash
# Todas las pruebas
./run_tests.sh all

# O con pytest directamente
pytest tests/ -v
```

#### Suites específicas
```bash
./run_tests.sh domain        # Pruebas de dominio (7 tests)
./run_tests.sh app           # Pruebas de aplicación (6 tests)
./run_tests.sh infra         # Pruebas de infraestructura (6 tests)
./run_tests.sh integration   # Pruebas de integración (10 tests)
```

#### Con cobertura de código
```bash
./run_tests.sh coverage
# Abre: htmlcov/index.html
```

#### Pruebas rápidas (sin integraciones lentas)
```bash
./run_tests.sh fast
```

#### En modo watch (ejecuta al guardar cambios)
```bash
./run_tests.sh watch
```

### 🧪 Pruebas Manuales

#### WebSocket (Tiempo Real)

```bash
# Test básico
python3 simple_real_time_client.py

# Test con latencia
python3 real_time_test_client.py
```

### API REST

```bash
# Health check
curl http://localhost:8000/health

# Sesiones recientes
curl http://localhost:8000/sessions/recent

# Estado de contenedores
./start.sh --status
```

### MongoDB

```bash
# Conectar a MongoDB directamente
docker exec -it birdnet-mongodb mongosh -u admin -p birdnet123 --authenticationDatabase admin

# Ver sesiones
use birdnet_db
db.sessions.find().limit(5)

# Ver detecciones
db.detections.find().limit(10)
```

## Monitoreo

### Logs en Tiempo Real

```bash
# Todos los servicios
./start.sh --logs

# Solo BirdNET
./start.sh --logs birdnet-service

# Solo MongoDB
./start.sh --logs mongodb
```

### Mongo Express UI

- **URL**: http://localhost:8081
- **Usuario**: admin
- **Contraseña**: birdnet123

### Métricas

```bash
# Estado de contenedores
./start.sh --status

# Uso de recursos
docker stats

# Conectividad
curl http://localhost:8000/health
```

## Desarrollo

### Hot Reload para Desarrollo

Los cambios en código Python se reflejan automáticamente en el contenedor gracias a los volúmenes Docker configurados:

```bash
# Para reflejar cambios
docker compose restart birdnet-service

# Ver logs en tiempo real
./start.sh --logs birdnet-service
```

### Configuración Local (sin Docker)

```bash
# Instalar dependencias
pip install -r requirements.txt

# Variables de entorno
export MONGODB_URL="mongodb://admin:birdnet123@localhost:27017/birdnet_db?authSource=admin"
export PYTHONPATH="/path/to/BirdNET-Analyzer"

# Ejecutar sin Docker
python main.py
```

## Monitoreo

### Logs en Tiempo Real

```bash
# Todos los servicios
./start.sh --logs

# Solo BirdNET
./start.sh --logs birdnet-service

# Solo MongoDB
./start.sh --logs mongodb
```

### Métricas

```bash
# Estado de contenedores
./start.sh --status

# Uso de recursos
docker stats

# Conectividad
curl http://localhost:8000/health
```

## Resolución de Problemas

### Problemas Comunes

**MongoDB no conecta**
```bash
# Verificar que el contenedor esté corriendo
docker compose ps mongodb

# Ver logs de MongoDB
./start.sh --logs mongodb

# Reiniciar solo MongoDB
docker compose restart mongodb
```

**Audio no se procesa**
```bash
# Verificar plugin BirdNET
curl http://localhost:8000/health

# Ver logs del microservicio
./start.sh --logs birdnet-service
```

**WebSocket desconecta**
```bash
# Verificar conexión
python3 simple_real_time_client.py

# Verificar logs del servicio
docker logs birdnet-microservice --tail=50
```

**Dependencias faltantes**
```bash
# Reconstruir imagen con nuevas dependencias
./start.sh --build

# Verificar instalación en contenedor
docker exec birdnet-microservice pip list
```

### Logs Importantes

```bash
# Conexión MongoDB exitosa
✅ MongoDB conectado exitosamente

# Sesión creada
✅ Sesión MongoDB creada: uuid-de-sesion

# Detección guardada
🐦 Detección guardada: Northern Cardinal en sesión uuid

# Sesión finalizada
🔚 Sesión finalizada: uuid (25 detecciones)
```

## Escalabilidad y Producción

### Múltiples Instancias

```bash
# Escalar el microservicio
docker compose up -d --scale birdnet-service=3

# Con load balancer (nginx)
docker compose -f docker-compose.prod.yml up -d
```

### URLs para diferentes entornos

```javascript
const getWebSocketUrl = () => {
    if (__DEV__) {
        if (Platform.OS === 'android') {
            return 'ws://10.0.2.2:8000/ws'; // Emulador Android
        } else {
            return 'ws://localhost:8000/ws'; // iOS Simulator
        }
    } else {
        return 'wss://tu-api.com/birdnet/ws'; // Producción
    }
};
```

## Referencias

- **BirdNET**: https://github.com/kahst/BirdNET-Analyzer
- **FastAPI**: https://fastapi.tiangolo.com/
- **MongoDB**: https://docs.mongodb.com/
- **Docker Compose**: https://docs.docker.com/compose/
- **Clean Architecture**: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html

---

**¿Listo para empezar?**

```bash
./start.sh
```