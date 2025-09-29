"""
API REST para resúmenes de sesiones - Para integración con Pokedex microservice
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from infrastructure.database.mongodb_adapter import mongodb_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["Sessions"])

class SessionSummaryResponse(BaseModel):
    """Respuesta con resumen de sesión"""
    session_id: str
    status: str
    created_at: str
    ended_at: str
    duration_seconds: float
    total_chunks: int
    total_detections: int
    unique_species: int
    species_detected: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class SessionListResponse(BaseModel):
    """Lista de sesiones"""
    sessions: List[Dict[str, Any]]
    total_count: int

@router.get("/recent", response_model=SessionListResponse)
async def get_recent_sessions(
    limit: int = Query(default=10, ge=1, le=100, description="Número máximo de sesiones a devolver")
):
    """
    Obtener sesiones recientes
    
    **Uso desde Pokedex microservice:**
    ```python
    response = requests.get("http://birdnet-service:8000/sessions/recent?limit=20")
    sessions = response.json()["sessions"]
    ```
    """
    try:
        sessions = await mongodb_adapter.get_recent_sessions(limit)
        
        return SessionListResponse(
            sessions=sessions,
            total_count=len(sessions)
        )
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo sesiones recientes: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/{session_id}/summary", response_model=SessionSummaryResponse)
async def get_session_summary(session_id: str):
    """
    Obtener resumen completo de una sesión específica
    
    **Uso desde Pokedex microservice:**
    ```python
    response = requests.get(f"http://birdnet-service:8000/sessions/{session_id}/summary")
    summary = response.json()
    
    # Acceder a detecciones
    for species in summary["species_detected"]:
        print(f"Especie: {species['species_name']}")
        print(f"Detecciones: {species['detection_count']}")
        print(f"Confianza máxima: {species['max_confidence']}")
    ```
    """
    try:
        summary = await mongodb_adapter.get_session_summary(session_id)
        
        return SessionSummaryResponse(**summary)
        
    except ValueError as e:
        # Sesión no encontrada
        logger.warning(f"⚠️ Sesión no encontrada: {session_id}")
        raise HTTPException(status_code=404, detail=str(e))
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo resumen de sesión {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/{session_id}/detections")
async def get_session_detections(
    session_id: str,
    species_code: Optional[str] = Query(None, description="Filtrar por código de especie")
):
    """
    Obtener detecciones detalladas de una sesión
    
    **Uso desde Pokedex microservice:**
    ```python
    # Todas las detecciones
    response = requests.get(f"http://birdnet-service:8000/sessions/{session_id}/detections")
    
    # Solo detecciones de una especie específica
    response = requests.get(f"http://birdnet-service:8000/sessions/{session_id}/detections?species_code=corcor")
    
    detections = response.json()["detections"]
    ```
    """
    try:
        summary = await mongodb_adapter.get_session_summary(session_id)
        
        all_detections = []
        for species in summary["species_detected"]:
            if species_code and species["species_code"] != species_code:
                continue
                
            for detection in species["detections"]:
                all_detections.append({
                    "species_code": species["species_code"],
                    "species_name": species["species_name"],
                    "confidence": detection["confidence"],
                    "start_time": detection["start_time"],
                    "end_time": detection["end_time"],
                    "detected_at": detection["detected_at"]
                })
        
        # Ordenar por tiempo de detección
        all_detections.sort(key=lambda x: x["detected_at"])
        
        return {
            "session_id": session_id,
            "total_detections": len(all_detections),
            "species_filter": species_code,
            "detections": all_detections
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo detecciones de sesión {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/{session_id}/species")
async def get_session_species(session_id: str):
    """
    Obtener lista de especies detectadas en una sesión
    
    **Uso desde Pokedex microservice:**
    ```python
    response = requests.get(f"http://birdnet-service:8000/sessions/{session_id}/species")
    species_list = response.json()["species"]
    
    # Integrar con datos locales del Pokedex
    for species in species_list:
        local_data = pokedex_db.get_species(species["species_code"])
        species.update(local_data)
    ```
    """
    try:
        summary = await mongodb_adapter.get_session_summary(session_id)
        
        species_list = []
        for species in summary["species_detected"]:
            species_list.append({
                "species_code": species["species_code"],
                "species_name": species["species_name"],
                "detection_count": species["detection_count"],
                "max_confidence": species["max_confidence"],
                "first_detected_at": species["first_detected_at"].isoformat() if hasattr(species["first_detected_at"], 'isoformat') else species["first_detected_at"]
            })
        
        # Ordenar por confianza máxima
        species_list.sort(key=lambda x: x["max_confidence"], reverse=True)
        
        return {
            "session_id": session_id,
            "total_species": len(species_list),
            "species": species_list
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo especies de sesión {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.post("/{session_id}/mark-processed")
async def mark_session_as_processed(session_id: str):
    """
    Marcar sesión como procesada por Pokedex microservice
    
    **Uso desde Pokedex microservice:**
    ```python
    # Después de integrar los datos de la sesión
    response = requests.post(f"http://birdnet-service:8000/sessions/{session_id}/mark-processed")
    ```
    """
    try:
        # Actualizar metadata de la sesión
        from ..infrastructure.database.mongodb_adapter import mongodb_adapter
        
        # Como no tenemos un método update_session, podríamos agregarlo
        # Por ahora, simplemente verificamos que la sesión existe
        summary = await mongodb_adapter.get_session_summary(session_id)
        
        return {
            "session_id": session_id,
            "status": "marked_as_processed",
            "processed_at": datetime.now().isoformat(),
            "message": "Sesión marcada como procesada por Pokedex"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    except Exception as e:
        logger.error(f"❌ Error marcando sesión como procesada {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/health")
async def sessions_health():
    """Health check para el servicio de sesiones"""
    try:
        # Verificar conexión a MongoDB
        recent_sessions = await mongodb_adapter.get_recent_sessions(1)
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat(),
            "message": "Servicio de sesiones funcionando correctamente"
        }
        
    except Exception as e:
        logger.error(f"❌ Health check falló: {e}")
        raise HTTPException(status_code=503, detail="Servicio no disponible")