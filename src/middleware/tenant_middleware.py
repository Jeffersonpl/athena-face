"""
Middleware de autenticacao e identificacao de tenant
Suporta rate limiting em memoria (desenvolvimento) ou Redis (producao)
"""
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader

from src.config.tenants import get_tenant_by_api_key
from src.config.settings import REDIS_ENABLED, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB

logger = logging.getLogger(__name__)

# API Key Header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ==================== Rate Limiter Interface ====================

class RateLimiter(ABC):
    """Interface para rate limiters"""

    @abstractmethod
    def check_and_increment(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        """
        Verifica se o limite foi excedido e incrementa o contador.

        Args:
            key: Identificador unico (tenant_id)
            limit: Limite maximo de requests
            window_seconds: Janela de tempo em segundos

        Returns:
            True se permitido, False se limite excedido
        """
        pass

    @abstractmethod
    def get_remaining(self, key: str, limit: int, window_seconds: int = 60) -> int:
        """Retorna numero de requests restantes"""
        pass


# ==================== In-Memory Rate Limiter ====================

class InMemoryRateLimiter(RateLimiter):
    """
    Rate limiter em memoria.
    Bom para desenvolvimento e instancias unicas.
    NAO funciona com multiplas instancias.
    """

    def __init__(self):
        self._store = defaultdict(list)
        logger.info("Rate limiter em memoria inicializado")

    def check_and_increment(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)

        # Limpar requests antigos
        self._store[key] = [
            ts for ts in self._store[key]
            if ts > window_start
        ]

        # Verificar limite
        if len(self._store[key]) >= limit:
            return False

        # Adicionar novo request
        self._store[key].append(now)
        return True

    def get_remaining(self, key: str, limit: int, window_seconds: int = 60) -> int:
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)

        # Contar requests na janela
        current = len([
            ts for ts in self._store[key]
            if ts > window_start
        ])

        return max(0, limit - current)


# ==================== Redis Rate Limiter ====================

class RedisRateLimiter(RateLimiter):
    """
    Rate limiter usando Redis.
    Funciona com multiplas instancias (distribuido).
    """

    def __init__(self):
        try:
            import redis
            self._redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD or None,
                db=REDIS_DB,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Testar conexao
            self._redis.ping()
            logger.info(f"Rate limiter Redis conectado em {REDIS_HOST}:{REDIS_PORT}")
        except ImportError:
            logger.error("Pacote 'redis' nao instalado. Use: pip install redis")
            raise
        except Exception as e:
            logger.error(f"Erro ao conectar ao Redis: {e}")
            raise

    def check_and_increment(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        redis_key = f"ratelimit:{key}"

        try:
            # Usar pipeline para operacoes atomicas
            pipe = self._redis.pipeline()

            # Incrementar contador
            pipe.incr(redis_key)

            # Definir expiracao se nova chave
            pipe.expire(redis_key, window_seconds)

            results = pipe.execute()
            current_count = results[0]

            return current_count <= limit

        except Exception as e:
            logger.error(f"Erro no rate limit Redis: {e}")
            # Em caso de erro, permitir a requisicao
            return True

    def get_remaining(self, key: str, limit: int, window_seconds: int = 60) -> int:
        redis_key = f"ratelimit:{key}"

        try:
            current = self._redis.get(redis_key)
            if current is None:
                return limit
            return max(0, limit - int(current))
        except Exception:
            return limit


# ==================== Rate Limiter Factory ====================

_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Retorna instancia do rate limiter apropriado.
    Usa Redis se configurado, senao usa em memoria.
    """
    global _rate_limiter

    if _rate_limiter is None:
        if REDIS_ENABLED:
            try:
                _rate_limiter = RedisRateLimiter()
            except Exception as e:
                logger.warning(f"Fallback para rate limiter em memoria: {e}")
                _rate_limiter = InMemoryRateLimiter()
        else:
            _rate_limiter = InMemoryRateLimiter()

    return _rate_limiter


# ==================== Middleware Functions ====================

async def verify_tenant_api_key(request: Request, api_key: Optional[str] = None) -> dict:
    """
    Verifica API Key e identifica tenant

    Args:
        request: FastAPI Request
        api_key: API Key do header

    Returns:
        Dict com tenant_id e config

    Raises:
        HTTPException: Se API Key invalida ou rate limit excedido
    """
    # Permitir endpoints publicos sem autenticacao
    public_paths = ["/", "/health", "/docs", "/openapi.json", "/redoc", "/api/tenants"]

    if request.url.path in public_paths:
        return {"tenant_id": None, "config": None}

    # Permitir arquivos estaticos
    if request.url.path.startswith("/static"):
        return {"tenant_id": None, "config": None}

    # Verificar se API Key foi fornecida
    if not api_key:
        api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key nao fornecida. Adicione header 'X-API-Key'",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # Buscar tenant pela API Key
    tenant_data = get_tenant_by_api_key(api_key)

    if not tenant_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key invalida ou tenant inativo"
        )

    tenant_id = tenant_data["tenant_id"]
    config = tenant_data["config"]

    # Rate limiting
    rate_limit = config.get("rate_limit", 100)
    limiter = get_rate_limiter()

    if not limiter.check_and_increment(tenant_id, rate_limit):
        remaining = limiter.get_remaining(tenant_id, rate_limit)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit excedido. Maximo: {rate_limit} requests/minuto",
            headers={
                "X-RateLimit-Limit": str(rate_limit),
                "X-RateLimit-Remaining": str(remaining),
                "Retry-After": "60"
            }
        )

    # Adicionar ao request state
    request.state.tenant_id = tenant_id
    request.state.tenant_config = config

    return tenant_data


def get_tenant_from_request(request: Request) -> dict:
    """
    Extrai tenant do request state

    Args:
        request: FastAPI Request

    Returns:
        Dict com tenant_id e config
    """
    if not hasattr(request.state, "tenant_id"):
        return {"tenant_id": None, "config": None}

    return {
        "tenant_id": request.state.tenant_id,
        "config": request.state.tenant_config
    }


# ==================== Rate Limit Headers Middleware ====================

async def add_rate_limit_headers(request: Request, call_next):
    """
    Middleware para adicionar headers de rate limit nas respostas.
    """
    response = await call_next(request)

    # Adicionar headers se tenant autenticado
    if hasattr(request.state, "tenant_id") and request.state.tenant_id:
        tenant_id = request.state.tenant_id
        config = request.state.tenant_config
        rate_limit = config.get("rate_limit", 100)

        limiter = get_rate_limiter()
        remaining = limiter.get_remaining(tenant_id, rate_limit)

        response.headers["X-RateLimit-Limit"] = str(rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

    return response
