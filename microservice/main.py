"""
Punto de entrada principal del microservicio
Arquitectura Limpia con FastAPI y WebSockets
"""
import logging
import sys
import os
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Agregar el directorio del microservicio al path
sys.path.insert(0, os.path.dirname(__file__))

# Importaciones locales
from config import Config
from domain.entities import AudioAnalysis, BirdDetection, AnalysisStatus
from domain.ports import AudioAnalyzerPort, AudioAnalysisRepository, NotificationPort
from application.use_cases import AnalyzeAudioUseCase, GetAnalysisStatusUseCase, HealthCheckUseCase
from application.streaming_use_cases import StreamingAnalysisUseCase, StreamingHealthCheckUseCase
from infrastructure.adapters.birdnet_adapter import BirdNetAdapter
from infrastructure.repositories.memory_repository import InMemoryAnalysisRepository
from infrastructure.websocket.notification_service import WebSocketNotificationService
from interfaces.websocket_controller import WebSocketController

# Configurar logging
def setup_logging(log_level: str):
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# Crear aplicación FastAPI
def create_app(config: Config) -> FastAPI:
    """Factory para crear la aplicación FastAPI"""
    
    app = FastAPI(
        title="BirdNET Analysis Microservice",
        description="Microservicio para análisis de aves con arquitectura limpia",
        version="1.0.0"
    )
    
    # Configurar CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app

# Inyección de dependencias
def setup_dependencies(config: Config):
    """Configurar inyección de dependencias"""
    
    # Adaptadores (Infrastructure)
    audio_analyzer = BirdNetAdapter({
        "min_confidence": config.min_confidence,
        "cleanup_temp_files": config.cleanup_temp_files,
        "temp_dir": config.temp_dir
    })
    
    analysis_repository = InMemoryAnalysisRepository()
    notification_service = WebSocketNotificationService()
    
    # Casos de uso (Application)
    analyze_audio_use_case = AnalyzeAudioUseCase(
        audio_analyzer=audio_analyzer,
        analysis_repository=analysis_repository,
        notification_service=notification_service,
        min_confidence=config.min_confidence
    )
    
    get_analysis_status_use_case = GetAnalysisStatusUseCase(
        analysis_repository=analysis_repository
    )
    
    health_check_use_case = HealthCheckUseCase(
        audio_analyzer=audio_analyzer
    )
    
    # Casos de uso de streaming
    streaming_analysis_use_case = StreamingAnalysisUseCase(
        audio_analyzer=audio_analyzer,
        notification_service=notification_service,
        buffer_duration=5.0,  # 5 segundos de buffer
        overlap_duration=1.0,  # 1 segundo de overlap
        min_confidence=config.min_confidence
    )
    
    streaming_health_check_use_case = StreamingHealthCheckUseCase(
        streaming_use_case=streaming_analysis_use_case
    )
    
    # Controlador (Interface)
    websocket_controller = WebSocketController(
        analyze_audio_use_case=analyze_audio_use_case,
        get_analysis_status_use_case=get_analysis_status_use_case,
        health_check_use_case=health_check_use_case,
        streaming_analysis_use_case=streaming_analysis_use_case,
        streaming_health_check_use_case=streaming_health_check_use_case,
        notification_service=notification_service
    )
    
    return {
        "websocket_controller": websocket_controller,
        "health_check_use_case": health_check_use_case
    }

# Configuración global
config = Config.from_env()
setup_logging(config.log_level)
logger = logging.getLogger(__name__)

# Crear aplicación
app = create_app(config)

# Configurar dependencias
dependencies = setup_dependencies(config)
websocket_controller = dependencies["websocket_controller"]
health_check_use_case = dependencies["health_check_use_case"]

# Endpoints

@app.get("/")
async def root():
    """Endpoint raíz con información del servicio"""
    return {
        "service": "BirdNET Analysis Microservice",
        "version": "1.0.0",
        "description": "Microservicio para análisis de aves con arquitectura limpia",
        "endpoints": {
            "websocket": "ws://localhost:8010/ws",
            "health": "/health",
            "docs": "/docs"
        },
        "websocket_commands": [
            "analyze_audio",
            "get_analysis_status",
            "health_check",
            "start_streaming",
            "stream_audio_chunk",
            "end_streaming",
            "get_streaming_status",
            "streaming_health_check"
        ]
    }

@app.get("/health")
async def health():
    """Endpoint de salud del servicio"""
    return await health_check_use_case.execute()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket principal"""
    await websocket_controller.handle_connection(websocket)

# Incluir API de sesiones
from interfaces.sessions_api import router as sessions_router
app.include_router(sessions_router)

# Eventos de aplicación
@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación"""
    logger.info("Iniciando microservicio BirdNET Analysis")
    logger.info(f"Configuración: {config}")
    
    # Conectar a MongoDB
    try:
        from infrastructure.database.mongodb_adapter import mongodb_adapter
        await mongodb_adapter.connect()
        logger.info("✅ MongoDB conectado exitosamente")
    except Exception as e:
        logger.warning(f"⚠️ MongoDB no disponible: {e}")
        logger.info("🔄 Continuando sin persistencia de sesiones...")
    
    # Verificar disponibilidad del plugin
    health = await health_check_use_case.execute()
    if health["status"] != "healthy":
        logger.warning(f"Servicio iniciado con estado: {health['status']}")
    else:
        logger.info("Servicio iniciado correctamente")

@app.on_event("shutdown")
async def shutdown_event():
    """Evento de cierre de la aplicación"""
    logger.info("Cerrando microservicio BirdNET Analysis")
    
    # Desconectar MongoDB
    try:
        from infrastructure.database.mongodb_adapter import mongodb_adapter
        await mongodb_adapter.disconnect()
    except Exception as e:
        logger.warning(f"⚠️ Error desconectando MongoDB: {e}")

# Punto de entrada
if __name__ == "__main__":
    logger.info(f"Iniciando servidor en {config.host}:{config.port}")
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower()
    )