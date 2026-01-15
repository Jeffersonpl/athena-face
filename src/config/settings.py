"""
Configuracoes gerais do Athena Face
"""

import os
from pathlib import Path
from typing import List

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = Path.home() / ".insightface" / "models"

# InsightFace
FACE_MODEL_NAME = os.getenv("FACE_MODEL_NAME", "buffalo_l")
FACE_DET_SIZE = (640, 640)

# API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8001"))
API_RELOAD = os.getenv("API_RELOAD", "true").lower() == "true"

# Recognition
DEFAULT_THRESHOLD = float(os.getenv("DEFAULT_THRESHOLD", "0.4"))
MIN_FACE_SIZE = 10000  # pixels
MAX_FACES_ALLOWED = 1

# Liveness - Configuracoes basicas
ENABLE_LIVENESS_CHECK = os.getenv("ENABLE_LIVENESS_CHECK", "true").lower() == "true"
LIVENESS_BLUR_THRESHOLD = float(os.getenv("LIVENESS_BLUR_THRESHOLD", "100.0"))
LIVENESS_BRIGHTNESS_MIN = int(os.getenv("LIVENESS_BRIGHTNESS_MIN", "50"))
LIVENESS_BRIGHTNESS_MAX = int(os.getenv("LIVENESS_BRIGHTNESS_MAX", "200"))

# Liveness - Configuracoes avancadas
LIVENESS_BLINK_ENABLED = os.getenv("LIVENESS_BLINK_ENABLED", "true").lower() == "true"
LIVENESS_BLINK_MIN_COUNT = int(os.getenv("LIVENESS_BLINK_MIN_COUNT", "2"))
LIVENESS_MOTION_ENABLED = os.getenv("LIVENESS_MOTION_ENABLED", "true").lower() == "true"
LIVENESS_MOTION_MIN_FRAMES = int(os.getenv("LIVENESS_MOTION_MIN_FRAMES", "10"))
LIVENESS_TEXTURE_ENABLED = os.getenv("LIVENESS_TEXTURE_ENABLED", "true").lower() == "true"
LIVENESS_CHALLENGE_TIMEOUT_MS = int(os.getenv("LIVENESS_CHALLENGE_TIMEOUT_MS", "10000"))
LIVENESS_MIN_CHALLENGE_TIME_MS = int(os.getenv("LIVENESS_MIN_CHALLENGE_TIME_MS", "500"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# CORS - Lista de origens permitidas
# Em producao, configure com dominios especificos separados por virgula
# Exemplo: CORS_ORIGINS=https://app.exemplo.com,https://admin.exemplo.com
_cors_origins_env = os.getenv("CORS_ORIGINS", "")


def _parse_cors_origins() -> List[str]:
    """
    Parse CORS origins de forma segura.
    Se nao configurado ou vazio, retorna lista vazia (nenhuma origem permitida).
    Se configurado como '*', permite todas (NAO recomendado em producao).
    """
    if not _cors_origins_env:
        return []

    if _cors_origins_env.strip() == "*":
        # Em desenvolvimento, permitir todas as origens
        # Em producao, isso deve ser evitado
        return ["*"]

    # Parsear lista de origens
    origins = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]

    return origins


CORS_ORIGINS = _parse_cors_origins()
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
CORS_ALLOW_METHODS = os.getenv("CORS_ALLOW_METHODS", "GET,POST,PUT,DELETE,OPTIONS").split(",")
CORS_ALLOW_HEADERS = os.getenv("CORS_ALLOW_HEADERS", "Content-Type,Authorization,X-API-Key").split(
    ","
)

# Redis - Para rate limiting distribuido e cache
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_SSL = os.getenv("REDIS_SSL", "false").lower() == "true"

# Cache de embeddings
EMBEDDING_CACHE_ENABLED = os.getenv("EMBEDDING_CACHE_ENABLED", "true").lower() == "true"
EMBEDDING_CACHE_TTL = int(os.getenv("EMBEDDING_CACHE_TTL", "3600"))  # 1 hora

# Metricas e Monitoramento
METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() == "true"
METRICS_PORT = int(os.getenv("METRICS_PORT", "9090"))

# Seguranca
# Tempo maximo para processar uma requisicao (segundos)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
# Tamanho maximo de upload (bytes) - 10MB
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(10 * 1024 * 1024)))


def get_redis_url() -> str:
    """Retorna URL de conexao Redis"""
    if REDIS_PASSWORD:
        return f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    return f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"


def is_production() -> bool:
    """Verifica se esta em modo producao"""
    env = os.getenv("ENVIRONMENT", "development").lower()
    return env in ("production", "prod")


def validate_cors_config():
    """Valida configuracao de CORS e emite warnings se inseguro"""
    import logging

    logger = logging.getLogger(__name__)

    if "*" in CORS_ORIGINS and is_production():
        logger.warning(
            "CORS configurado com '*' em producao! "
            "Configure CORS_ORIGINS com dominios especificos."
        )

    if not CORS_ORIGINS:
        logger.warning(
            "CORS_ORIGINS vazio. Nenhuma origem sera permitida. "
            "Configure CORS_ORIGINS no arquivo .env"
        )
