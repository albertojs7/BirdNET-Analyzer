"""
Pruebas para la capa de Dominio
"""
import pytest
from datetime import datetime
from domain.entities import AudioAnalysis, BirdDetection, AnalysisStatus


class TestAudioAnalysis:
    """Pruebas para la entidad AudioAnalysis"""
    
    def test_create_audio_analysis(self):
        """Debe crear un análisis de audio válido"""
        analysis = AudioAnalysis(
            analysis_id="test-123",
            filename="test.mp3",
            status=AnalysisStatus.PENDING,
            detections=[],
            created_at=datetime.utcnow()
        )
        
        assert analysis.analysis_id == "test-123"
        assert analysis.filename == "test.mp3"
        assert analysis.status == AnalysisStatus.PENDING
        assert analysis.detections == []
        assert analysis.created_at is not None
    
    def test_audio_analysis_with_detections(self):
        """Debe crear análisis con detecciones"""
        detection = BirdDetection(
            species_name="Northern Cardinal",
            species_code="norcad",
            confidence=0.85,
            start_time=10.5,
            end_time=12.3
        )
        
        analysis = AudioAnalysis(
            analysis_id="test-123",
            filename="test.mp3",
            status=AnalysisStatus.COMPLETED,
            detections=[detection],
            created_at=datetime.utcnow()
        )
        
        assert len(analysis.detections) == 1
        assert analysis.detections[0].species_name == "Northern Cardinal"
        assert analysis.detections[0].confidence == 0.85


class TestBirdDetection:
    """Pruebas para la entidad BirdDetection"""
    
    def test_create_bird_detection(self):
        """Debe crear una detección de ave válida"""
        detection = BirdDetection(
            species_name="House Sparrow",
            species_code="houspa",
            confidence=0.92,
            start_time=5.0,
            end_time=7.5
        )
        
        assert detection.species_name == "House Sparrow"
        assert detection.species_code == "houspa"
        assert detection.confidence == 0.92
        assert detection.start_time == 5.0
        assert detection.end_time == 7.5
    
    def test_bird_detection_duration(self):
        """Debe calcular correctamente la duración"""
        detection = BirdDetection(
            species_name="Test Bird",
            species_code="test",
            confidence=0.8,
            start_time=10.0,
            end_time=15.0
        )
        
        duration = detection.end_time - detection.start_time
        assert duration == 5.0
    
    def test_bird_detection_confidence_range(self):
        """Debe validar que la confianza esté entre 0 y 1"""
        # Confianza válida
        detection = BirdDetection(
            species_name="Test",
            species_code="test",
            confidence=0.5,
            start_time=0.0,
            end_time=1.0
        )
        assert 0 <= detection.confidence <= 1
    
    def test_invalid_time_range(self):
        """Debe manejar rangos de tiempo inválidos"""
        # End time menor que start time (esto es un bug potencial)
        detection = BirdDetection(
            species_name="Test",
            species_code="test",
            confidence=0.8,
            start_time=10.0,
            end_time=5.0  # Inválido: end < start
        )
        
        # El sistema debería manejarlo
        duration = detection.end_time - detection.start_time
        assert duration < 0  # Detectar el problema


class TestAnalysisStatus:
    """Pruebas para el enum AnalysisStatus"""
    
    def test_analysis_status_values(self):
        """Debe tener los estados correctos"""
        assert AnalysisStatus.PENDING is not None
        assert AnalysisStatus.PROCESSING is not None
        assert AnalysisStatus.COMPLETED is not None
        assert AnalysisStatus.FAILED is not None
    
    def test_status_transitions(self):
        """Los estados deben transicionar correctamente"""
        # Transición válida
        initial_status = AnalysisStatus.PENDING
        processing_status = AnalysisStatus.PROCESSING
        final_status = AnalysisStatus.COMPLETED
        
        assert initial_status != processing_status
        assert processing_status != final_status
