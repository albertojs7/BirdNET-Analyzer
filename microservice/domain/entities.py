"""
Entidades de dominio para el análisis de aves
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum
from collections import deque
import io

class AnalysisStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class BirdDetection:
    """Entidad de dominio para una detección de ave"""
    species_name: str
    species_code: str
    confidence: float
    start_time: float
    end_time: float
    
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    def is_high_confidence(self, threshold: float = 0.5) -> bool:
        return self.confidence >= threshold

@dataclass
class AudioAnalysis:
    """Entidad agregada para el análisis completo"""
    analysis_id: str
    filename: str
    status: AnalysisStatus
    detections: List[BirdDetection]
    processing_time: Optional[float] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Optional[Dict] = None
    
    @property
    def total_detections(self) -> int:
        return len(self.detections)
    
    @property
    def unique_species_count(self) -> int:
        return len(set(d.species_code for d in self.detections))
    
    def get_high_confidence_detections(self, threshold: float = 0.5) -> List[BirdDetection]:
        return [d for d in self.detections if d.is_high_confidence(threshold)]
    
    def to_dict(self) -> Dict:
        return {
            "analysis_id": self.analysis_id,
            "filename": self.filename,
            "status": self.status.value,
            "total_detections": self.total_detections,
            "unique_species": self.unique_species_count,
            "detections": [
                {
                    "species_name": d.species_name,
                    "species_code": d.species_code,
                    "confidence": d.confidence,
                    "start_time": d.start_time,
                    "end_time": d.end_time,
                    "duration": d.duration()
                }
                for d in self.detections
            ],
            "processing_time": self.processing_time,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata or {}
        }

@dataclass
class AudioChunk:
    """Chunk de audio para análisis en tiempo real"""
    data: bytes
    timestamp: float
    duration: float
    sequence_number: int

@dataclass
class StreamingSession:
    """Sesión de análisis en tiempo real"""
    session_id: str
    created_at: datetime
    last_activity: datetime
    total_chunks_received: int = 0
    total_detections: int = 0
    is_active: bool = True
    
    def update_activity(self):
        """Actualizar timestamp de última actividad"""
        self.last_activity = datetime.utcnow()

@dataclass
class AudioBuffer:
    """Buffer deslizante para análisis en tiempo real"""
    buffer_duration: float = 5.0  # segundos
    overlap_duration: float = 1.0  # segundos
    chunks: deque = field(default_factory=deque)
    _total_duration: float = 0.0
    
    def add_chunk(self, audio_data: bytes, timestamp: float, duration: float, sequence: int):
        """Agregar chunk al buffer"""
        chunk = AudioChunk(audio_data, timestamp, duration, sequence)
        self.chunks.append(chunk)
        self._total_duration += duration
        
        # Limpiar chunks antiguos si excede el buffer
        while self._total_duration > self.buffer_duration:
            if self.chunks:
                old_chunk = self.chunks.popleft()
                self._total_duration -= old_chunk.duration
    
    def get_audio_data(self) -> bytes:
        """Obtener datos de audio concatenados del buffer"""
        if not self.chunks:
            return b''
        
        # Concatenar todos los chunks
        audio_data = b''
        for chunk in self.chunks:
            audio_data += chunk.data
        return audio_data
    
    def get_time_range(self) -> tuple[float, float]:
        """Obtener rango temporal del buffer"""
        if not self.chunks:
            return 0.0, 0.0
        
        start_time = self.chunks[0].timestamp
        end_time = self.chunks[-1].timestamp + self.chunks[-1].duration
        return start_time, end_time
    
    def is_ready_for_analysis(self) -> bool:
        """Verificar si el buffer tiene suficientes datos para análisis"""
        return self._total_duration >= self.buffer_duration
    
    def slide_window(self):
        """Deslizar ventana eliminando chunks antiguos"""
        overlap_time = self.overlap_duration
        removed_duration = 0.0
        
        while self.chunks and removed_duration < (self._total_duration - overlap_time):
            chunk = self.chunks.popleft()
            removed_duration += chunk.duration
            self._total_duration -= chunk.duration
    
    @property
    def current_duration(self) -> float:
        """Duración actual del buffer"""
        return self._total_duration
    
    @property
    def chunk_count(self) -> int:
        """Número de chunks en el buffer"""
        return len(self.chunks)

@dataclass
class RealTimeDetection:
    """Detección en tiempo real con metadatos adicionales"""
    detection: BirdDetection
    session_id: str
    chunk_timestamp: float
    detection_timestamp: datetime
    is_new_species: bool = False
    
    def to_dict(self) -> Dict:
        """Convertir a diccionario para JSON"""
        return {
            "session_id": self.session_id,
            "chunk_timestamp": self.chunk_timestamp,
            "detection_timestamp": self.detection_timestamp.isoformat(),
            "is_new_species": self.is_new_species,
            "species_name": self.detection.species_name,
            "species_code": self.detection.species_code,
            "confidence": self.detection.confidence,
            "start_time": self.detection.start_time,
            "end_time": self.detection.end_time,
            "duration": self.detection.duration()
        }