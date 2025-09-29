"""
Servicio de notificaciones WebSocket - Capa de infraestructura
"""
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

from domain.entities import AudioAnalysis, RealTimeDetection
from domain.ports import NotificationPort

logger = logging.getLogger(__name__)

class WebSocketNotificationService(NotificationPort):
    """Servicio de notificaciones usando WebSockets"""
    
    def __init__(self):
        # Mantener conexiones activas por analysis_id
        self._connections: Dict[str, WebSocket] = {}
        # Mantener conexiones generales
        self._general_connections: Set[WebSocket] = set()
        # Mantener conexiones de streaming por session_id
        self._streaming_connections: Dict[str, WebSocket] = {}
    
    def register_connection(self, websocket: WebSocket, analysis_id: str = None, session_id: str = None):
        """Registrar conexión WebSocket"""
        if analysis_id:
            self._connections[analysis_id] = websocket
        elif session_id:
            self._streaming_connections[session_id] = websocket
        else:
            self._general_connections.add(websocket)
    
    def unregister_connection(self, websocket: WebSocket, analysis_id: str = None, session_id: str = None):
        """Desregistrar conexión WebSocket"""
        if analysis_id and analysis_id in self._connections:
            del self._connections[analysis_id]
        elif session_id and session_id in self._streaming_connections:
            del self._streaming_connections[session_id]
        else:
            self._general_connections.discard(websocket)
    
    async def _send_message(self, websocket: WebSocket, message: dict):
        """Enviar mensaje por WebSocket con manejo de errores"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error enviando mensaje WebSocket: {e}")
    
    async def notify_analysis_started(self, analysis_id: str) -> None:
        """Notificar inicio de análisis"""
        message = {
            "type": "analysis_started",
            "analysis_id": analysis_id,
            "message": "Análisis iniciado"
        }
        
        # Enviar a conexión específica si existe
        if analysis_id in self._connections:
            await self._send_message(self._connections[analysis_id], message)
        
        # Enviar a conexiones generales
        for websocket in self._general_connections:
            await self._send_message(websocket, message)
    
    async def notify_analysis_progress(self, analysis_id: str, message: str) -> None:
        """Notificar progreso del análisis"""
        notification = {
            "type": "analysis_progress",
            "analysis_id": analysis_id,
            "message": message
        }
        
        # Enviar a conexión específica si existe
        if analysis_id in self._connections:
            await self._send_message(self._connections[analysis_id], notification)
        
        # Enviar a conexiones generales
        for websocket in self._general_connections:
            await self._send_message(websocket, notification)
    
    async def notify_analysis_completed(self, analysis: AudioAnalysis) -> None:
        """Notificar análisis completado"""
        message = {
            "type": "analysis_completed",
            "analysis_id": analysis.analysis_id,
            "result": analysis.to_dict()
        }
        
        # Enviar a conexión específica si existe
        if analysis.analysis_id in self._connections:
            await self._send_message(self._connections[analysis.analysis_id], message)
        
        # Enviar a conexiones generales
        for websocket in self._general_connections:
            await self._send_message(websocket, message)
    
    async def notify_analysis_failed(self, analysis_id: str, error: str) -> None:
        """Notificar fallo en análisis"""
        message = {
            "type": "analysis_failed",
            "analysis_id": analysis_id,
            "error": error
        }
        
        # Enviar a conexión específica si existe
        if analysis_id in self._connections:
            await self._send_message(self._connections[analysis_id], message)
        
        # Enviar a conexiones generales
        for websocket in self._general_connections:
            await self._send_message(websocket, message)
    
    async def notify_real_time_detection(self, detection: RealTimeDetection) -> None:
        """Notificar detección en tiempo real"""
        message = {
            "type": "real_time_detection",
            "detection": detection.to_dict()
        }
        
        # Enviar a conexión específica de streaming si existe
        if detection.session_id in self._streaming_connections:
            await self._send_message(self._streaming_connections[detection.session_id], message)
        
        # Enviar a conexiones generales
        for websocket in self._general_connections:
            await self._send_message(websocket, message)