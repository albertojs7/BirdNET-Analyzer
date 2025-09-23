"""
Puertos (interfaces) de dominio - Arquitectura Limpia
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from .entities import AudioAnalysis, BirdDetection

class AudioAnalyzerPort(ABC):
    """Puerto para análisis de audio de aves"""
    
    @abstractmethod
    async def analyze_audio(self, audio_data: bytes, filename: str) -> List[BirdDetection]:
        """Analizar audio y retornar detecciones"""
        pass
    
    @abstractmethod
    async def is_service_available(self) -> bool:
        """Verificar disponibilidad del servicio"""
        pass

class AudioAnalysisRepository(ABC):
    """Puerto para persistencia de análisis"""
    
    @abstractmethod
    async def save_analysis(self, analysis: AudioAnalysis) -> None:
        """Guardar análisis"""
        pass
    
    @abstractmethod
    async def get_analysis_by_id(self, analysis_id: str) -> Optional[AudioAnalysis]:
        """Obtener análisis por ID"""
        pass

class NotificationPort(ABC):
    """Puerto para notificaciones en tiempo real"""
    
    @abstractmethod
    async def notify_analysis_started(self, analysis_id: str) -> None:
        """Notificar inicio de análisis"""
        pass
    
    @abstractmethod
    async def notify_analysis_progress(self, analysis_id: str, message: str) -> None:
        """Notificar progreso"""
        pass
    
    @abstractmethod
    async def notify_analysis_completed(self, analysis: AudioAnalysis) -> None:
        """Notificar análisis completado"""
        pass
    
    @abstractmethod
    async def notify_analysis_failed(self, analysis_id: str, error: str) -> None:
        """Notificar fallo en análisis"""
        pass