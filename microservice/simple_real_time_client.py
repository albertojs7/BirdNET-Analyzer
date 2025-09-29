#!/usr/bin/env python3
"""
Cliente simple para tiempo real - Sin concurrencia WebSocket
"""

import asyncio
import websockets
import json
import base64
import os
import time

class SimpleRealTimeClient:
    def __init__(self):
        self.websocket = None
        self.session_id = None
        
    async def connect(self):
        """Conectar al servidor"""
        try:
            self.websocket = await websockets.connect("ws://localhost:8000/ws")
            
            # Recibir mensaje de bienvenida
            welcome = await self.websocket.recv()
            welcome_data = json.loads(welcome)
            print(f"✅ Conectado: {welcome_data['message']}")
            return True
            
        except Exception as e:
            print(f"❌ Error conectando: {e}")
            return False
    
    async def start_session(self):
        """Iniciar sesión de tiempo real"""
        message = {"type": "start_real_time_listening"}
        
        await self.websocket.send(json.dumps(message))
        response = json.loads(await self.websocket.recv())
        
        if response.get("type") == "real_time_session_started":
            self.session_id = response.get("session_id")
            print(f"🎵 Sesión iniciada: {self.session_id}")
            return True
        else:
            print(f"❌ Error: {response}")
            return False
    
    async def send_audio_and_wait(self, audio_data, timestamp):
        """Enviar audio y esperar TODAS las respuestas"""
        print(f"\n📤 Enviando chunk (timestamp: {timestamp})")
        
        # 1. Enviar audio
        message = {
            "type": "send_real_time_audio",
            "session_id": self.session_id,
            "audio": base64.b64encode(audio_data).decode('utf-8'),
            "timestamp": timestamp
        }
        
        await self.websocket.send(json.dumps(message))
        
        # 2. Esperar confirmación inmediata
        response1 = json.loads(await self.websocket.recv())
        print(f"   📥 Respuesta 1: {response1.get('type')} - {response1.get('message', '')}")
        
        # 3. Esperar resultado del análisis
        print("   ⏳ Esperando análisis...")
        response2 = json.loads(await self.websocket.recv())
        
        if response2.get("type") == "real_time_detections":
            birds = response2.get("birds", [])
            processing_time = response2.get("processing_time", 0)
            print(f"   🐦 ¡{len(birds)} DETECCIONES! (procesado en {processing_time}s)")
            
            for bird in birds:
                species = bird.get("species_name")
                confidence = bird.get("confidence", 0)
                print(f"      • {species}: {confidence:.3f}")
                
        elif response2.get("type") == "chunk_analyzed":
            processing_time = response2.get("processing_time", 0)
            print(f"   📊 Sin detecciones (procesado en {processing_time}s)")
            
        elif response2.get("type") == "analysis_error":
            error = response2.get("error")
            print(f"   ❌ Error en análisis: {error}")
            
        else:
            print(f"   📩 Respuesta inesperada: {response2}")
    
    async def test_with_file(self, file_path, num_chunks=3):
        """Probar con archivo real"""
        if not os.path.exists(file_path):
            print(f"❌ Archivo no encontrado: {file_path}")
            return
        
        # Leer archivo
        with open(file_path, "rb") as f:
            audio_data = f.read()
        
        print(f"📁 Archivo: {file_path} ({len(audio_data)} bytes)")
        
        # Enviar chunks secuencialmente
        for i in range(num_chunks):
            timestamp = int(time.time() * 1000) + i * 1000
            await self.send_audio_and_wait(audio_data, timestamp)
            
            # Pausa entre chunks
            if i < num_chunks - 1:
                print("   💤 Pausa 2 segundos...")
                await asyncio.sleep(2)
    
    async def stop_session(self):
        """Finalizar sesión"""
        if not self.session_id:
            return
        
        message = {
            "type": "stop_real_time_listening", 
            "session_id": self.session_id
        }
        
        await self.websocket.send(json.dumps(message))
        response = json.loads(await self.websocket.recv())
        
        if response.get("type") == "real_time_session_ended":
            stats = response.get("statistics", {})
            print(f"\n🔚 Sesión finalizada:")
            print(f"   📤 Chunks: {stats.get('total_chunks_received', 0)}")
            print(f"   🐦 Detecciones: {stats.get('total_detections', 0)}")
        
    async def disconnect(self):
        """Desconectar"""
        if self.websocket:
            await self.websocket.close()
            print("👋 Desconectado")

async def main():
    print("🧪 Cliente Simple de Tiempo Real")
    print("=" * 50)
    
    client = SimpleRealTimeClient()
    
    try:
        # Conectar
        if not await client.connect():
            return
        
        # Iniciar sesión
        if await client.start_session():
            
            # Probar con archivo que sabemos que funciona
            await client.test_with_file(
                "/mnt/c/Users/victus R/Documents/BirdNET-Analyzer/prueba.mp3",
                num_chunks=3
            )
            
            # Finalizar
            await client.stop_session()
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())