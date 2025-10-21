# 🧪 Pruebas Unitarias del Microservicio BirdNET

Suite completa de pruebas para el microservicio BirdNET con arquitectura limpia.

## 📋 Estructura de Pruebas

```
tests/
├── __init__.py                 # Inicialización del módulo de pruebas
├── conftest.py                # Configuración y fixtures de pytest
├── test_domain.py             # Pruebas de entidades y dominio
├── test_application.py        # Pruebas de casos de uso
├── test_infrastructure.py     # Pruebas de infraestructura
├── test_integration.py        # Pruebas de integración
└── README.md                  # Este archivo
```

## 🚀 Instalación

### Paso 1: Instalar dependencias de prueba

```bash
pip install pytest pytest-asyncio pytest-cov pytest-mock httpx
```

### Paso 2: Agregar a requirements.txt (opcional)

```bash
# Para desarrollo/testing
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov pytest-mock
```

## ▶️ Ejecutar Pruebas

### Ejecutar todas las pruebas
```bash
pytest
```

### Ejecutar con verbosidad
```bash
pytest -v
```

### Ejecutar suite específica
```bash
# Solo pruebas de dominio
pytest tests/test_domain.py -v

# Solo pruebas de aplicación
pytest tests/test_application.py -v

# Solo pruebas de infraestructura
pytest tests/test_infrastructure.py -v

# Solo pruebas de integración
pytest tests/test_integration.py -v
```

### Ejecutar test específico
```bash
pytest tests/test_domain.py::TestBirdDetection::test_bird_detection_duration -v
```

### Con cobertura de código
```bash
pytest --cov=. --cov-report=html
```

Luego abre `htmlcov/index.html` en el navegador.

### Ejecutar solo pruebas rápidas (sin integraciones)
```bash
pytest -m "not integration"
```

### Ejecutar solo pruebas que requieren MongoDB
```bash
pytest -m "mongodb"
```

## 🧩 Cobertura de Pruebas

### Capa de Dominio (`test_domain.py`)
- ✅ Creación de entidades `AudioAnalysis`
- ✅ Creación de detecciones `BirdDetection`
- ✅ Validación de estados `AnalysisStatus`
- ✅ Transiciones de estado

**Coverage esperado**: 100%

### Capa de Aplicación (`test_application.py`)
- ✅ Caso de uso `AnalyzeAudioUseCase`
- ✅ Filtrado por confianza mínima
- ✅ Caso de uso `GetAnalysisStatusUseCase`
- ✅ Caso de uso `HealthCheckUseCase`
- ✅ Manejo de errores

**Coverage esperado**: 85-95%

### Capa de Infraestructura (`test_infrastructure.py`)
- ✅ Repositorio en memoria
- ✅ Servicio WebSocket
- ✅ Conexión MongoDB
- ✅ Guardado de sesiones y detecciones

**Coverage esperado**: 80-90%

### Pruebas de Integración (`test_integration.py`)
- ✅ Endpoints REST
- ✅ Health check
- ✅ Adaptador BirdNET
- ✅ Análisis completo

**Coverage esperado**: 70-80%

## 🔧 Fixtures Disponibles

### Mock Analyzer
```python
@pytest.fixture
def mock_analyzer(self):
    analyzer = AsyncMock()
    analyzer.is_service_available = AsyncMock(return_value=True)
    analyzer.analyze_audio = AsyncMock(return_value=[...])
    return analyzer
```

### Mock Repository
```python
@pytest.fixture
def mock_repository(self):
    repository = AsyncMock()
    repository.save_analysis = AsyncMock()
    repository.get_analysis = AsyncMock()
    return repository
```

### Mock Notification Service
```python
@pytest.fixture
def mock_notification_service(self):
    service = AsyncMock()
    service.notify_analysis_started = AsyncMock()
    return service
```

## 📊 Ejemplo: Escribir una Nueva Prueba

```python
import pytest
from domain.entities import BirdDetection

class TestMiNuevaFuncionalidad:
    """Pruebas para mi nueva funcionalidad"""
    
    def test_mi_prueba(self):
        """Descripción de qué prueba"""
        # Arrange - Preparar datos
        detection = BirdDetection(
            species_name="Test Bird",
            species_code="test",
            confidence=0.8,
            start_time=0.0,
            end_time=1.0
        )
        
        # Act - Ejecutar lógica
        result = detection.species_name
        
        # Assert - Verificar resultado
        assert result == "Test Bird"
```

## 🐳 Pruebas con Docker

### Ejecutar pruebas dentro del contenedor
```bash
# Desde el host
docker exec -it birdnet-microservice pytest -v

# O con cobertura
docker exec -it birdnet-microservice pytest --cov=. -v
```

### Incluir pruebas en el build de Docker

Agregar a `Dockerfile`:
```dockerfile
# Instalar dependencias de prueba
RUN pip install pytest pytest-asyncio pytest-mock

# Ejecutar pruebas
RUN pytest tests/ --tb=short
```

## 📈 CI/CD Integration

### GitHub Actions Ejemplo
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.10
      
      - name: Instalar dependencias
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-mock pytest-cov
      
      - name: Ejecutar pruebas
        run: pytest --cov=. --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## 🐛 Troubleshooting

### Error: "No module named 'pytest'"
```bash
pip install pytest
```

### Error: "asyncio.run() cannot be called from a running event loop"
```bash
# Solución: Usar pytest-asyncio
pip install pytest-asyncio
```

### Error: "MongoDB connection refused"
```bash
# MongoDB no está corriendo. Opciones:
# 1. Iniciar MongoDB
docker compose up -d mongodb

# 2. O ejecutar solo pruebas sin MongoDB
pytest -m "not mongodb"
```

### Error: "Import error"
```bash
# Asegurate que estás en el directorio correcto
cd microservice/
pytest tests/
```

## 📝 Mejores Prácticas

1. **Nombres descriptivos**: `test_should_filter_detections_by_confidence`
2. **Una cosa por test**: Cada test verifica un comportamiento específico
3. **Arrange-Act-Assert**: Preparar, ejecutar, verificar
4. **Fixtures para reutilización**: Evitar código duplicado
5. **Mocks para dependencias**: No depender de BD real
6. **Tests independientes**: Cada test debe ser independiente
7. **Coverage > 80%**: Objetivo mínimo de cobertura

## 🚀 Próximos Pasos

- [ ] Agregar pruebas de carga
- [ ] Agregar pruebas de seguridad
- [ ] Pruebas de WebSocket
- [ ] Pruebas de caché
- [ ] Pruebas de performance

## 📚 Referencias

- [Pytest Documentation](https://docs.pytest.org/)
- [Testing FastAPI](https://fastapi.tiangolo.com/tutorial/testing/)
- [Unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [Pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
