"""
Controlador WebSocket - Capa de interfaces
"""
import json
import base64
import logging
from typing import Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

from application.use_cases import AnalyzeAudioUseCase, GetAnalysisStatusUseCase, HealthCheckUseCase
from infrastructure.websocket.notification_service import WebSocketNotificationService

logger = logging.getLogger(__name__)

class WebSocketController:
    """Controlador para manejar conexiones WebSocket"""
    
    def __init__(
        self,
        analyze_audio_use_case: AnalyzeAudioUseCase,
        get_analysis_status_use_case: GetAnalysisStatusUseCase,
        health_check_use_case: HealthCheckUseCase,
        notification_service: WebSocketNotificationService
    ):
        self.analyze_audio_use_case = analyze_audio_use_case
        self.get_analysis_status_use_case = get_analysis_status_use_case
        self.health_check_use_case = health_check_use_case
        self.notification_service = notification_service
    
    async def handle_connection(self, websocket: WebSocket):
        """Manejar conexión WebSocket"""
        await websocket.accept()
        
        # Registrar conexión para notificaciones generales
        self.notification_service.register_connection(websocket)
        
        try:
            # Enviar mensaje de bienvenida
            await websocket.send_text(json.dumps({
                "type": "connected",
                "message": "Conectado al servicio de análisis de aves",
                "available_commands": [
                    "analyze_audio",
                    "get_analysis_status", 
                    "health_check"
                ]
            }))
            
            while True:
                # Recibir mensaje
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Procesar mensaje según tipo
                await self._handle_message(websocket, message)
                
        except WebSocketDisconnect:
            logger.info("Cliente desconectado")
        except Exception as e:
            logger.error(f"Error en conexión WebSocket: {e}")
            await self._send_error(websocket, str(e))
        finally:
            # Desregistrar conexión
            self.notification_service.unregister_connection(websocket)
    
    async def _handle_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """Procesar mensaje recibido"""
        message_type = message.get("type")
        
        if message_type == "analyze_audio":
            await self._handle_analyze_audio(websocket, message)
        elif message_type == "get_analysis_status":
            await self._handle_get_analysis_status(websocket, message)
        elif message_type == "health_check":
            await self._handle_health_check(websocket)
        else:
            await self._send_error(websocket, f"Tipo de mensaje no reconocido: {message_type}")
    
    async def _handle_analyze_audio(self, websocket: WebSocket, message: Dict[str, Any]):
        """Manejar solicitud de análisis de audio"""
        try:
            # Validar campos requeridos
            if "audio" not in message:
                await self._send_error(websocket, "Campo 'audio' requerido")
                return
            
            # Extraer datos
            audio_base64 = message["audio"]
            filename = message.get("filename", "audio.mp3")
            
            # Decodificar audio
            try:
                audio_data = base64.b64decode(audio_base64)
            except Exception as e:
                await self._send_error(websocket, f"Error decodificando audio Base64: {e}")
                return
            
            # Validar tamaño
            if len(audio_data) > 50 * 1024 * 1024:  # 50MB
                await self._send_error(websocket, "Archivo demasiado grande (máximo 50MB)")
                return
            
            # Ejecutar análisis
            analysis = await self.analyze_audio_use_case.execute(audio_data, filename)
            
            # El resultado se enviará automáticamente via notificaciones
            # Pero enviamos confirmación inmediata
            await websocket.send_text(json.dumps({
                "type": "analysis_accepted",
                "analysis_id": analysis.analysis_id,
                "message": "Análisis iniciado correctamente"
            }))
            
        except Exception as e:
            logger.error(f"Error procesando análisis: {e}")
            await self._send_error(websocket, f"Error procesando análisis: {e}")
    
    async def _handle_get_analysis_status(self, websocket: WebSocket, message: Dict[str, Any]):
        """Manejar solicitud de estado de análisis"""
        try:
            analysis_id = message.get("analysis_id")
            if not analysis_id:
                await self._send_error(websocket, "Campo 'analysis_id' requerido")
                return
            
            analysis = await self.get_analysis_status_use_case.execute(analysis_id)
            
            if analysis:
                await websocket.send_text(json.dumps({
                    "type": "analysis_status",
                    "analysis": analysis.to_dict()
                }))
            else:
                await websocket.send_text(json.dumps({
                    "type": "analysis_not_found",
                    "analysis_id": analysis_id,
                    "message": "Análisis no encontrado"
                }))
                
        except Exception as e:
            logger.error(f"Error obteniendo estado: {e}")
            await self._send_error(websocket, f"Error obteniendo estado: {e}")
    
    async def _handle_health_check(self, websocket: WebSocket):
        """Manejar verificación de salud"""
        try:
            health = await self.health_check_use_case.execute()
            
            await websocket.send_text(json.dumps({
                "type": "health_check",
                "health": health
            }))
            
        except Exception as e:
            logger.error(f"Error en health check: {e}")
            await self._send_error(websocket, f"Error en health check: {e}")
    
    async def _send_error(self, websocket: WebSocket, error_message: str):
        """Enviar mensaje de error"""
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": error_message
            }))
        except Exception as e:
            logger.error(f"Error enviando mensaje de error: {e}")