"""
Pruebas de Integración con MongoDB
Tests funcionales que validan la comunicación real con la base de datos
"""
import pytest
import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock
from typing import AsyncGenerator

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False
    AsyncIOMotorClient = None

try:
    import mongomock_motor
    MONGOMOCK_AVAILABLE = True
except ImportError:
    MONGOMOCK_AVAILABLE = False
    mongomock_motor = None


@pytest.fixture
async def mongodb_adapter():
    """Fixture que proporciona un adaptador MongoDB"""
    if not MOTOR_AVAILABLE:
        pytest.skip("motor no instalado. Instala con: pip install motor pymongo")
    
    from infrastructure.database.mongodb_adapter import MongoDBAdapter
    
    adapter = MongoDBAdapter()
    
    # Usar MongoDB de prueba con credenciales correctas
    mongodb_url = os.getenv(
        "MONGODB_URL",
        "mongodb://admin:birdnet123@localhost:27017/test_birdnet?authSource=admin"
    )
    
    with patch.dict(os.environ, {"MONGODB_URL": mongodb_url}):
        try:
            await adapter.connect()
            yield adapter
            await adapter.disconnect()
        except Exception as e:
            pytest.skip(f"No se pudo conectar a MongoDB: {e}")


class TestMongoDBIntegration:
    """Pruebas de integración con MongoDB"""
    
    @pytest.mark.asyncio
    async def test_mongodb_connection(self, mongodb_adapter):
        """Debe conectar a MongoDB correctamente"""
        assert mongodb_adapter.client is not None
        assert mongodb_adapter.database is not None
        assert mongodb_adapter.sessions_collection is not None
        assert mongodb_adapter.detections_collection is not None
    
    @pytest.mark.asyncio
    async def test_create_session(self, mongodb_adapter):
        """Debe crear una nueva sesión"""
        session_id = "test-session-001"
        
        # Limpiar antes de crear
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        
        # Crear sesión
        session = await mongodb_adapter.create_session(
            session_id=session_id,
            metadata={"user": "test", "device": "microphone"}
        )
        
        assert session["session_id"] == session_id
        assert session["status"] == "active"
        assert session["total_detections"] == 0
        assert session["metadata"]["user"] == "test"
    
    @pytest.mark.asyncio
    async def test_create_duplicate_session_fails(self, mongodb_adapter):
        """Debe rechazar sesión duplicada"""
        session_id = "test-session-dup"
        
        # Limpiar antes
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        
        # Crear primera vez
        await mongodb_adapter.create_session(session_id=session_id)
        
        # Intentar crear duplicada
        with pytest.raises(ValueError, match="ya existe"):
            await mongodb_adapter.create_session(session_id=session_id)
        
        # Limpiar
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
    
    @pytest.mark.asyncio
    async def test_save_detection(self, mongodb_adapter):
        """Debe guardar una detección"""
        session_id = "test-session-det-001"
        
        # Crear sesión primero
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.create_session(session_id=session_id)
        
        # Guardar detección
        detection_data = {
            "species_name": "American Robin",
            "species_code": "amro",
            "confidence": 0.95,
            "start_time": 0.5,
            "end_time": 1.5,
            "chunk_timestamp": 0,
            "processing_time": 0.123,
            "chunk_sequence": 1,
            "is_new_species": True
        }
        
        detection_id = await mongodb_adapter.save_detection(session_id, detection_data)
        
        assert detection_id is not None
        assert len(detection_id) > 0
        
        # Verificar que se guardó
        detection = await mongodb_adapter.detections_collection.find_one({"_id": ObjectId(detection_id)})
        assert detection is not None
        assert detection["species_name"] == "American Robin"
        assert detection["confidence"] == 0.95
        
        # Limpiar
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.detections_collection.delete_many({"session_id": session_id})
    
    @pytest.mark.asyncio
    async def test_save_multiple_detections(self, mongodb_adapter):
        """Debe guardar múltiples detecciones de la misma sesión"""
        session_id = "test-session-multi-001"
        
        # Limpiar y crear sesión
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.create_session(session_id=session_id)
        
        # Guardar múltiples detecciones
        species_list = [
            ("American Robin", "amro", 0.95),
            ("Carolina Wren", "carw", 0.88),
            ("Northern Cardinal", "noca", 0.92),
        ]
        
        detection_ids = []
        for species_name, species_code, confidence in species_list:
            detection_id = await mongodb_adapter.save_detection(
                session_id,
                {
                    "species_name": species_name,
                    "species_code": species_code,
                    "confidence": confidence,
                    "start_time": 0.0,
                    "end_time": 1.0,
                    "chunk_timestamp": 0,
                    "processing_time": 0.1,
                    "chunk_sequence": 1,
                }
            )
            detection_ids.append(detection_id)
        
        # Verificar que se guardaron todas
        assert len(detection_ids) == 3
        
        # Verificar contadores de sesión
        session = await mongodb_adapter.sessions_collection.find_one({"session_id": session_id})
        assert session["total_detections"] >= 3
        assert session["unique_species"] >= 3
        
        # Limpiar
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.detections_collection.delete_many({"session_id": session_id})
    
    @pytest.mark.asyncio
    async def test_get_session_by_id(self, mongodb_adapter):
        """Debe recuperar una sesión por ID"""
        session_id = "test-session-get-001"
        
        # Limpiar y crear
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.create_session(
            session_id=session_id,
            metadata={"region": "northeast"}
        )
        
        # Recuperar
        session = await mongodb_adapter.sessions_collection.find_one({"session_id": session_id})
        
        assert session is not None
        assert session["session_id"] == session_id
        assert session["metadata"]["region"] == "northeast"
        
        # Limpiar
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
    
    @pytest.mark.asyncio
    async def test_get_detections_by_session(self, mongodb_adapter):
        """Debe recuperar todas las detecciones de una sesión"""
        session_id = "test-session-retrieve-001"
        
        # Limpiar y crear sesión
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.create_session(session_id=session_id)
        
        # Guardar 3 detecciones
        for i in range(3):
            await mongodb_adapter.save_detection(
                session_id,
                {
                    "species_name": f"Species-{i}",
                    "species_code": f"sp{i}",
                    "confidence": 0.9 - i * 0.05,
                    "start_time": float(i),
                    "end_time": float(i + 1),
                    "chunk_timestamp": i,
                    "processing_time": 0.1,
                    "chunk_sequence": i,
                }
            )
        
        # Recuperar todas
        detections = await mongodb_adapter.detections_collection.find(
            {"session_id": session_id}
        ).to_list(length=None)
        
        assert len(detections) >= 3
        
        # Limpiar
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.detections_collection.delete_many({"session_id": session_id})
    
    @pytest.mark.asyncio
    async def test_update_session_status(self, mongodb_adapter):
        """Debe actualizar el estado de una sesión"""
        session_id = "test-session-update-001"
        
        # Limpiar y crear
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.create_session(session_id=session_id)
        
        # Actualizar estado
        await mongodb_adapter.sessions_collection.update_one(
            {"session_id": session_id},
            {"$set": {"status": "completed"}}
        )
        
        # Verificar
        session = await mongodb_adapter.sessions_collection.find_one({"session_id": session_id})
        assert session["status"] == "completed"
        
        # Limpiar
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})


class TestMongoDBIndexes:
    """Pruebas para verificar índices de MongoDB"""
    
    @pytest.mark.asyncio
    async def test_sessions_indexes_exist(self, mongodb_adapter):
        """Debe tener índices en colección de sesiones"""
        indexes = await mongodb_adapter.sessions_collection.list_indexes().to_list(None)
        index_names = [idx["name"] for idx in indexes]
        
        # Verificar índices clave
        assert "session_id_1" in index_names or any("session_id" in idx for idx in index_names)
        assert "_id_" in index_names  # Índice por defecto
    
    @pytest.mark.asyncio
    async def test_detections_indexes_exist(self, mongodb_adapter):
        """Debe tener índices en colección de detecciones"""
        indexes = await mongodb_adapter.detections_collection.list_indexes().to_list(None)
        index_names = [idx["name"] for idx in indexes]
        
        # Verificar índices clave
        assert "_id_" in index_names


class TestMongoDBQueryPerformance:
    """Pruebas de rendimiento con MongoDB"""
    
    @pytest.mark.asyncio
    async def test_bulk_insert_performance(self, mongodb_adapter):
        """Debe insertar múltiples registros eficientemente"""
        session_id = "perf-test-session"
        
        # Limpiar
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.detections_collection.delete_many({"session_id": session_id})
        
        # Crear sesión
        await mongodb_adapter.create_session(session_id=session_id)
        
        # Guardar 100 detecciones
        import time
        start = time.time()
        
        for i in range(100):
            await mongodb_adapter.save_detection(
                session_id,
                {
                    "species_name": f"Species-{i % 10}",
                    "species_code": f"sp{i % 10}",
                    "confidence": 0.5 + (i % 50) * 0.01,
                    "start_time": float(i),
                    "end_time": float(i + 1),
                    "chunk_timestamp": i,
                    "processing_time": 0.01,
                    "chunk_sequence": i,
                }
            )
        
        elapsed = time.time() - start
        
        # Verificar
        detections = await mongodb_adapter.detections_collection.count_documents(
            {"session_id": session_id}
        )
        assert detections >= 100
        
        # Rendimiento: debe ser < 5 segundos para 100 inserciones
        assert elapsed < 5.0, f"Inserción lenta: {elapsed}s para 100 registros"
        
        # Limpiar
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.detections_collection.delete_many({"session_id": session_id})
    
    @pytest.mark.asyncio
    async def test_query_by_index(self, mongodb_adapter):
        """Debe buscar eficientemente usando índices"""
        session_id = "perf-test-query"
        
        # Limpiar y crear
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.detections_collection.delete_many({"session_id": session_id})
        await mongodb_adapter.create_session(session_id=session_id)
        
        # Guardar detecciones con diferentes especies
        species_codes = ["amro", "carw", "noca", "blca", "howr"]
        
        for i in range(50):
            await mongodb_adapter.save_detection(
                session_id,
                {
                    "species_name": f"Species-{i}",
                    "species_code": species_codes[i % len(species_codes)],
                    "confidence": 0.9,
                    "start_time": float(i),
                    "end_time": float(i + 1),
                    "chunk_timestamp": i,
                    "processing_time": 0.01,
                    "chunk_sequence": i,
                }
            )
        
        # Buscar por especie (debe usar índice)
        import time
        start = time.time()
        
        results = await mongodb_adapter.detections_collection.find(
            {"session_id": session_id, "species_code": "amro"}
        ).to_list(length=None)
        
        elapsed = time.time() - start
        
        assert len(results) == 10  # 50 registros / 5 especies
        assert elapsed < 0.5, f"Búsqueda lenta: {elapsed}s"
        
        # Limpiar
        await mongodb_adapter.sessions_collection.delete_one({"session_id": session_id})
        await mongodb_adapter.detections_collection.delete_many({"session_id": session_id})


# Import para ObjectId si motor está disponible
if MOTOR_AVAILABLE:
    from bson import ObjectId
else:
    ObjectId = None
