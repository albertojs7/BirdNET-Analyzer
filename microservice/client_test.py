"""
Cliente de ejemplo para probar el microservicio WebSocket
"""
import asyncio
import websockets
import json
import base64
import os
from pathlib import Path

class BirdNetWebSocketClient:
    """Cliente WebSocket para el microservicio BirdNET"""
    
    def __init__(self, uri: str = "ws://localhost:8000/ws"):
        self.uri = uri
        self.websocket = None
    
    async def connect(self):
        """Conectar al WebSocket"""
        self.websocket = await websockets.connect(self.uri)
    
    async def disconnect(self):
        """Desconectar del WebSocket"""
        if self.websocket:
            await self.websocket.close()
    
    async def send_message(self, message: dict):
        """Enviar mensaje"""
        if not self.websocket:
            raise Exception("No conectado")
        
        await self.websocket.send(json.dumps(message))
    
    async def receive_message(self):
        """Recibir mensaje"""
        if not self.websocket:
            raise Exception("No conectado")
        
        message = await self.websocket.recv()
        return json.loads(message)
    
    async def analyze_audio_file(self, file_path: str):
        """Analizar archivo de audio"""
        if not os.path.exists(file_path):
            print(f"❌ Archivo no encontrado: {file_path}")
            return
        
        # Leer y codificar archivo
        with open(file_path, "rb") as f:
            audio_data = f.read()
        
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        filename = Path(file_path).name
        
        # Enviar solicitud de análisis
        message = {
            "type": "analyze_audio",
            "audio": audio_base64,
            "filename": filename
        }
        
        await self.send_message(message)
        
        # Escuchar respuestas
        while True:
            try:
                response = await self.receive_message()
                await self._handle_response(response)
                
                # Terminar si el análisis está completo o falló
                if response.get("type") in ["analysis_completed", "analysis_failed"]:
                    break
                    
            except websockets.exceptions.ConnectionClosed:
                break
    
    async def get_analysis_status(self, analysis_id: str):
        """Obtener estado de análisis"""
        message = {
            "type": "get_analysis_status",
            "analysis_id": analysis_id
        }
        
        await self.send_message(message)
        response = await self.receive_message()
        await self._handle_response(response)
    
    async def health_check(self):
        """Verificar salud del servicio"""
        message = {"type": "health_check"}
        
        await self.send_message(message)
        response = await self.receive_message()
        await self._handle_response(response)
    
    async def _handle_response(self, response: dict):
        """Manejar respuesta del servidor - Solo imprimir JSON"""
        print(json.dumps(response, indent=2, ensure_ascii=False))

async def test_microservice():
    """Probar el microservicio"""
    client = BirdNetWebSocketClient()
    
    try:
        await client.connect()
        
        # 1. Health check
        await client.health_check()
        
        # 2. Analizar archivo si existe
        audio_file = "../prueba_fixed.mp3"
        if os.path.exists(audio_file):
            await client.analyze_audio_file(audio_file)
        else:
            print(f"❌ Archivo {audio_file} no encontrado")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_microservice())