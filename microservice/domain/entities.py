"""
Entidades de dominio para el análisis de aves
"""
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

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