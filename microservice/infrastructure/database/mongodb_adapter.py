"""
Adaptador MongoDB para almacenar sesiones y detecciones
"""
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
import json

logger = logging.getLogger(__name__)

class MongoDBAdapter:
    """Adaptador para MongoDB usando Motor (async)"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database = None
        self.sessions_collection = None
        self.detections_collection = None
        
    async def connect(self):
        """Conectar a MongoDB"""
        try:
            # URL desde variables de entorno
            mongodb_url = os.getenv("MONGODB_URL", "mongodb://admin:birdnet123@localhost:27017/birdnet_db?authSource=admin")
            
            self.client = AsyncIOMotorClient(mongodb_url)
            
            # Probar conexión
            await self.client.admin.command('ping')
            
            # Configurar base de datos y colecciones
            self.database = self.client.birdnet_db
            self.sessions_collection = self.database.sessions
            self.detections_collection = self.database.detections
            
            # Crear índices
            await self._create_indexes()
            
            logger.info("✅ Conectado a MongoDB exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error conectando a MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Desconectar de MongoDB"""
        if self.client:
            self.client.close()
            logger.info("👋 Desconectado de MongoDB")
    
    async def _create_indexes(self):
        """Crear índices para optimizar consultas"""
        try:
            # Índices para sesiones
            await self.sessions_collection.create_index("session_id", unique=True)
            await self.sessions_collection.create_index("created_at")
            await self.sessions_collection.create_index("status")
            
            # Índices para detecciones
            await self.detections_collection.create_index("session_id")
            await self.detections_collection.create_index("species_code")
            await self.detections_collection.create_index("detected_at")
            await self.detections_collection.create_index([("session_id", 1), ("species_code", 1)])
            
            logger.debug("📊 Índices MongoDB creados")
            
        except Exception as e:
            logger.warning(f"⚠️ Error creando índices: {e}")
    
    async def create_session(self, session_id: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Crear nueva sesión de análisis"""
        try:
            session_doc = {
                "session_id": session_id,
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "total_chunks": 0,
                "total_detections": 0,
                "unique_species": 0,
                "metadata": metadata or {}
            }
            
            await self.sessions_collection.insert_one(session_doc)
            logger.info(f"📝 Sesión creada: {session_id}")
            
            return session_doc
            
        except DuplicateKeyError:
            logger.warning(f"⚠️ Sesión ya existe: {session_id}")
            raise ValueError(f"Sesión {session_id} ya existe")
        except Exception as e:
            logger.error(f"❌ Error creando sesión: {e}")
            raise
    
    async def save_detection(self, session_id: str, detection_data: Dict[str, Any]) -> str:
        """Guardar detección individual"""
        try:
            detection_doc = {
                "session_id": session_id,
                "species_name": detection_data.get("species_name"),
                "species_code": detection_data.get("species_code"),
                "confidence": detection_data.get("confidence"),
                "start_time": detection_data.get("start_time"),
                "end_time": detection_data.get("end_time"),
                "detected_at": datetime.now(timezone.utc),
                "chunk_timestamp": detection_data.get("chunk_timestamp"),
                "processing_info": {
                    "processing_time": detection_data.get("processing_time"),
                    "chunk_sequence": detection_data.get("chunk_sequence"),
                    "is_new_species": detection_data.get("is_new_species", False)
                }
            }
            
            result = await self.detections_collection.insert_one(detection_doc)
            detection_id = str(result.inserted_id)
            
            # Actualizar contadores de sesión
            await self._update_session_stats(session_id)
            
            logger.debug(f"🐦 Detección guardada: {detection_data.get('species_name')} en sesión {session_id}")
            
            return detection_id
            
        except Exception as e:
            logger.error(f"❌ Error guardando detección: {e}")
            raise
    
    async def _update_session_stats(self, session_id: str):
        """Actualizar estadísticas de la sesión"""
        try:
            # Contar detecciones totales
            total_detections = await self.detections_collection.count_documents({"session_id": session_id})
            
            # Contar especies únicas
            unique_species = len(await self.detections_collection.distinct("species_code", {"session_id": session_id}))
            
            # Actualizar sesión
            await self.sessions_collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "total_detections": total_detections,
                        "unique_species": unique_species,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$inc": {"total_chunks": 1}
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Error actualizando stats de sesión: {e}")
    
    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """Finalizar sesión y devolver resumen"""
        try:
            # Marcar sesión como completada
            await self.sessions_collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "status": "completed",
                        "ended_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            # Obtener resumen completo
            summary = await self.get_session_summary(session_id)
            
            logger.info(f"🔚 Sesión finalizada: {session_id} ({summary.get('total_detections', 0)} detecciones)")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error finalizando sesión: {e}")
            raise
    
    async def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Obtener resumen completo de la sesión"""
        try:
            # Obtener datos de la sesión
            session = await self.sessions_collection.find_one({"session_id": session_id})
            if not session:
                raise ValueError(f"Sesión no encontrada: {session_id}")
            
            # Obtener todas las detecciones
            detections_cursor = self.detections_collection.find({"session_id": session_id})
            detections = await detections_cursor.to_list(length=None)
            
            # Agrupar por especie
            species_summary = {}
            for detection in detections:
                species_code = detection["species_code"]
                if species_code not in species_summary:
                    species_summary[species_code] = {
                        "species_code": species_code,
                        "species_name": detection["species_name"],
                        "detection_count": 0,
                        "max_confidence": 0.0,
                        "first_detected_at": detection["detected_at"],
                        "detections": []
                    }
                
                species_summary[species_code]["detection_count"] += 1
                species_summary[species_code]["max_confidence"] = max(
                    species_summary[species_code]["max_confidence"],
                    detection["confidence"]
                )
                species_summary[species_code]["detections"].append({
                    "confidence": detection["confidence"],
                    "start_time": detection["start_time"],
                    "end_time": detection["end_time"],
                    "detected_at": detection["detected_at"].isoformat()
                })
            
            # Crear resumen final
            summary = {
                "session_id": session_id,
                "status": session.get("status", "unknown"),
                "created_at": session["created_at"].isoformat(),
                "ended_at": session.get("ended_at", datetime.now(timezone.utc)).isoformat(),
                "duration_seconds": (session.get("ended_at", datetime.now(timezone.utc)) - session["created_at"]).total_seconds(),
                "total_chunks": session.get("total_chunks", 0),
                "total_detections": session.get("total_detections", 0),
                "unique_species": session.get("unique_species", 0),
                "species_detected": list(species_summary.values()),
                "metadata": session.get("metadata", {})
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo resumen de sesión: {e}")
            raise
    
    async def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtener sesiones recientes"""
        try:
            cursor = self.sessions_collection.find().sort("created_at", -1).limit(limit)
            sessions = await cursor.to_list(length=limit)
            
            # Convertir ObjectId a string y datetime a ISO
            for session in sessions:
                session["_id"] = str(session["_id"])
                session["created_at"] = session["created_at"].isoformat()
                if "ended_at" in session:
                    session["ended_at"] = session["ended_at"].isoformat()
                session["updated_at"] = session["updated_at"].isoformat()
            
            return sessions
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo sesiones recientes: {e}")
            raise

# Instancia global
mongodb_adapter = MongoDBAdapter()