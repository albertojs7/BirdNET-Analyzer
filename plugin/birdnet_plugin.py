"""
Plugin BirdNET para análisis de audio de aves
Plugin independiente que puede ser consumido por microservicios
"""
import sys
import os
import tempfile
import json
import asyncio
import logging
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from pathlib import Path

# Agregar el directorio padre al path para importar birdnet_analyzer
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from birdnet_analyzer.analyze.core import analyze
    BIRDNET_AVAILABLE = True
except ImportError as e:
    BIRDNET_AVAILABLE = False
    logging.error(f"BirdNET no disponible: {e}")

@dataclass
class BirdDetection:
    """Estructura de datos para una detección de ave"""
    begin_time: float
    end_time: float
    common_name: str
    species_code: str
    confidence: float
    
    def to_dict(self) -> Dict:
        return {
            "begin_time": self.begin_time,
            "end_time": self.end_time,
            "common_name": self.common_name,
            "species_code": self.species_code,
            "confidence": self.confidence
        }

@dataclass
class AnalysisResult:
    """Resultado completo del análisis"""
    success: bool
    filename: str
    detections: List[BirdDetection]
    total_detections: int
    processing_time: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "filename": self.filename,
            "detections": [d.to_dict() for d in self.detections],
            "total_detections": self.total_detections,
            "processing_time": self.processing_time,
            "error_message": self.error_message,
            "metadata": self.metadata or {}
        }

class BirdNetPlugin:
    """
    Plugin principal para análisis de aves con BirdNET
    Diseñado para ser consumido por microservicios backend
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Inicializar el plugin
        
        Args:
            config: Configuración del plugin
                - temp_dir: Directorio temporal para archivos
                - min_confidence: Confianza mínima para detecciones (default: 0.1)
                - cleanup_temp_files: Limpiar archivos temporales (default: True)
        """
        self.config = config or {}
        self.temp_dir = self.config.get('temp_dir', tempfile.gettempdir())
        self.min_confidence = self.config.get('min_confidence', 0.1)
        self.cleanup_temp_files = self.config.get('cleanup_temp_files', True)
        self.logger = logging.getLogger(__name__)
        
        # Verificar disponibilidad
        if not BIRDNET_AVAILABLE:
            raise RuntimeError("BirdNET no está disponible. Verifique la instalación.")
    
    async def analyze_audio_bytes(self, audio_data: bytes, filename: str = "audio.mp3") -> AnalysisResult:
        """
        Analizar audio desde bytes
        
        Args:
            audio_data: Datos de audio en bytes
            filename: Nombre del archivo (opcional)
            
        Returns:
            AnalysisResult con las detecciones
        """
        import time
        start_time = time.time()
        
        temp_path = None
        output_dir = None
        
        try:
            # Crear archivo temporal
            suffix = Path(filename).suffix or '.mp3'
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir=self.temp_dir) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # Realizar análisis
            result = await self.analyze_audio_file(temp_path, filename)
            
            # Agregar tiempo de procesamiento
            result.processing_time = time.time() - start_time
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error analizando audio desde bytes: {str(e)}")
            return AnalysisResult(
                success=False,
                filename=filename,
                detections=[],
                total_detections=0,
                processing_time=time.time() - start_time,
                error_message=str(e)
            )
        finally:
            # Limpiar archivo temporal
            if self.cleanup_temp_files and temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    self.logger.warning(f"No se pudo eliminar archivo temporal {temp_path}: {e}")
    
    async def analyze_audio_file(self, file_path: str, filename: Optional[str] = None) -> AnalysisResult:
        """
        Analizar archivo de audio existente
        
        Args:
            file_path: Ruta al archivo de audio
            filename: Nombre personalizado (opcional, usa el nombre del archivo si no se proporciona)
            
        Returns:
            AnalysisResult con las detecciones
        """
        import time
        start_time = time.time()
        
        if filename is None:
            filename = os.path.basename(file_path)
        
        output_dir = None
        
        try:
            # Verificar que el archivo existe
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
            
            # Crear directorio temporal para salida
            output_dir = tempfile.mkdtemp(dir=self.temp_dir)
            
            # Ejecutar análisis en thread separado para no bloquear el event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, analyze, file_path, output_dir)
            
            # Procesar resultados
            detections = await self._parse_results(file_path, output_dir)
            
            # Filtrar por confianza mínima
            filtered_detections = [
                d for d in detections 
                if d.confidence >= self.min_confidence
            ]
            
            return AnalysisResult(
                success=True,
                filename=filename,
                detections=filtered_detections,
                total_detections=len(filtered_detections),
                processing_time=time.time() - start_time,
                metadata={
                    "raw_detections": len(detections),
                    "min_confidence": self.min_confidence,
                    "file_path": file_path
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error analizando archivo {file_path}: {str(e)}")
            return AnalysisResult(
                success=False,
                filename=filename,
                detections=[],
                total_detections=0,
                processing_time=time.time() - start_time,
                error_message=str(e)
            )
        finally:
            # Limpiar directorio temporal
            if self.cleanup_temp_files and output_dir and os.path.exists(output_dir):
                try:
                    for file in os.listdir(output_dir):
                        os.unlink(os.path.join(output_dir, file))
                    os.rmdir(output_dir)
                except Exception as e:
                    self.logger.warning(f"No se pudo limpiar directorio temporal {output_dir}: {e}")
    
    async def _parse_results(self, audio_path: str, output_dir: str) -> List[BirdDetection]:
        """Parsear resultados de BirdNET"""
        audio_name = os.path.splitext(os.path.basename(audio_path))[0]
        result_file = os.path.join(output_dir, f"{audio_name}.BirdNET.selection.table.txt")
        
        detections = []
        
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[1:]:  # Saltar header
                    if line.strip():
                        parts = line.strip().split('\t')
                        if len(parts) >= 10:
                            try:
                                detection = BirdDetection(
                                    begin_time=float(parts[3]),
                                    end_time=float(parts[4]),
                                    common_name=parts[7],
                                    species_code=parts[8],
                                    confidence=float(parts[9])
                                )
                                detections.append(detection)
                            except (ValueError, IndexError) as e:
                                self.logger.warning(f"Error parseando línea: {line.strip()}: {str(e)}")
                                continue
        
        return detections
    
    def is_available(self) -> bool:
        """Verificar si el plugin está disponible"""
        return BIRDNET_AVAILABLE
    
    def get_plugin_info(self) -> Dict:
        """Obtener información del plugin"""
        return {
            "name": "BirdNET Audio Analyzer",
            "version": "1.0.0",
            "description": "Plugin para análisis de aves en audio usando BirdNET",
            "available": self.is_available(),
            "config": {
                "min_confidence": self.min_confidence,
                "temp_dir": self.temp_dir,
                "cleanup_temp_files": self.cleanup_temp_files
            }
        }

# Factory function para crear instancias del plugin
def create_birdnet_plugin(config: Optional[Dict] = None) -> BirdNetPlugin:
    """
    Factory function para crear una instancia del plugin BirdNET
    
    Args:
        config: Configuración del plugin
        
    Returns:
        Instancia de BirdNetPlugin
    """
    return BirdNetPlugin(config)

# Función de conveniencia para análisis rápido
async def quick_analyze(audio_data: Union[bytes, str], filename: str = "audio.mp3", 
                       min_confidence: float = 0.1) -> Dict:
    """
    Función de conveniencia para análisis rápido
    
    Args:
        audio_data: Bytes de audio o ruta al archivo
        filename: Nombre del archivo
        min_confidence: Confianza mínima
        
    Returns:
        Diccionario con resultados
    """
    plugin = create_birdnet_plugin({
        "min_confidence": min_confidence
    })
    
    if isinstance(audio_data, bytes):
        result = await plugin.analyze_audio_bytes(audio_data, filename)
    else:
        result = await plugin.analyze_audio_file(audio_data, filename)
    
    return result.to_dict()