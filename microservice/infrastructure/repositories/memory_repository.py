"""
Repositorio en memoria - Capa de infraestructura
"""
from typing import Dict, Optional
from domain.entities import AudioAnalysis
from domain.ports import AudioAnalysisRepository

class InMemoryAnalysisRepository(AudioAnalysisRepository):
    """Implementación en memoria del repositorio de análisis"""
    
    def __init__(self):
        self._analyses: Dict[str, AudioAnalysis] = {}
    
    async def save_analysis(self, analysis: AudioAnalysis) -> None:
        """Guardar análisis en memoria"""
        self._analyses[analysis.analysis_id] = analysis
    
    async def get_analysis_by_id(self, analysis_id: str) -> Optional[AudioAnalysis]:
        """Obtener análisis por ID"""
        return self._analyses.get(analysis_id)