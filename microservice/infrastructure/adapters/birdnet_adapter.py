"""
Adaptador BirdNET - Capa de infraestructura
"""
import sys
import os
from typing import List
import logging


try:
    from plugin.birdnet_plugin import create_birdnet_plugin
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
            logger.info(f"Iniciando análisis de {filename} ({len(audio_data)} bytes)")
            
            # Usar el plugin para análisis
            result = await self.plugin.analyze_audio_bytes(audio_data, filename)
            
            if not result.success:
                logger.error(f"Error en análisis: {result.error_message}")
                raise Exception(f"Error en análisis: {result.error_message}")
            
            logger.info(f"Plugin devolvió {len(result.detections)} detecciones brutas")
            
            # Convertir resultados del plugin a entidades de dominio
            detections = []
            for i, detection in enumerate(result.detections):
                # Filtrar detecciones no deseadas
                species_lower = detection.common_name.lower()
                code_lower = detection.species_code.lower()
                
                if ("nocall" in code_lower or "nocall" in species_lower or
                    "human" in species_lower or "human" in code_lower or
                    "whistle" in species_lower or "voice" in species_lower):
                    logger.debug(f"Filtrando: {detection.common_name}")
                    continue
                
                bird_detection = BirdDetection(
                    species_name=detection.common_name,
                    species_code=detection.species_code,
                    confidence=detection.confidence,
                    start_time=detection.begin_time,
                    end_time=detection.end_time
                )
                detections.append(bird_detection)
                
                logger.debug(f"Detección {i+1}: {detection.common_name} ({detection.confidence:.3f})")
            
            logger.info(f"Análisis completado: {len(detections)} detecciones encontradas")
            return detections
            
        except Exception as e:
            logger.error(f"Error en análisis BirdNET: {str(e)}")
            raise
    
    async def analyze_audio_window(self, audio_data: bytes, start_time: float, end_time: float) -> List[BirdDetection]:
        """Analizar ventana específica de audio para streaming"""
        if not self.plugin:
            raise Exception("Plugin BirdNET no disponible")
        
        try:
            # Para ventanas de streaming, usamos el mismo método pero con metadatos de tiempo
            result = await self.plugin.analyze_audio_bytes(audio_data, f"stream_{start_time:.1f}-{end_time:.1f}.wav")
            
            if not result.success:
                raise Exception(f"Error en análisis de ventana: {result.error_message}")
            
            # Convertir resultados y ajustar tiempos relativos a la ventana
            detections = []
            for detection in result.detections:
                # Filtrar detecciones no deseadas
                species_lower = detection.common_name.lower()
                code_lower = detection.species_code.lower()
                
                if ("nocall" in code_lower or "nocall" in species_lower or
                    "human" in species_lower or "human" in code_lower or
                    "whistle" in species_lower or "voice" in species_lower):
                    continue
                
                # Ajustar tiempos relativos al inicio de la ventana
                bird_detection = BirdDetection(
                    species_name=detection.common_name,
                    species_code=detection.species_code,
                    confidence=detection.confidence,
                    start_time=start_time + detection.begin_time,  # Tiempo absoluto
                    end_time=start_time + detection.end_time      # Tiempo absoluto
                )
                detections.append(bird_detection)
            
            logger.debug(f"Análisis ventana {start_time:.1f}-{end_time:.1f}s: {len(detections)} detecciones")
            return detections
            
        except Exception as e:
            logger.error(f"Error en análisis de ventana BirdNET: {str(e)}")
            # No lanzar excepción para ventanas, devolver lista vacía
            return []
    
    async def is_service_available(self) -> bool:
        """Verificar si el servicio está disponible"""
        if not PLUGIN_AVAILABLE or not self.plugin:
            return False
        
        try:
            return self.plugin.is_available()
        except Exception as e:
            logger.error(f"Error verificando disponibilidad: {e}")
            return False