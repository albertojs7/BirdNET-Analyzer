# 🐦 BirdNET Microservice con MongoDB - GUÍA COMPLETA

Microservicio de análisis de aves en tiempo real con persistencia NoSQL y arquitectura para integración con otros microservicios.

## 🚀 Inicio Rápido

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

## 📋 Requisitos

- **Docker** y **Docker Compose**
- **Python 3.10+** (para desarrollo local)
- **8GB RAM** mínimo
- **Puertos disponibles**: 8010, 27018, 8081

## 🏗️ Arquitectura

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

### Patrón de Microservicios

- **✅ Separación clara**: Cada servicio maneja su propia base de datos
- **✅ Comunicación HTTP/REST**: Para datos batch (resúmenes de sesiones)
- **✅ WebSocket directo**: Para tiempo real (Expo ↔ BirdNET)
- **✅ Escalabilidad**: Cada servicio puede escalarse independientemente

## 🔌 Endpoints

### WebSocket (Tiempo Real)
```javascript
// Conectar al WebSocket
const ws = new WebSocket('ws://localhost:8010/ws');

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
```

### REST API (Integración entre Microservicios)

```bash
# Health check
curl http://localhost:8010/health

# Sesiones recientes (para Pokedex)
curl http://localhost:8010/sessions/recent?limit=10

# Resumen de sesión específica
curl http://localhost:8010/sessions/{session_id}/summary

# Detecciones de una sesión
curl http://localhost:8010/sessions/{session_id}/detections

# Especies detectadas en una sesión
curl http://localhost:8010/sessions/{session_id}/species
```

## 🗄️ Base de Datos MongoDB

### Estructura de Documentos

**Colección: `sessions`**
```json
{
  "_id": "ObjectId",
  "session_id": "uuid-generado",
  "status": "active|completed",
  "created_at": ISODate,
  "ended_at": ISODate,
  "total_chunks": 150,
  "total_detections": 25,
  "unique_species": 8,
  "metadata": {
    "session_type": "real_time",
    "client_info": {...}
  }
}
```

**Colección: `detections`**
```json
{
  "_id": "ObjectId",
  "session_id": "uuid-de-sesion",
  "species_name": "Northern Cardinal",
  "species_code": "norcad",
  "confidence": 0.89,
  "start_time": 12.5,
  "end_time": 15.2,
  "detected_at": ISODate,
  "chunk_timestamp": 1672531200000,
  "processing_info": {
    "processing_time": 1.23,
    "chunk_sequence": 45,
    "is_new_species": true
  }
}
```

## 🐳 Docker

### Servicios Contenidos

```yaml
# docker-compose.yml
services:
  birdnet:      # Microservicio principal
    ports: ["8010:8000"]
    
  mongodb:      # Base de datos NoSQL
    ports: ["27018:27017"]
    
  mongo-express: # UI para MongoDB
    ports: ["8081:8081"]
```

### Variables de Entorno

```bash
# MongoDB
MONGODB_URL=mongodb://admin:birdnet123@mongodb:27017/birdnet_db?authSource=admin

# BirdNET
BIRDNET_MODEL_PATH=/app/checkpoints/V2.4
MIN_CONFIDENCE=0.5
```

## 🔄 Integración con Pokedex Microservice

### Flujo de Datos

1. **Usuario graba audio** en Expo app
2. **Expo envía chunks** via WebSocket a BirdNET
3. **BirdNET analiza** y guarda detecciones en MongoDB
4. **BirdNET responde** con detecciones en tiempo real
5. **Usuario termina sesión** en Expo
6. **Pokedex consulta** resumen de sesión via REST API
7. **Pokedex integra** datos con información local de especies

### Código de Ejemplo (Pokedex)

```python
import requests

# Obtener sesiones recientes
response = requests.get("http://birdnet-service:8000/sessions/recent?limit=20")
recent_sessions = response.json()["sessions"]

# Procesar cada sesión
for session in recent_sessions:
    if session["status"] == "completed":
        # Obtener detalles
        summary_response = requests.get(f"http://birdnet-service:8000/sessions/{session['session_id']}/summary")
        summary = summary_response.json()
        
        # Integrar con datos locales
        for species in summary["species_detected"]:
            local_species_data = pokedex_db.get_species(species["species_code"])
            
            # Crear registro de avistamiento
            sighting = {
                "user_id": get_user_from_session(session),
                "species_code": species["species_code"],
                "detection_count": species["detection_count"],
                "max_confidence": species["max_confidence"],
                "session_date": summary["created_at"],
                "location": get_location_from_metadata(summary["metadata"])
            }
            
            pokedex_db.save_sighting(sighting)
        
        # Marcar como procesada
        requests.post(f"http://birdnet-service:8000/sessions/{session['session_id']}/mark-processed")
```

## 🧪 Testing

### WebSocket (Tiempo Real)

```bash
# Test básico
python simple_real_time_client.py

# Test con latencia
python real_time_test_client.py
```

### REST API

```bash
# Script de prueba completo
./test_api.sh
```

### MongoDB

```bash
# Conectar a MongoDB directamente
docker exec -it microservice_mongodb_1 mongo -u admin -p birdnet123 --authenticationDatabase admin

# Ver sesiones
use birdnet_db
db.sessions.find().limit(5)

# Ver detecciones
db.detections.find().limit(10)
```

## 📊 Monitoreo

### Logs en Tiempo Real

```bash
# Todos los servicios
./start.sh --logs

# Solo BirdNET
./start.sh --logs birdnet

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
```

## 🛠️ Desarrollo

### Estructura del Proyecto

```
microservice/
├── application/          # Casos de uso
├── domain/              # Entidades y puertos
├── infrastructure/      # Adaptadores
│   ├── database/        # MongoDB adapter
│   └── adapters/        # BirdNET adapter
├── interfaces/          # Controllers y APIs
│   ├── websocket_controller.py
│   └── sessions_api.py
├── docker-compose.yml   # Orquestación
├── Dockerfile          # Imagen del microservicio
├── requirements.txt    # Dependencias Python
└── start.sh           # Script de inicio
```

### Agregar Nueva Funcionalidad

1. **Dominio**: Definir entidades en `domain/`
2. **Aplicación**: Crear caso de uso en `application/`
3. **Infraestructura**: Implementar adaptador en `infrastructure/`
4. **Interface**: Exponer via WebSocket o REST en `interfaces/`

### Configuración Local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Variables de entorno
export MONGODB_URL="mongodb://admin:birdnet123@localhost:27018/birdnet_db?authSource=admin"
export MIN_CONFIDENCE=0.5

# Ejecutar sin Docker
python main.py
```

## 🚀 Despliegue

### Producción

```bash
# Construir para producción
docker-compose -f docker-compose.prod.yml build

# Iniciar en producción
docker-compose -f docker-compose.prod.yml up -d
```

### Escalabilidad

```bash
# Multiple instancias del microservicio
docker-compose up -d --scale birdnet=3

# Load balancer (nginx)
docker-compose -f docker-compose.lb.yml up -d
```

## 🔧 Troubleshooting

### Problemas Comunes

**MongoDB no conecta**
```bash
# Verificar que el contenedor esté corriendo
docker-compose ps mongodb

# Ver logs de MongoDB
./start.sh --logs mongodb

# Reiniciar solo MongoDB
docker-compose restart mongodb
```

**Audio no se procesa**
```bash
# Verificar plugin BirdNET
curl http://localhost:8010/health

# Ver logs del microservicio
./start.sh --logs birdnet
```

**WebSocket desconecta**
```bash
# Verificar conexión
python simple_real_time_client.py

# Aumentar timeout
# En websocket_controller.py, ajustar timeout values
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

## 📚 Referencias

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

🎉 **¡Tu sistema BirdNET con MongoDB está funcionando!**