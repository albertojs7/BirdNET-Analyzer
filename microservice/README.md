# Microservicio BirdNET con Arquitectura Limpia

Microservicio FastAPI con WebSockets que implementa arquitectura limpia para análisis de aves con soporte para **análisis en tiempo real**.

## ✨ Características

- **Análisis tradicional**: Subir archivo completo y obtener resultados
- **Análisis en tiempo real**: Stream de audio con detecciones instantáneas  
- **WebSockets**: Comunicación bidireccional en tiempo real
- **Arquitectura limpia**: Código organizado y mantenible
- **Docker ready**: Configurado para contenedores

## Estructura del Proyecto

```
microservice/
├── domain/                     # Capa de Dominio
│   ├── entities.py            # Entidades de negocio
│   └── ports.py               # Interfaces/Puertos
├── application/               # Capa de Aplicación  
│   ├── use_cases.py          # Casos de uso tradicionales
│   └── streaming_use_cases.py # Casos de uso para streaming
├── infrastructure/           # Capa de Infraestructura
│   ├── adapters/
│   │   └── birdnet_adapter.py # Adaptador BirdNET
│   ├── repositories/
│   │   └── memory_repository.py # Repositorio en memoria
│   └── websocket/
│       └── notification_service.py # Servicio WebSocket
├── interfaces/               # Capa de Interfaces
│   └── websocket_controller.py # Controlador WebSocket
├── config.py                 # Configuración
├── main.py                   # Punto de entrada
├── client_test.py           # Cliente de prueba tradicional
├── streaming_client_test.py # Cliente de prueba streaming
└── README.md                # Este archivo
```

## Arquitectura Limpia

### Capas de la Arquitectura

1. **Dominio (Entidades + Puertos)**
   - `BirdDetection`: Entidad para detecciones
   - `AudioAnalysis`: Agregado para análisis completo
   - `AudioChunk`: Chunk de audio para streaming
   - `StreamingSession`: Sesión de análisis en tiempo real
   - `AudioBuffer`: Buffer deslizante para streaming
   - `RealTimeDetection`: Detección con metadatos de tiempo real
   - `AudioAnalyzerPort`: Interface para análisis
   - `AudioAnalysisRepository`: Interface para persistencia
   - `NotificationPort`: Interface para notificaciones

2. **Aplicación (Casos de Uso)**
   - `AnalyzeAudioUseCase`: Análisis de audio tradicional
   - `GetAnalysisStatusUseCase`: Consulta de estado
   - `HealthCheckUseCase`: Verificación de salud
   - `StreamingAnalysisUseCase`: Análisis en tiempo real
   - `StreamingHealthCheckUseCase`: Health check de streaming

3. **Infraestructura (Adaptadores)**
   - `BirdNetAdapter`: Implementa análisis usando el plugin
   - `InMemoryAnalysisRepository`: Persistencia en memoria
   - `WebSocketNotificationService`: Notificaciones en tiempo real

4. **Interfaces (Controladores)**
   - `WebSocketController`: Maneja conexiones WebSocket

## Instalación

```bash
# Instalar dependencias
pip install fastapi uvicorn websockets

# Opcional para cliente de prueba
pip install websockets
```

## Uso

### 1. Ejecutar el Microservicio

```bash
cd microservice
python main.py
```

El servicio estará disponible en:
- WebSocket: `ws://localhost:8000/ws`
- Health: `http://localhost:8000/health`
- Docs: `http://localhost:8000/docs`

### 2. Probar con Cliente

**Análisis tradicional:**
```bash
python client_test.py
```

**Análisis en tiempo real:**
```bash
python streaming_client_test.py
```

### 3. Variables de Entorno

```bash
# .env
HOST=0.0.0.0
PORT=8000
DEBUG=true
MIN_CONFIDENCE=0.1
MAX_FILE_SIZE=52428800
TEMP_DIR=/tmp
CLEANUP_TEMP_FILES=true
LOG_LEVEL=INFO
```

## Protocolo WebSocket

### Conexión

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
    console.log('Conectado');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Recibido:', data);
};
```

### Comandos Disponibles

#### Análisis Tradicional

##### 1. Analizar Audio

```json
{
    "type": "analyze_audio",
    "audio": "base64_encoded_audio_data",
    "filename": "audio.mp3"
}
```

**Respuestas:**
```json
// Análisis aceptado
{
    "type": "analysis_accepted",
    "analysis_id": "uuid",
    "message": "Análisis iniciado correctamente"
}

// Progreso
{
    "type": "analysis_progress", 
    "analysis_id": "uuid",
    "message": "Iniciando análisis de audio..."
}

// Completado
{
    "type": "analysis_completed",
    "analysis_id": "uuid",
    "result": {
        "analysis_id": "uuid",
        "filename": "audio.mp3",
        "status": "completed",
        "total_detections": 3,
        "detections": [...],
        "processing_time": 2.5
    }
}
```

##### 2. Consultar Estado

```json
{
    "type": "get_analysis_status",
    "analysis_id": "uuid"
}
```

##### 3. Health Check

```json
{
    "type": "health_check"
}
```

#### Análisis en Tiempo Real

##### 1. Iniciar Sesión de Streaming

```json
{
    "type": "start_streaming"
}
```

**Respuesta:**
```json
{
    "type": "streaming_started",
    "session_id": "uuid",
    "message": "Sesión de streaming iniciada"
}
```

##### 2. Enviar Chunk de Audio

```json
{
    "type": "stream_audio_chunk",
    "session_id": "uuid",
    "audio": "base64_encoded_chunk",
    "timestamp": 2.5,
    "duration": 2.0,
    "sequence": 1
}
```

**Respuestas:**
```json
// Confirmación del chunk
{
    "type": "chunk_processed",
    "session_id": "uuid",
    "sequence": 1,
    "detections_count": 2
}

// Detección en tiempo real
{
    "type": "real_time_detection",
    "detection": {
        "session_id": "uuid",
        "chunk_timestamp": 2.5,
        "detection_timestamp": "2025-09-23T10:30:45.123Z",
        "is_new_species": true,
        "species_name": "House Sparrow",
        "species_code": "houspa",
        "confidence": 0.85,
        "start_time": 2.8,
        "end_time": 4.2,
        "duration": 1.4
    }
}
```

##### 3. Finalizar Streaming

```json
{
    "type": "end_streaming",
    "session_id": "uuid"
}
```

**Respuesta:**
```json
{
    "type": "streaming_ended",
    "session_summary": {
        "session_id": "uuid",
        "duration": 45.2,
        "total_chunks": 23,
        "total_detections": 15,
        "unique_species": 5,
        "species_list": ["houspa", "amecro", "norcar"]
    }
}
```

##### 4. Estado de Streaming

```json
{
    "type": "get_streaming_status",
    "session_id": "uuid"
}
```

##### 5. Health Check de Streaming

```json
{
    "type": "streaming_health_check"
}
```

## Integración con Front-end

### Análisis Tradicional vs Tiempo Real

#### Análisis Tradicional
- ✅ **Mejor para**: Archivos completos, análisis detallado
- ✅ **Ventajas**: Precisión máxima, análisis completo
- ❌ **Desventajas**: Latencia alta, no interactivo

#### Análisis en Tiempo Real  
- ✅ **Mejor para**: Grabación en vivo, feedback inmediato
- ✅ **Ventajas**: Latencia baja, experiencia interactiva
- ❌ **Desventajas**: Uso más de recursos, mayor complejidad

### URLs para diferentes entornos:

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

// Para dispositivo físico en red local
const WS_URL = 'ws://192.168.1.100:8000/ws';
```

### Ejemplo de uso en React Native:

```javascript
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';

const BirdAnalyzer = () => {
    const [ws, setWs] = useState(null);
    const [analysis, setAnalysis] = useState(null);
    const [streamingSession, setStreamingSession] = useState(null);
    const [realTimeDetections, setRealTimeDetections] = useState([]);

    const connectWebSocket = () => {
        const websocket = new WebSocket(getWebSocketUrl());
        
        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            switch (data.type) {
                case 'analysis_completed':
                    setAnalysis(data.result);
                    break;
                    
                case 'streaming_started':
                    setStreamingSession(data.session_id);
                    break;
                    
                case 'real_time_detection':
                    setRealTimeDetections(prev => [...prev, data.detection]);
                    break;
                    
                case 'streaming_ended':
                    setStreamingSession(null);
                    console.log('Resumen:', data.session_summary);
                    break;
            }
        };
        
        setWs(websocket);
    };

    // Análisis tradicional
    const analyzeAudio = async () => {
        try {
            const result = await DocumentPicker.getDocumentAsync({
                type: 'audio/*',
            });

            if (result.type === 'success') {
                const base64 = await FileSystem.readAsStringAsync(result.uri, {
                    encoding: 'base64',
                });

                ws.send(JSON.stringify({
                    type: 'analyze_audio',
                    audio: base64,
                    filename: result.name
                }));
            }
        } catch (error) {
            console.error('Error:', error);
        }
    };

    // Streaming en tiempo real
    const startStreaming = () => {
        ws.send(JSON.stringify({
            type: 'start_streaming'
        }));
    };

    const sendAudioChunk = (audioChunk, timestamp, duration, sequence) => {
        if (streamingSession) {
            ws.send(JSON.stringify({
                type: 'stream_audio_chunk',
                session_id: streamingSession,
                audio: audioChunk,
                timestamp: timestamp,
                duration: duration,
                sequence: sequence
            }));
        }
    };

    const endStreaming = () => {
        if (streamingSession) {
            ws.send(JSON.stringify({
                type: 'end_streaming',
                session_id: streamingSession
            }));
        }
    };

    return (
        <View>
            <Button title="Conectar" onPress={connectWebSocket} />
            
            {/* Análisis Tradicional */}
            <Button title="Analizar Audio" onPress={analyzeAudio} />
            {analysis && (
                <Text>Detecciones: {analysis.total_detections}</Text>
            )}
            
            {/* Streaming */}
            <Button title="Iniciar Streaming" onPress={startStreaming} />
            <Button title="Terminar Streaming" onPress={endStreaming} />
            
            {/* Detecciones en tiempo real */}
            <FlatList
                data={realTimeDetections}
                keyExtractor={(item, index) => index.toString()}
                renderItem={({ item }) => (
                    <View>
                        <Text>{item.species_name}</Text>
                        <Text>Confianza: {item.confidence.toFixed(2)}</Text>
                        {item.is_new_species && <Text>🆕 Nueva especie!</Text>}
                    </View>
                )}
            />
        </View>
    );
};
```

## Ventajas de esta Arquitectura

1. **Separación de Responsabilidades**: Cada capa tiene una responsabilidad específica
2. **Testeable**: Fácil de crear tests unitarios para cada capa
3. **Flexible**: Fácil cambiar implementaciones (BD, notificaciones, etc.)
4. **Escalable**: Arquitectura preparada para crecer
5. **Mantenible**: Código organizado y fácil de entender
6. **Tiempo Real**: Soporte nativo para análisis streaming
7. **Docker Ready**: Configurado para contenedores

## Análisis en Tiempo Real - Detalles Técnicos

### Buffer Deslizante
- **Tamaño del buffer**: 5 segundos configurable
- **Overlap**: 1 segundo para evitar pérdida de detecciones
- **Chunks**: Procesamiento de audio por ventanas temporales

### Gestión de Sesiones
- **Timeout automático**: Sesiones se limpian tras 5 minutos de inactividad
- **Múltiples sesiones**: Soporte para varios usuarios simultáneos
- **Estado persistente**: Seguimiento de especies detectadas por sesión

### Notificaciones
- **Detecciones inmediatas**: WebSocket push cuando se detecta ave
- **Marcado de especies nuevas**: Indica si es primera vez en la sesión
- **Metadatos temporales**: Timestamps precisos para cada detección

## Posibles Extensiones

1. **Base de Datos**: Cambiar `InMemoryRepository` por PostgreSQL/MongoDB
2. **Autenticación**: Agregar JWT/OAuth para WebSockets  
3. **Rate Limiting**: Limitar análisis por usuario
4. **Métricas**: Agregar Prometheus/Grafana
5. **Caching**: Redis para resultados frecuentes
6. **Queue**: Celery/RQ para análisis asíncronos
7. **Audio Processing**: Mejores algoritmos de chunking para streaming
8. **ML Optimization**: Optimizar BirdNET para tiempo real
9. **Geographic Context**: Filtrar especies por ubicación
10. **Real-time Visualization**: Dashboard en tiempo real

## Testing

```bash
# Tests unitarios (a implementar)
pytest tests/

# Test análisis tradicional
python client_test.py

# Test análisis en tiempo real
python streaming_client_test.py
```