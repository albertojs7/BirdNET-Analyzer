import asyncio
import websockets
import json
import base64
import os

async def test_birdnet_websocket():
    """Cliente de prueba para el servidor WebSocket de BirdNET"""
    uri = "ws://localhost:8000/ws"
    
    # Verificar que existe el archivo de audio
    audio_file = "../prueba_fixed.mp3"  # Archivo en la raíz del proyecto
    
    if not os.path.exists(audio_file):
        print(f"❌ No se encuentra el archivo: {audio_file}")
        return
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Conectado al servidor WebSocket")
            print(f"🔊 Enviando archivo: {audio_file}")
            
            # Leer archivo de audio
            with open(audio_file, "rb") as f:
                audio_data = f.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Crear mensaje
            message = {
                "type": "audio", 
                "filename": "prueba_fixed.mp3",
                "audio": audio_base64
            }
            
            # Enviar al WebSocket
            await websocket.send(json.dumps(message))
            print("📤 Audio enviado, esperando respuesta...")
            
            # Escuchar respuestas
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                if data.get("type") == "status":
                    print(f"📊 {data['message']}")
                
                elif data.get("type") == "results":
                    print(f"\n🎯 Resultados para: {data['filename']}")
                    print(f"🔢 Total detecciones: {data['total_detections']}")
                    
                    if data['detections']:
                        print("\n🐦 Aves detectadas:")
                        print("-" * 50)
                        for i, detection in enumerate(data['detections'], 1):
                            print(f"{i}. {detection['common_name']}")
                            print(f"   Código: {detection['species_code']}")
                            print(f"   Tiempo: {detection['begin_time']:.1f}s - {detection['end_time']:.1f}s")
                            print(f"   Confianza: {detection['confidence']:.2f}")
                    else:
                        print("🚫 No se detectaron aves en el audio")
                    
                    break  # Terminar después de recibir resultados
                    
    except ConnectionRefusedError:
        print("❌ No se pudo conectar al servidor")
        print("💡 Asegúrate de que el servidor esté corriendo:")
        print("   python3 analyzer_connection.py")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🧪 Cliente de prueba para BirdNET")
    print("=" * 40)
    asyncio.run(test_birdnet_websocket())