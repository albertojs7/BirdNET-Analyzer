"""
Casos de uso para análisis en tiempo real
"""
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from domain.entities import (
    AudioBuffer, StreamingSession, RealTimeDetection, 
    BirdDetection, AudioChunk
)
from domain.ports import AudioAnalyzerPort, NotificationPort

logger = logging.getLogger(__name__)

class StreamingAnalysisUseCase:
    """Caso de uso para análisis de audio en tiempo real"""
    
    def __init__(
        self,
        audio_analyzer: AudioAnalyzerPort,
        notification_service: NotificationPort,
        buffer_duration: float = 5.0,
        overlap_duration: float = 1.0,
        min_confidence: float = 0.1,
        session_timeout: int = 300  # 5 minutos
    ):
        self.audio_analyzer = audio_analyzer
        self.notification_service = notification_service
        self.buffer_duration = buffer_duration
        self.overlap_duration = overlap_duration
        self.min_confidence = min_confidence
        self.session_timeout = session_timeout
        
        # Almacenamiento en memoria de sesiones activas
        self.active_sessions: Dict[str, StreamingSession] = {}
        self.session_buffers: Dict[str, AudioBuffer] = {}
        self.session_species: Dict[str, set] = {}  # Track especies detectadas por sesión
    
    async def start_session(self) -> str:
        """Iniciar nueva sesión de análisis en tiempo real"""
        session_id = str(uuid.uuid4())
        
        session = StreamingSession(
            session_id=session_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        
        buffer = AudioBuffer(
            buffer_duration=self.buffer_duration,
            overlap_duration=self.overlap_duration
        )
        
        self.active_sessions[session_id] = session
        self.session_buffers[session_id] = buffer
        self.session_species[session_id] = set()
        
        logger.info(f"Nueva sesión de streaming iniciada: {session_id}")
        return session_id
    
    async def process_audio_chunk(
        self, 
        session_id: str, 
        audio_data: bytes, 
        timestamp: float, 
        duration: float,
        sequence_number: int
    ) -> List[RealTimeDetection]:
        """
        Procesar chunk de audio en tiempo real
        
        Args:
            session_id: ID de la sesión
            audio_data: Datos de audio del chunk
            timestamp: Timestamp del chunk
            duration: Duración del chunk en segundos
            sequence_number: Número de secuencia del chunk
            
        Returns:
            Lista de detecciones encontradas
        """
        # Verificar que la sesión existe
        if session_id not in self.active_sessions:
            raise ValueError(f"Sesión no encontrada: {session_id}")
        
        session = self.active_sessions[session_id]
        buffer = self.session_buffers[session_id]
        
        # Actualizar actividad de la sesión
        session.update_activity()
        session.total_chunks_received += 1
        
        # ENFOQUE MEJORADO: Analizar chunk directamente en lugar de usar buffer
        # ya que nuestros chunks contienen archivos completos de audio válidos
        
        logger.info(f"Procesando chunk {sequence_number} de sesión {session_id} "
                   f"(tamaño: {len(audio_data)} bytes, timestamp: {timestamp:.1f}s)")
        
        # Analizar chunk directamente como archivo completo
        detections = await self._analyze_complete_chunk(session_id, audio_data, timestamp, duration)
        
        return detections
    
    async def _analyze_complete_chunk(self, session_id: str, audio_data: bytes, 
                                    timestamp: float, duration: float) -> List[RealTimeDetection]:
        """
        Analizar chunk completo directamente
        
        Args:
            session_id: ID de la sesión
            audio_data: Datos completos del archivo de audio
            timestamp: Timestamp del chunk
            duration: Duración del chunk
            
        Returns:
            Lista de detecciones en tiempo real
        """
        try:
            # Crear nombre temporal único
            temp_filename = f"stream_{session_id}_{timestamp:.1f}.mp3"
            
            logger.debug(f"Analizando chunk completo {len(audio_data)} bytes como {temp_filename}")
            
            # Usar el método de análisis tradicional que sabemos que funciona
            raw_detections = await self.audio_analyzer.analyze_audio(audio_data, temp_filename)
            
            logger.info(f"Análisis directo encontró {len(raw_detections)} detecciones brutas")
            
            # Filtrar detecciones y crear detecciones en tiempo real
            real_time_detections = []
            session_species = self.session_species[session_id]
            
            for detection in raw_detections:
                if detection.confidence >= self.min_confidence:
                    # Verificar si es una especie nueva en esta sesión
                    is_new_species = detection.species_code not in session_species
                    if is_new_species:
                        session_species.add(detection.species_code)
                    
                    # Para chunks que representan ventanas temporales, 
                    # ajustar tiempos relativos al timestamp del chunk
                    adjusted_detection = BirdDetection(
                        species_name=detection.species_name,
                        species_code=detection.species_code,
                        confidence=detection.confidence,
                        start_time=timestamp + detection.start_time,
                        end_time=timestamp + detection.end_time
                    )
                    
                    real_time_detection = RealTimeDetection(
                        detection=adjusted_detection,
                        session_id=session_id,
                        chunk_timestamp=timestamp,
                        detection_timestamp=datetime.utcnow(),
                        is_new_species=is_new_species
                    )
                    
                    real_time_detections.append(real_time_detection)
            
            # Actualizar estadísticas de la sesión
            session = self.active_sessions[session_id]
            session.total_detections += len(real_time_detections)
            
            logger.info(f"Chunk análisis sesión {session_id}: "
                       f"{len(real_time_detections)} detecciones de {len(raw_detections)} brutas "
                       f"(timestamp: {timestamp:.1f}s, confianza >= {self.min_confidence})")
            
            return real_time_detections
            
        except Exception as e:
            logger.error(f"Error analizando chunk sesión {session_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def _analyze_buffer(self, session_id: str, buffer: AudioBuffer) -> List[RealTimeDetection]:
        """Analizar buffer y devolver detecciones"""
        try:
            # Obtener datos de audio del buffer
            audio_data = buffer.get_audio_data()
            if not audio_data:
                return []

            start_time, end_time = buffer.get_time_range()
            
            # SOLUCION: Usar el método que funciona (analyze_audio) en lugar de analyze_audio_window
            # que no maneja bien los chunks concatenados
            
            # Crear nombre temporal único para el chunk
            temp_filename = f"stream_{session_id}_{start_time:.1f}.mp3"
            
            logger.debug(f"Analizando buffer {len(audio_data)} bytes como {temp_filename}")
            
            # Usar el método de análisis tradicional que sabemos que funciona
            raw_detections = await self.audio_analyzer.analyze_audio(audio_data, temp_filename)
            
            logger.debug(f"Análisis directo encontró {len(raw_detections)} detecciones brutas")
            
            # Filtrar detecciones por ventana temporal y confianza
            real_time_detections = []
            session_species = self.session_species[session_id]
            
            for detection in raw_detections:
                # Para streaming, aplicar filtro de confianza y verificar ventana
                if detection.confidence >= self.min_confidence:
                    # Verificar si es una especie nueva en esta sesión
                    is_new_species = detection.species_code not in session_species
                    if is_new_species:
                        session_species.add(detection.species_code)
                    
                    # Ajustar tiempos relativos a la ventana de streaming
                    adjusted_detection = BirdDetection(
                        species_name=detection.species_name,
                        species_code=detection.species_code,
                        confidence=detection.confidence,
                        start_time=start_time + detection.start_time,  # Tiempo absoluto en el stream
                        end_time=start_time + detection.end_time
                    )
                    
                    real_time_detection = RealTimeDetection(
                        detection=adjusted_detection,
                        session_id=session_id,
                        chunk_timestamp=start_time,
                        detection_timestamp=datetime.utcnow(),
                        is_new_species=is_new_species
                    )
                    
                    real_time_detections.append(real_time_detection)

            # Actualizar estadísticas de la sesión
            session = self.active_sessions[session_id]
            session.total_detections += len(real_time_detections)

            logger.info(f"Análisis buffer sesión {session_id}: "
                       f"{len(real_time_detections)} detecciones de {len(raw_detections)} brutas "
                       f"(tiempo: {start_time:.1f}-{end_time:.1f}s, confianza >= {self.min_confidence})")

            return real_time_detections
            
        except Exception as e:
            logger.error(f"Error analizando buffer sesión {session_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def end_session(self, session_id: str) -> Optional[Dict]:
        """Finalizar sesión de análisis"""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        session.is_active = False
        
        # Crear resumen de la sesión
        summary = {
            "session_id": session_id,
            "duration": (session.last_activity - session.created_at).total_seconds(),
            "total_chunks": session.total_chunks_received,
            "total_detections": session.total_detections,
            "unique_species": len(self.session_species[session_id]),
            "species_list": list(self.session_species[session_id])
        }
        
        # Limpiar recursos
        del self.active_sessions[session_id]
        del self.session_buffers[session_id]
        del self.session_species[session_id]
        
        logger.info(f"Sesión {session_id} finalizada: {summary}")
        return summary
    
    async def get_session_status(self, session_id: str) -> Optional[Dict]:
        """Obtener estado actual de una sesión"""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        buffer = self.session_buffers[session_id]
        
        return {
            "session_id": session_id,
            "is_active": session.is_active,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "total_chunks": session.total_chunks_received,
            "total_detections": session.total_detections,
            "unique_species": len(self.session_species[session_id]),
            "buffer_duration": buffer.current_duration,
            "buffer_chunks": buffer.chunk_count
        }
    
    async def cleanup_expired_sessions(self):
        """Limpiar sesiones expiradas"""
        current_time = datetime.utcnow()
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            time_since_activity = (current_time - session.last_activity).total_seconds()
            if time_since_activity > self.session_timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            await self.end_session(session_id)
            logger.info(f"Sesión expirada limpiada: {session_id}")
        
        return len(expired_sessions)

class StreamingHealthCheckUseCase:
    """Caso de uso para verificar salud del servicio de streaming"""
    
    def __init__(self, streaming_use_case: StreamingAnalysisUseCase):
        self.streaming_use_case = streaming_use_case
    
    async def execute(self) -> Dict:
        """Verificar salud del servicio de streaming"""
        try:
            active_sessions = len(self.streaming_use_case.active_sessions)
            
            # Limpiar sesiones expiradas
            cleaned_sessions = await self.streaming_use_case.cleanup_expired_sessions()
            
            return {
                "status": "healthy",
                "active_sessions": active_sessions,
                "cleaned_expired_sessions": cleaned_sessions,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error en health check streaming: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }