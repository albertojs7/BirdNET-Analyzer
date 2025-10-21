"""
Pruebas para la capa de Infraestructura
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from infrastructure.repositories.memory_repository import InMemoryAnalysisRepository
from domain.entities import AudioAnalysis, BirdDetection, AnalysisStatus
from datetime import datetime


class TestInMemoryAnalysisRepository:
    """Pruebas para el repositorio en memoria"""
    
    @pytest.fixture
    def repository(self):
        """Crear repositorio limpio"""
        return InMemoryAnalysisRepository()
    
    @pytest.mark.asyncio
    async def test_save_and_get_analysis(self, repository):
        """Debe guardar y recuperar análisis"""
        analysis = AudioAnalysis(
            analysis_id="test-123",
            filename="test.mp3",
            status=AnalysisStatus.COMPLETED,
            detections=[],
            created_at=datetime.utcnow()
        )
        
        await repository.save_analysis(analysis)
        retrieved = await repository.get_analysis_by_id("test-123")
        
        assert retrieved is not None
        assert retrieved.analysis_id == "test-123"
        assert retrieved.filename == "test.mp3"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_analysis(self, repository):
        """Debe retornar None para análisis inexistentes"""
        result = await repository.get_analysis_by_id("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_analysis(self, repository):
        """Debe actualizar análisis existente"""
        analysis = AudioAnalysis(
            analysis_id="test-123",
            filename="test.mp3",
            status=AnalysisStatus.PENDING,
            detections=[],
            created_at=datetime.utcnow()
        )
        
        await repository.save_analysis(analysis)
        
        # Actualizar estado
        analysis.status = AnalysisStatus.COMPLETED
        analysis.detections = [
            BirdDetection("Bird", "bird", 0.9, 0, 1)
        ]
        
        await repository.save_analysis(analysis)
        
        retrieved = await repository.get_analysis_by_id("test-123")
        assert retrieved.status == AnalysisStatus.COMPLETED
        assert len(retrieved.detections) == 1
    
    @pytest.mark.asyncio
    async def test_get_all_analyses(self, repository):
        """Debe obtener todos los análisis (usando el diccionario interno)"""
        analysis1 = AudioAnalysis(
            analysis_id="test-1",
            filename="test1.mp3",
            status=AnalysisStatus.COMPLETED,
            detections=[],
            created_at=datetime.utcnow()
        )
        
        analysis2 = AudioAnalysis(
            analysis_id="test-2",
            filename="test2.mp3",
            status=AnalysisStatus.COMPLETED,
            detections=[],
            created_at=datetime.utcnow()
        )
        
        await repository.save_analysis(analysis1)
        await repository.save_analysis(analysis2)
        
        # Acceder directamente al diccionario interno
        all_analyses = list(repository._analyses.values())
        assert len(all_analyses) >= 2


class TestWebSocketNotificationService:
    """Pruebas para el servicio de notificaciones WebSocket"""
    
    def test_register_connection(self):
        """Debe registrar una conexión"""
        from infrastructure.websocket.notification_service import WebSocketNotificationService
        
        service = WebSocketNotificationService()
        mock_websocket = AsyncMock()
        
        # Registrar con analysis_id
        service.register_connection(mock_websocket, analysis_id="test-123")
        
        # Verificar que se registró (acceder al atributo privado)
        assert "test-123" in service._connections
        assert service._connections["test-123"] == mock_websocket
    
    def test_unregister_connection(self):
        """Debe deregistrar una conexión"""
        from infrastructure.websocket.notification_service import WebSocketNotificationService
        
        service = WebSocketNotificationService()
        mock_websocket = AsyncMock()
        
        service.register_connection(mock_websocket, analysis_id="test-123")
        assert "test-123" in service._connections
        
        service.unregister_connection(mock_websocket, analysis_id="test-123")
        
        assert "test-123" not in service._connections
    
    @pytest.mark.asyncio
    async def test_notify_analysis_completed(self):
        """Debe notificar cuando se completa un análisis"""
        from infrastructure.websocket.notification_service import WebSocketNotificationService
        
        service = WebSocketNotificationService()
        mock_websocket = AsyncMock()
        
        service.register_connection(mock_websocket)
        
        analysis = AudioAnalysis(
            analysis_id="test-123",
            filename="test.mp3",
            status=AnalysisStatus.COMPLETED,
            detections=[],
            created_at=datetime.utcnow()
        )
        
        await service.notify_analysis_completed(analysis)
        
        # Verificar que se envió notificación
        assert mock_websocket.send_text.called
