"""
Pruebas para la capa de Aplicación
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from domain.entities import AudioAnalysis, BirdDetection, AnalysisStatus
from application.use_cases import (
    AnalyzeAudioUseCase,
    GetAnalysisStatusUseCase,
    HealthCheckUseCase
)


class TestAnalyzeAudioUseCase:
    """Pruebas para el caso de uso AnalyzeAudioUseCase"""
    
    @pytest.fixture
    def mock_analyzer(self):
        """Mock del analizador de audio"""
        analyzer = AsyncMock()
        analyzer.is_service_available = AsyncMock(return_value=True)
        analyzer.analyze_audio = AsyncMock(return_value=[
            BirdDetection(
                species_name="Northern Cardinal",
                species_code="norcad",
                confidence=0.85,
                start_time=10.5,
                end_time=12.3
            )
        ])
        return analyzer
    
    @pytest.fixture
    def mock_repository(self):
        """Mock del repositorio"""
        repository = AsyncMock()
        repository.save_analysis = AsyncMock()
        repository.get_analysis = AsyncMock()
        return repository
    
    @pytest.fixture
    def mock_notification_service(self):
        """Mock del servicio de notificaciones"""
        service = AsyncMock()
        service.notify_analysis_started = AsyncMock()
        service.notify_analysis_progress = AsyncMock()
        service.notify_analysis_completed = AsyncMock()
        service.notify_analysis_failed = AsyncMock()
        return service
    
    @pytest.mark.asyncio
    async def test_execute_analysis_successfully(self, mock_analyzer, mock_repository, mock_notification_service):
        """Debe ejecutar un análisis exitosamente"""
        use_case = AnalyzeAudioUseCase(
            audio_analyzer=mock_analyzer,
            analysis_repository=mock_repository,
            notification_service=mock_notification_service,
            min_confidence=0.1
        )
        
        audio_data = b"fake audio data"
        filename = "test.mp3"
        
        result = await use_case.execute(audio_data, filename)
        
        # Verificar que el análisis fue creado
        assert result.analysis_id is not None
        assert result.filename == filename
        assert result.status == AnalysisStatus.COMPLETED
        
        # Verificar que se guardó
        assert mock_repository.save_analysis.called
        
        # Verificar notificaciones
        assert mock_notification_service.notify_analysis_completed.called
    
    @pytest.mark.asyncio
    async def test_analyze_with_min_confidence_filter(self, mock_analyzer, mock_repository, mock_notification_service):
        """Debe filtrar detecciones por confianza mínima"""
        # Crear detecciones con diferentes niveles de confianza
        detections = [
            BirdDetection("Bird1", "bird1", 0.9, 0, 1),
            BirdDetection("Bird2", "bird2", 0.3, 1, 2),  # Bajo
            BirdDetection("Bird3", "bird3", 0.8, 2, 3),
        ]
        
        mock_analyzer.analyze_audio = AsyncMock(return_value=detections)
        
        use_case = AnalyzeAudioUseCase(
            audio_analyzer=mock_analyzer,
            analysis_repository=mock_repository,
            notification_service=mock_notification_service,
            min_confidence=0.5  # Solo mostrar >= 0.5
        )
        
        result = await use_case.execute(b"audio", "test.mp3")
        
        # Solo 2 detecciones deberían pasar el filtro
        assert len(result.detections) == 2
        assert all(d.confidence >= 0.5 for d in result.detections)


class TestGetAnalysisStatusUseCase:
    """Pruebas para obtener estado de análisis"""
    
    @pytest.mark.asyncio
    async def test_get_analysis_status_found(self):
        """Debe obtener el estado cuando existe"""
        mock_repository = AsyncMock()
        
        expected_analysis = AudioAnalysis(
            analysis_id="test-123",
            filename="test.mp3",
            status=AnalysisStatus.COMPLETED,
            detections=[],
            created_at=datetime.utcnow()
        )
        
        mock_repository.get_analysis_by_id = AsyncMock(return_value=expected_analysis)
        
        use_case = GetAnalysisStatusUseCase(analysis_repository=mock_repository)
        result = await use_case.execute("test-123")
        
        assert result.analysis_id == "test-123"
        assert result.status == AnalysisStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_get_analysis_status_not_found(self):
        """Debe manejar análisis no encontrado"""
        mock_repository = AsyncMock()
        mock_repository.get_analysis_by_id = AsyncMock(return_value=None)
        
        use_case = GetAnalysisStatusUseCase(analysis_repository=mock_repository)
        result = await use_case.execute("nonexistent")
        
        assert result is None


class TestHealthCheckUseCase:
    """Pruebas para health check"""
    
    @pytest.mark.asyncio
    async def test_health_check_service_available(self):
        """Debe reportar healthy cuando el servicio está disponible"""
        mock_analyzer = AsyncMock()
        mock_analyzer.is_service_available = AsyncMock(return_value=True)
        
        use_case = HealthCheckUseCase(audio_analyzer=mock_analyzer)
        result = await use_case.execute()
        
        assert result["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_check_service_unavailable(self):
        """Debe reportar unhealthy cuando el servicio no está disponible"""
        mock_analyzer = AsyncMock()
        mock_analyzer.is_service_available = AsyncMock(return_value=False)
        
        use_case = HealthCheckUseCase(audio_analyzer=mock_analyzer)
        result = await use_case.execute()
        
        assert result["status"] != "healthy"
