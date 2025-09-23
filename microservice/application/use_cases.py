"""
Casos de uso - Capa de aplicación
"""
import uuid
from datetime import datetime
from typing import Dict, Optional
import logging

from domain.entities import AudioAnalysis, AnalysisStatus, BirdDetection
from domain.ports import AudioAnalyzerPort, AudioAnalysisRepository, NotificationPort

logger = logging.getLogger(__name__)

class AnalyzeAudioUseCase:
    """Caso de uso para análisis de audio"""
    
    def __init__(
        self,
        audio_analyzer: AudioAnalyzerPort,
        analysis_repository: AudioAnalysisRepository,
        notification_service: NotificationPort,
        min_confidence: float = 0.1
    ):
        self.audio_analyzer = audio_analyzer
        self.analysis_repository = analysis_repository
        self.notification_service = notification_service
        self.min_confidence = min_confidence
    
    async def execute(self, audio_data: bytes, filename: str) -> AudioAnalysis:
        """
        Ejecutar análisis de audio
        
        Args:
            audio_data: Datos de audio en bytes
            filename: Nombre del archivo
            
        Returns:
            AudioAnalysis con el resultado
        """
        analysis_id = str(uuid.uuid4())
        
        # Crear análisis inicial
        analysis = AudioAnalysis(
            analysis_id=analysis_id,
            filename=filename,
            status=AnalysisStatus.PENDING,
            detections=[],
            created_at=datetime.utcnow()
        )
        
        try:
            # Guardar estado inicial
            await self.analysis_repository.save_analysis(analysis)
            
            # Notificar inicio
            await self.notification_service.notify_analysis_started(analysis_id)
            
            # Verificar disponibilidad del servicio
            if not await self.audio_analyzer.is_service_available():
                raise Exception("Servicio de análisis no disponible")
            
            # Cambiar estado a procesando
            analysis.status = AnalysisStatus.PROCESSING
            await self.analysis_repository.save_analysis(analysis)
            await self.notification_service.notify_analysis_progress(
                analysis_id, "Iniciando análisis de audio..."
            )
            
            # Realizar análisis
            import time
            start_time = time.time()
            
            detections = await self.audio_analyzer.analyze_audio(audio_data, filename)
            
            # Filtrar por confianza mínima
            filtered_detections = [
                d for d in detections 
                if d.confidence >= self.min_confidence
            ]
            
            processing_time = time.time() - start_time
            
            # Actualizar análisis con resultados
            analysis.status = AnalysisStatus.COMPLETED
            analysis.detections = filtered_detections
            analysis.processing_time = processing_time
            analysis.metadata = {
                "raw_detections": len(detections),
                "filtered_detections": len(filtered_detections),
                "min_confidence": self.min_confidence,
                "audio_size_bytes": len(audio_data)
            }
            
            # Guardar resultado final
            await self.analysis_repository.save_analysis(analysis)
            
            # Notificar completado
            await self.notification_service.notify_analysis_completed(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error en análisis {analysis_id}: {str(e)}")
            
            # Actualizar análisis con error
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(e)
            
            # Guardar estado de error
            await self.analysis_repository.save_analysis(analysis)
            
            # Notificar fallo
            await self.notification_service.notify_analysis_failed(analysis_id, str(e))
            
            return analysis

class GetAnalysisStatusUseCase:
    """Caso de uso para obtener estado de análisis"""
    
    def __init__(self, analysis_repository: AudioAnalysisRepository):
        self.analysis_repository = analysis_repository
    
    async def execute(self, analysis_id: str) -> Optional[AudioAnalysis]:
        """Obtener estado de análisis por ID"""
        return await self.analysis_repository.get_analysis_by_id(analysis_id)

class HealthCheckUseCase:
    """Caso de uso para verificar salud del servicio"""
    
    def __init__(self, audio_analyzer: AudioAnalyzerPort):
        self.audio_analyzer = audio_analyzer
    
    async def execute(self) -> Dict:
        """Verificar salud del servicio"""
        try:
            is_available = await self.audio_analyzer.is_service_available()
            return {
                "status": "healthy" if is_available else "degraded",
                "analyzer_available": is_available,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error en health check: {str(e)}")
            return {
                "status": "unhealthy",
                "analyzer_available": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }