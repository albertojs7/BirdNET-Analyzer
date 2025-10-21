#!/usr/bin/env python3
"""
Script para generar reporte de pruebas disponibles
Muestra un resumen de todas las pruebas creadas
"""

import os
import json
from pathlib import Path

def analyze_test_files():
    """Analizar archivos de prueba"""
    test_dir = Path("tests")
    
    test_files = {
        "test_domain.py": {
            "classes": [
                "TestAudioAnalysis",
                "TestBirdDetection",
                "TestAnalysisStatus"
            ],
            "tests": 7,
            "description": "Pruebas de entidades de dominio"
        },
        "test_application.py": {
            "classes": [
                "TestAnalyzeAudioUseCase",
                "TestGetAnalysisStatusUseCase",
                "TestHealthCheckUseCase"
            ],
            "tests": 6,
            "description": "Pruebas de casos de uso"
        },
        "test_infrastructure.py": {
            "classes": [
                "TestInMemoryAnalysisRepository",
                "TestWebSocketNotificationService"
            ],
            "tests": 6,
            "description": "Pruebas de adaptadores e infraestructura"
        },
        "test_integration.py": {
            "classes": [
                "TestHealthCheckEndpoint",
                "TestSessionsAPIEndpoints",
                "TestConfigModule",
                "TestMongoDBAdapter",
                "TestBirdNetAdapter"
            ],
            "tests": 10,
            "description": "Pruebas de integración"
        }
    }
    
    return test_files

def print_report():
    """Imprimir reporte formateado"""
    
    print("=" * 70)
    print("📊 REPORTE DE PRUEBAS - BirdNET Microservice")
    print("=" * 70)
    print()
    
    test_files = analyze_test_files()
    
    total_tests = 0
    total_classes = 0
    
    for filename, info in test_files.items():
        print(f"\n📄 {filename}")
        print(f"   ├─ Descripción: {info['description']}")
        print(f"   ├─ Clases: {len(info['classes'])}")
        print(f"   ├─ Pruebas: {info['tests']}")
        print(f"   └─ Clases:")
        
        for cls in info['classes']:
            print(f"      • {cls}")
        
        total_tests += info['tests']
        total_classes += len(info['classes'])
    
    print()
    print("=" * 70)
    print(f"📈 RESUMEN TOTAL")
    print("=" * 70)
    print(f"   • Archivos de prueba: {len(test_files)}")
    print(f"   • Clases de prueba: {total_classes}")
    print(f"   • Pruebas unitarias: {total_tests}")
    print()
    
    print("🚀 COMANDOS PARA EJECUTAR:")
    print("=" * 70)
    print()
    print("  Instalar dependencias:")
    print("    pip install pytest pytest-asyncio pytest-mock pytest-cov")
    print()
    print("  Ejecutar todas las pruebas:")
    print("    ./run_tests.sh all")
    print("    # O sin el script:")
    print("    pytest tests/ -v")
    print()
    print("  Con cobertura:")
    print("    ./run_tests.sh coverage")
    print()
    print("  Suite específica:")
    print("    ./run_tests.sh domain      # Solo dominio")
    print("    ./run_tests.sh app         # Solo aplicación")
    print("    ./run_tests.sh infra       # Solo infraestructura")
    print("    ./run_tests.sh integration # Solo integración")
    print()
    print("=" * 70)
    print()

if __name__ == "__main__":
    print_report()
