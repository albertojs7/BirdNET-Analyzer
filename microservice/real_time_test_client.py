"""
Cliente de prueba para análisis en tiempo real
Simula el comportamiento de una app móvil enviando chunks de audio cada 2 segundos
"""

import asyncio
import websockets
import json
import base64
import os
import time
from typing import Optional

class RealTimeTestClient:
    def __init__(self):
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.session_id: Optional[str] = None
        self.chunks_sent = 0
        self.detections_received = 0
        self.latency_stats = []
        
    async def connect(self, uri: str = "ws://localhost:8000/ws"):
        """Conectar al servidor WebSocket"""
        try:
            self.websocket = await websockets.connect(uri)
            
            # Consumir mensaje de bienvenida
            welcome = await self.websocket.recv()
            welcome_data = json.loads(welcome)
            print(f"{welcome_data['message']}")
            print(f"Comandos disponibles: {', '.join(welcome_data['available_commands'])}")
            
            print("Conectado al servidor WebSocket")
            return True
            
        except Exception as e:
            print(f"Error conectando: {e}")
            return False
    
    async def disconnect(self):
        """Desconectar del servidor"""
        if self.websocket:
            await self.websocket.close()
            print("👋 Desconectado del servidor")
    
    async def send_message(self, message: dict):
        """Enviar mensaje al servidor"""
        if self.websocket:
            await self.websocket.send(json.dumps(message))
    
    async def receive_message(self) -> dict:
        """Recibir mensaje del servidor"""
        if self.websocket:
            response = await self.websocket.recv()
            return json.loads(response)
        return {}
    
    async def start_real_time_session(self) -> bool:
        """Iniciar sesión de escucha en tiempo real"""
        message = {"type": "start_real_time_listening"}
        
        await self.send_message(message)
        response = await self.receive_message()
        
        if response.get("type") == "real_time_session_started":
            self.session_id = response.get("session_id")
            config = response.get("config", {})
            
            print(f"Sesión de tiempo real iniciada: {self.session_id}")
            print(f"Configuración recomendada:")
            print(f"   - Duración chunk: {config.get('recommended_chunk_duration', 2.0)}s")
            print(f"   - Overlap: {config.get('recommended_overlap', 0.5)}s")
            print(f"   - Latencia esperada: {config.get('max_latency_expected', '2-5 segundos')}")
            return True
        else:
            print(f"❌ Error iniciando sesión: {response}")
            return False
    
    async def simulate_real_time_audio(self, test_file: str, chunk_duration: float = 2.0, total_duration: float = 20.0):
        """
        Simular envío de audio en tiempo real usando archivo de prueba
        
        Args:
            test_file: Archivo de audio para usar como fuente
            chunk_duration: Duración de cada chunk en segundos
            total_duration: Duración total de la simulación
        """
        if not os.path.exists(test_file):
            print(f"❌ Archivo no encontrado: {test_file}")
            return
        
        if not self.session_id:
            print("❌ No hay sesión activa")
            return
        
        # Leer archivo de audio
        with open(test_file, "rb") as f:
            audio_data = f.read()
        
        print(f"📁 Usando archivo: {test_file} ({len(audio_data)} bytes)")
        print(f"⏰ Simulando {total_duration}s de audio en tiempo real...")
        print(f"📤 Enviando chunks cada {chunk_duration}s")
        print()
        
        # Tarea para escuchar respuestas
        listen_task = asyncio.create_task(self._listen_for_responses())
        
        chunks_to_send = int(total_duration / chunk_duration)
        
        for i in range(chunks_to_send):
            timestamp = int(time.time() * 1000)  # Timestamp en milisegundos
            chunk_start_time = time.time()
            
            print(f"📤 Enviando chunk {i+1}/{chunks_to_send} (timestamp: {timestamp})")
            
            # Enviar chunk (en tiempo real usaríamos diferentes partes del audio,
            # pero para la demo enviamos el archivo completo cada vez)
            message = {
                "type": "send_real_time_audio",
                "session_id": self.session_id,
                "audio": base64.b64encode(audio_data).decode('utf-8'),
                "timestamp": timestamp,
                "chunk_info": {
                    "duration": chunk_duration,
                    "chunk_number": i + 1,
                    "total_chunks": chunks_to_send
                }
            }
            
            await self.send_message(message)
            self.chunks_sent += 1
            
            # Esperar tiempo del chunk antes del siguiente
            await asyncio.sleep(chunk_duration)
        
        print(f"\n✅ Simulación completada: {chunks_to_send} chunks enviados")
        
        # Esperar un poco más para recibir últimas respuestas
        print("⏳ Esperando análisis finales...")
        await asyncio.sleep(5)
        
        # Cancelar tarea de escucha ANTES de hacer más recv()
        listen_task.cancel()
        
        # Esperar a que la tarea termine completamente
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
        
        # Mostrar estadísticas
        self._show_statistics()
    
    async def _listen_for_responses(self):
        """Escuchar respuestas del servidor continuamente"""
        try:
            while True:
                response = await self.receive_message()
                await self._handle_response(response)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ Error escuchando respuestas: {e}")
    
    async def _handle_response(self, response: dict):
        """Manejar respuestas del servidor"""
        response_type = response.get("type")
        
        if response_type == "chunk_received":
            timestamp = response.get("timestamp")
            queue_pos = response.get("queue_position", 0)
            print(f"   ✅ Chunk recibido (timestamp: {timestamp}, cola: {queue_pos})")
            
        elif response_type == "real_time_detections":
            await self._handle_detections(response)
            
        elif response_type == "chunk_analyzed":
            timestamp = response.get("analysis_timestamp")
            processing_time = response.get("processing_time", 0)
            print(f"   📊 Chunk {timestamp} analizado en {processing_time}s - sin detecciones")
            
        elif response_type == "analysis_error":
            timestamp = response.get("timestamp")
            error = response.get("error")
            print(f"   ❌ Error analizando chunk {timestamp}: {error}")
            
        else:
            print(f"   📩 Respuesta: {json.dumps(response, indent=4, ensure_ascii=False)}")
    
    async def _handle_detections(self, response: dict):
        """Manejar detecciones encontradas"""
        timestamp = response.get("analysis_timestamp")
        processing_time = response.get("processing_time", 0)
        birds = response.get("birds", [])
        latency_info = response.get("latency_info", "")
        
        self.detections_received += len(birds)
        self.latency_stats.append(processing_time)
        
        print(f"   🐦 DETECCIONES ENCONTRADAS! ({latency_info})")
        for bird in birds:
            species = bird.get("species_name", "Unknown")
            confidence = bird.get("confidence", 0)
            start_time = bird.get("start_time", 0)
            end_time = bird.get("end_time", 0)
            
            print(f"      • {species}: {confidence:.3f} ({start_time:.1f}s - {end_time:.1f}s)")
        
        print()
    
    def _show_statistics(self):
        """Mostrar estadísticas de la sesión"""
        print(f"\n📊 ESTADÍSTICAS DE LA SESIÓN:")
        print(f"   📤 Chunks enviados: {self.chunks_sent}")
        print(f"   🐦 Detecciones recibidas: {self.detections_received}")
        
        if self.latency_stats:
            avg_latency = sum(self.latency_stats) / len(self.latency_stats)
            max_latency = max(self.latency_stats)
            min_latency = min(self.latency_stats)
            
            print(f"   ⏱️ Latencia promedio: {avg_latency:.1f}s")
            print(f"   ⏱️ Latencia máxima: {max_latency:.1f}s")
            print(f"   ⏱️ Latencia mínima: {min_latency:.1f}s")
            
            if avg_latency < 2.0:
                print("   ⚡ ¡Excelente latencia para tiempo real!")
            elif avg_latency < 3.0:
                print("   ✅ Latencia aceptable para tiempo real")
            else:
                print("   ⚠️ Latencia alta - considerar optimizaciones")
    
    async def stop_real_time_session(self):
        """Finalizar sesión de tiempo real"""
        if not self.session_id:
            print("❌ No hay sesión activa")
            return
        
        message = {
            "type": "stop_real_time_listening",
            "session_id": self.session_id
        }
        
        try:
            await self.send_message(message)
            
            # Esperar respuesta con timeout para evitar bloqueos
            response = await asyncio.wait_for(self.receive_message(), timeout=5.0)
            
            if response.get("type") == "real_time_session_ended":
                stats = response.get("statistics", {})
                print(f"🔚 Sesión finalizada:")
                print(f"   ⏱️ Duración: {stats.get('duration_seconds', 0)}s")
                print(f"   📤 Chunks procesados: {stats.get('total_chunks_received', 0)}")
                print(f"   🐦 Detecciones totales: {stats.get('total_detections', 0)}")
                print(f"   🦅 Especies únicas: {stats.get('unique_species', 0)}")
            else:
                print(f"❌ Error finalizando sesión: {response}")
                
        except asyncio.TimeoutError:
            print("⏰ Timeout esperando respuesta de finalización")
        except Exception as e:
            print(f"❌ Error enviando comando de stop: {e}")
        
        self.session_id = None

async def main():
    """Función principal de prueba"""
    print("🎵 Cliente de Prueba - Análisis en Tiempo Real")
    print("=" * 60)
    
    client = RealTimeTestClient()
    
    try:
        # 1. Conectar
        if not await client.connect():
            return
        
        # 2. Iniciar sesión de tiempo real
        if await client.start_real_time_session():
            
            # 3. Simular audio en tiempo real
            test_file = "/mnt/c/Users/victus R/Documents/BirdNET-Analyzer/prueba2.mp3"
            
            if os.path.exists(test_file):
                await client.simulate_real_time_audio(
                    test_file, 
                    chunk_duration=2.0,    # 2 segundos por chunk
                    total_duration=15.0    # 15 segundos total
                )
            else:
                print(f"⚠️ Archivo de prueba no encontrado: {test_file}")
                print("Simulando sin audio...")
                await asyncio.sleep(10)
            
            # 4. Finalizar sesión
            await client.stop_real_time_session()
        
    except KeyboardInterrupt:
        print("\n⏹️ Prueba interrumpida por usuario")
    except Exception as e:
        print(f"❌ Error en prueba: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()

if __name__ == "__main__":
    print("🚀 Iniciando cliente de tiempo real...")
    asyncio.run(main())
