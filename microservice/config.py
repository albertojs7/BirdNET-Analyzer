"""
Configuración del microservicio
"""
import os
from dataclasses import dataclass

@dataclass
class Config:
    """Configuración"""
    
    # Servidor
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    # BirdNET
    min_confidence: float = 0.1
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    temp_dir: str = "/tmp"
    cleanup_temp_files: bool = True
    
    # Logging
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Crear configuración desde variables de entorno"""
        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            debug=os.getenv("DEBUG", "true").lower() == "true",
            min_confidence=float(os.getenv("MIN_CONFIDENCE", "0.1")),
            max_file_size=int(os.getenv("MAX_FILE_SIZE", str(50 * 1024 * 1024))),
            temp_dir=os.getenv("TEMP_DIR", "/tmp"),
            cleanup_temp_files=os.getenv("CLEANUP_TEMP_FILES", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )