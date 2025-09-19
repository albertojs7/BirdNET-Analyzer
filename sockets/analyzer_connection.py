import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from birdnet_analyzer.analyze.core import analyze
from fastapi import FastAPI, WebSocket
import json
import tempfile
import base64
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Endpoint principal - información del servidor"""
    return {
        "message": "BirdNET Analyzer API funcionando",
        "endpoints": {
            "websocket": "ws://localhost:8000/ws",
            "docs": "http://localhost:8000/docs"
        }
    }

@app.get("/health")
async def health_check():
    """Endpoint de salud del servidor"""
    return {"status": "healthy", "message": "Servidor funcionando"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Recibir mensaje
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "audio":
                # Decodificar audio
                audio_data = base64.b64decode(message["audio"])
                filename = message.get("filename", "audio.mp3")
                
                # Guardar temporal
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    temp_file.write(audio_data)
                    temp_path = temp_file.name
                
                # Análisis
                await websocket.send_text(json.dumps({
                    "type": "status", 
                    "message": "Analizando..."
                }))
                
                results = analyze_audio_file(temp_path)
                os.unlink(temp_path)
                
                # Enviar resultados
                response = {
                    "type": "results",
                    "filename": filename,
                    "detections": results,
                    "total_detections": len(results)
                }
                await websocket.send_text(json.dumps(response))
                
    except WebSocketDisconnect:
        print("Cliente desconectado")

def analyze_audio_file(audio_file_path: str) -> List[Dict]:
    """Analizar archivo de audio con BirdNET"""
    output_dir = tempfile.mkdtemp()
    
    # Ejecutar análisis
    analyze(audio_input=audio_file_path, output=output_dir)
    
    # Leer resultados
    audio_name = os.path.splitext(os.path.basename(audio_file_path))[0]
    result_file = os.path.join(output_dir, f"{audio_name}.BirdNET.selection.table.txt")
    
    results = []
    if os.path.exists(result_file):
        with open(result_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[1:]:  # Saltar header
                if line.strip():
                    parts = line.strip().split('\t')
                    if len(parts) >= 10:
                        results.append({
                            "begin_time": float(parts[3]),
                            "end_time": float(parts[4]),
                            "common_name": parts[7],
                            "species_code": parts[8],
                            "confidence": float(parts[9])
                        })
    return results

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)