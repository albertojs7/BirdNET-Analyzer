"""
Adaptador BirdNET - Capa de infraestructura
"""
import sys
import os
from typing import List
import logging

# Agregar path al plugin
plugin_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'plugin')
sys.path.insert(0, os.path.abspath(plugin_path))

try:
    from birdnet_plugin import create_birdnet_plugin
    PLUGIN_AVAILABLE = True
except ImportError as e:
    PLUGIN_AVAILABLE = False
    logging.error(f"Plugin BirdNET no disponible: {e}")

from domain.entities import BirdDetection
from domain.ports import AudioAnalyzerPort

logger = logging.getLogger(__name__)

class BirdNetAdapter(AudioAnalyzerPort):
    """Adaptador que implementa AudioAnalyzerPort usando el plugin BirdNET"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.plugin = None
        
        if PLUGIN_AVAILABLE:
            try:
                self.plugin = create_birdnet_plugin({
                    "min_confidence": self.config.get("min_confidence", 0.05),
                    "cleanup_temp_files": self.config.get("cleanup_temp_files", True),
                    "temp_dir": self.config.get("temp_dir", "/tmp")
                })
                logger.info("Plugin BirdNET inicializado correctamente")
            except Exception as e:
                logger.error(f"Error inicializando plugin BirdNET: {e}")
                self.plugin = None
        else:
            logger.error("Plugin BirdNET no disponible")
    
    async def analyze_audio(self, audio_data: bytes, filename: str) -> List[BirdDetection]:
        """Analizar audio usando BirdNET"""
        if not self.plugin:
            raise Exception("Plugin BirdNET no disponible")
        
        try:
            # Usar el plugin para análisis
            result = await self.plugin.analyze_audio_bytes(audio_data, filename)
            
            if not result.success:
                raise Exception(f"Error en análisis: {result.error_message}")
            
            # Convertir resultados del plugin a entidades de dominio
            detections = []
            for detection in result.detections:
                bird_detection = BirdDetection(
                    species_name=detection.common_name,
                    species_code=detection.species_code,
                    confidence=detection.confidence,
                    start_time=detection.begin_time,
                    end_time=detection.end_time
                )
                detections.append(bird_detection)
            
            logger.info(f"Análisis completado: {len(detections)} detecciones encontradas")
            return detections
            
        except Exception as e:
            logger.error(f"Error en análisis BirdNET: {str(e)}")
            raise
    
    async def is_service_available(self) -> bool:
        """Verificar si el servicio está disponible"""
        if not PLUGIN_AVAILABLE or not self.plugin:
            return False
        
        try:
            return self.plugin.is_available()
        except Exception as e:
            logger.error(f"Error verificando disponibilidad: {e}")
            return False