"""
Configuración de pytest
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuración de pytest
pytest_plugins = []

# Fixtures globales
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Crear event loop para pruebas async"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
