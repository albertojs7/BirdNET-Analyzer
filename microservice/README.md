# Microservicio BirdNET con Arquitectura Limpia

Microservicio FastAPI con WebSockets que implementa arquitectura limpia para análisis de aves.

## Estructura del Proyecto

```
microservice/
├── domain/                     # Capa de Dominio
│   ├── entities.py            # Entidades de negocio
│   └── ports.py               # Interfaces/Puertos
├── application/               # Capa de Aplicación  
│   └── use_cases.py          # Casos de uso
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
├── client_test.py           # Cliente de prueba
└── README.md                # Este archivo
```

## Arquitectura Limpia

### Capas de la Arquitectura

1. **Dominio (Entidades + Puertos)**
   - `BirdDetection`: Entidad para detecciones
   - `AudioAnalysis`: Agregado para análisis completo
   - `AudioAnalyzerPort`: Interface para análisis
   - `AudioAnalysisRepository`: Interface para persistencia
   - `NotificationPort`: Interface para notificaciones

2. **Aplicación (Casos de Uso)**
   - `AnalyzeAudioUseCase`: Análisis de audio
   - `GetAnalysisStatusUseCase`: Consulta de estado
   - `HealthCheckUseCase`: Verificación de salud

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

```bash
python client_test.py
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

#### 1. Analizar Audio

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

#### 2. Consultar Estado

```json
{
    "type": "get_analysis_status",
    "analysis_id": "uuid"
}
```

#### 3. Health Check

```json
{
    "type": "health_check"
}
```

## Integración en Expo/React Native

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

    const connectWebSocket = () => {
        const websocket = new WebSocket(getWebSocketUrl());
        
        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'analysis_completed') {
                setAnalysis(data.result);
            }
        };
        
        setWs(websocket);
    };

    const analyzeAudio = async () => {
        try {
            // Seleccionar archivo
            const result = await DocumentPicker.getDocumentAsync({
                type: 'audio/*',
            });

            if (result.type === 'success') {
                // Leer como Base64
                const base64 = await FileSystem.readAsStringAsync(result.uri, {
                    encoding: 'base64',
                });

                // Enviar por WebSocket
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

    return (
        <View>
            <Button title="Conectar" onPress={connectWebSocket} />
            <Button title="Analizar Audio" onPress={analyzeAudio} />
            {analysis && (
                <Text>Detecciones: {analysis.total_detections}</Text>
            )}
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

## Posibles Extensiones

1. **Base de Datos**: Cambiar `InMemoryRepository` por PostgreSQL/MongoDB
2. **Autenticación**: Agregar JWT/OAuth para WebSockets
3. **Rate Limiting**: Limitar análisis por usuario
4. **Métricas**: Agregar Prometheus/Grafana
5. **Caching**: Redis para resultados frecuentes
6. **Queue**: Celery/RQ para análisis asíncronos

## Testing

```bash
# Tests unitarios (a implementar)
pytest tests/

# Test de integración
python client_test.py
```