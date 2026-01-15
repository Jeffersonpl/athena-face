"""
Servico de Cache de Embeddings
Melhora performance do reconhecimento facial cacheando embeddings em memoria ou Redis
"""

import json
import logging
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import datetime, timedelta

from src.config.settings import (
    EMBEDDING_CACHE_ENABLED,
    EMBEDDING_CACHE_TTL,
    REDIS_DB,
    REDIS_ENABLED,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)

logger = logging.getLogger(__name__)


class EmbeddingCache(ABC):
    """Interface para cache de embeddings"""

    @abstractmethod
    def get(self, tenant_id: str, user_id: int) -> list[float] | None:
        """Busca embedding do cache"""
        pass

    @abstractmethod
    def set(self, tenant_id: str, user_id: int, embedding: list[float], ttl: int = None) -> bool:
        """Salva embedding no cache"""
        pass

    @abstractmethod
    def delete(self, tenant_id: str, user_id: int) -> bool:
        """Remove embedding do cache"""
        pass

    @abstractmethod
    def get_all_embeddings(self, tenant_id: str) -> dict[int, list[float]]:
        """Busca todos os embeddings de um tenant"""
        pass

    @abstractmethod
    def invalidate_tenant(self, tenant_id: str) -> int:
        """Invalida todo o cache de um tenant"""
        pass

    @abstractmethod
    def get_stats(self) -> dict:
        """Retorna estatisticas do cache"""
        pass


class InMemoryEmbeddingCache(EmbeddingCache):
    """
    Cache de embeddings em memoria usando LRU.
    Bom para desenvolvimento e instancias unicas.
    """

    def __init__(self, max_size: int = 10000, default_ttl: int = 3600):
        self._cache: OrderedDict = OrderedDict()
        self._expiry: dict[str, datetime] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()

        # Estatisticas
        self._hits = 0
        self._misses = 0

        logger.info(f"Cache em memoria inicializado (max_size={max_size}, ttl={default_ttl}s)")

    def _make_key(self, tenant_id: str, user_id: int) -> str:
        return f"{tenant_id}:user:{user_id}"

    def _is_expired(self, key: str) -> bool:
        if key not in self._expiry:
            return True
        return datetime.now() > self._expiry[key]

    def _evict_if_needed(self):
        """Remove itens mais antigos se cache estiver cheio"""
        while len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            if oldest_key in self._expiry:
                del self._expiry[oldest_key]

    def _cleanup_expired(self):
        """Remove itens expirados"""
        now = datetime.now()
        expired_keys = [key for key, exp_time in self._expiry.items() if exp_time < now]
        for key in expired_keys:
            if key in self._cache:
                del self._cache[key]
            del self._expiry[key]

    def get(self, tenant_id: str, user_id: int) -> list[float] | None:
        key = self._make_key(tenant_id, user_id)

        with self._lock:
            if key not in self._cache or self._is_expired(key):
                self._misses += 1
                return None

            # Move para o fim (LRU)
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]

    def set(self, tenant_id: str, user_id: int, embedding: list[float], ttl: int = None) -> bool:
        key = self._make_key(tenant_id, user_id)
        ttl = ttl or self._default_ttl

        with self._lock:
            self._evict_if_needed()
            self._cache[key] = embedding
            self._expiry[key] = datetime.now() + timedelta(seconds=ttl)
            return True

    def delete(self, tenant_id: str, user_id: int) -> bool:
        key = self._make_key(tenant_id, user_id)

        with self._lock:
            if key in self._cache:
                del self._cache[key]
            if key in self._expiry:
                del self._expiry[key]
            return True

    def get_all_embeddings(self, tenant_id: str) -> dict[int, list[float]]:
        prefix = f"{tenant_id}:user:"
        result = {}

        with self._lock:
            self._cleanup_expired()

            for key, embedding in self._cache.items():
                if key.startswith(prefix):
                    user_id = int(key.replace(prefix, ""))
                    result[user_id] = embedding

        return result

    def invalidate_tenant(self, tenant_id: str) -> int:
        prefix = f"{tenant_id}:"
        count = 0

        with self._lock:
            keys_to_delete = [key for key in self._cache.keys() if key.startswith(prefix)]

            for key in keys_to_delete:
                del self._cache[key]
                if key in self._expiry:
                    del self._expiry[key]
                count += 1

        return count

    def get_stats(self) -> dict:
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        with self._lock:
            self._cleanup_expired()
            current_size = len(self._cache)

        return {
            "type": "memory",
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
            "current_size": current_size,
            "max_size": self._max_size,
        }


class RedisEmbeddingCache(EmbeddingCache):
    """
    Cache de embeddings usando Redis.
    Funciona com multiplas instancias (distribuido).
    """

    def __init__(self, default_ttl: int = 3600):
        self._default_ttl = default_ttl

        try:
            import redis

            self._redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD or None,
                db=REDIS_DB,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            self._redis.ping()
            logger.info(f"Cache Redis conectado em {REDIS_HOST}:{REDIS_PORT}")
        except ImportError:
            logger.error("Pacote 'redis' nao instalado")
            raise
        except Exception as e:
            logger.error(f"Erro ao conectar ao Redis: {e}")
            raise

        # Estatisticas
        self._hits = 0
        self._misses = 0

    def _make_key(self, tenant_id: str, user_id: int) -> str:
        return f"embedding:{tenant_id}:user:{user_id}"

    def get(self, tenant_id: str, user_id: int) -> list[float] | None:
        key = self._make_key(tenant_id, user_id)

        try:
            data = self._redis.get(key)
            if data is None:
                self._misses += 1
                return None

            self._hits += 1
            return json.loads(data)
        except Exception as e:
            logger.error(f"Erro ao buscar do cache Redis: {e}")
            self._misses += 1
            return None

    def set(self, tenant_id: str, user_id: int, embedding: list[float], ttl: int = None) -> bool:
        key = self._make_key(tenant_id, user_id)
        ttl = ttl or self._default_ttl

        try:
            data = json.dumps(embedding)
            self._redis.setex(key, ttl, data)
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar no cache Redis: {e}")
            return False

    def delete(self, tenant_id: str, user_id: int) -> bool:
        key = self._make_key(tenant_id, user_id)

        try:
            self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Erro ao deletar do cache Redis: {e}")
            return False

    def get_all_embeddings(self, tenant_id: str) -> dict[int, list[float]]:
        pattern = f"embedding:{tenant_id}:user:*"
        result = {}

        try:
            cursor = 0
            while True:
                cursor, keys = self._redis.scan(cursor, match=pattern, count=100)

                for key in keys:
                    try:
                        data = self._redis.get(key)
                        if data:
                            user_id = int(key.split(":")[-1])
                            result[user_id] = json.loads(data)
                    except Exception:
                        continue

                if cursor == 0:
                    break

        except Exception as e:
            logger.error(f"Erro ao buscar embeddings do Redis: {e}")

        return result

    def invalidate_tenant(self, tenant_id: str) -> int:
        pattern = f"embedding:{tenant_id}:*"
        count = 0

        try:
            cursor = 0
            while True:
                cursor, keys = self._redis.scan(cursor, match=pattern, count=100)

                if keys:
                    count += self._redis.delete(*keys)

                if cursor == 0:
                    break

        except Exception as e:
            logger.error(f"Erro ao invalidar cache do tenant: {e}")

        return count

    def get_stats(self) -> dict:
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        try:
            info = self._redis.info("memory")
            memory_used = info.get("used_memory_human", "unknown")
        except Exception:
            memory_used = "unknown"

        return {
            "type": "redis",
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
            "memory_used": memory_used,
        }


class NoOpEmbeddingCache(EmbeddingCache):
    """Cache desabilitado - nao faz nada"""

    def get(self, tenant_id: str, user_id: int) -> list[float] | None:
        return None

    def set(self, tenant_id: str, user_id: int, embedding: list[float], ttl: int = None) -> bool:
        return True

    def delete(self, tenant_id: str, user_id: int) -> bool:
        return True

    def get_all_embeddings(self, tenant_id: str) -> dict[int, list[float]]:
        return {}

    def invalidate_tenant(self, tenant_id: str) -> int:
        return 0

    def get_stats(self) -> dict:
        return {"type": "disabled"}


# ==================== Factory ====================

_embedding_cache: EmbeddingCache | None = None


def get_embedding_cache() -> EmbeddingCache:
    """
    Retorna instancia do cache de embeddings.
    Prioridade: Redis > Memoria > Desabilitado
    """
    global _embedding_cache

    if _embedding_cache is None:
        if not EMBEDDING_CACHE_ENABLED:
            logger.info("Cache de embeddings desabilitado")
            _embedding_cache = NoOpEmbeddingCache()
        elif REDIS_ENABLED:
            try:
                _embedding_cache = RedisEmbeddingCache(default_ttl=EMBEDDING_CACHE_TTL)
            except Exception as e:
                logger.warning(f"Fallback para cache em memoria: {e}")
                _embedding_cache = InMemoryEmbeddingCache(default_ttl=EMBEDDING_CACHE_TTL)
        else:
            _embedding_cache = InMemoryEmbeddingCache(default_ttl=EMBEDDING_CACHE_TTL)

    return _embedding_cache


def warm_cache_for_tenant(tenant_id: str, embeddings: dict[int, list[float]]) -> int:
    """
    Pre-popula o cache com embeddings de um tenant.

    Args:
        tenant_id: ID do tenant
        embeddings: Dict de user_id -> embedding

    Returns:
        Numero de embeddings carregados
    """
    cache = get_embedding_cache()
    count = 0

    for user_id, embedding in embeddings.items():
        if cache.set(tenant_id, user_id, embedding):
            count += 1

    logger.info(f"Cache aquecido para tenant {tenant_id}: {count} embeddings")
    return count
