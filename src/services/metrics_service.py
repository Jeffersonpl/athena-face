"""
Servico de Metricas e Monitoramento
Fornece metricas Prometheus e endpoints de health check
"""
import logging
import time
from datetime import datetime
from functools import wraps
from typing import Callable, Dict, Optional
from collections import defaultdict

from src.config.settings import METRICS_ENABLED

logger = logging.getLogger(__name__)


# ==================== Metricas Internas ====================

class MetricsCollector:
    """
    Coletor de metricas interno.
    Pode ser exportado para Prometheus ou acessado via API.
    """

    def __init__(self):
        self._counters: Dict[str, int] = defaultdict(int)
        self._histograms: Dict[str, list] = defaultdict(list)
        self._gauges: Dict[str, float] = {}
        self._start_time = datetime.now()

        # Limitar historico de histogramas
        self._max_histogram_size = 1000

    def increment_counter(self, name: str, value: int = 1, labels: Dict = None):
        """Incrementa um contador"""
        key = self._make_key(name, labels)
        self._counters[key] += value

    def observe_histogram(self, name: str, value: float, labels: Dict = None):
        """Adiciona observacao a um histograma"""
        key = self._make_key(name, labels)
        self._histograms[key].append(value)

        # Limitar tamanho
        if len(self._histograms[key]) > self._max_histogram_size:
            self._histograms[key] = self._histograms[key][-self._max_histogram_size:]

    def set_gauge(self, name: str, value: float, labels: Dict = None):
        """Define valor de um gauge"""
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def _make_key(self, name: str, labels: Dict = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_counter(self, name: str, labels: Dict = None) -> int:
        key = self._make_key(name, labels)
        return self._counters.get(key, 0)

    def get_histogram_stats(self, name: str, labels: Dict = None) -> Dict:
        key = self._make_key(name, labels)
        values = self._histograms.get(key, [])

        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0}

        sorted_values = sorted(values)
        count = len(values)

        return {
            "count": count,
            "sum": sum(values),
            "avg": sum(values) / count,
            "min": min(values),
            "max": max(values),
            "p50": sorted_values[int(count * 0.5)],
            "p95": sorted_values[int(count * 0.95)] if count >= 20 else sorted_values[-1],
            "p99": sorted_values[int(count * 0.99)] if count >= 100 else sorted_values[-1]
        }

    def get_all_metrics(self) -> Dict:
        """Retorna todas as metricas"""
        return {
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                name: self.get_histogram_stats(name)
                for name in set(self._histograms.keys())
            }
        }


# Instancia global
metrics = MetricsCollector()


# ==================== Decorators ====================

def track_request_time(name: str = "request_duration_seconds"):
    """
    Decorator para rastrear tempo de execucao de requests.

    Usage:
        @track_request_time("face_register_duration")
        async def register_face(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not METRICS_ENABLED:
                return await func(*args, **kwargs)

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                metrics.increment_counter(f"{name}_total", labels={"status": "success"})
                return result
            except Exception as e:
                metrics.increment_counter(f"{name}_total", labels={"status": "error"})
                raise
            finally:
                duration = time.time() - start_time
                metrics.observe_histogram(name, duration)

        return wrapper
    return decorator


def count_calls(name: str):
    """
    Decorator para contar chamadas de funcao.

    Usage:
        @count_calls("liveness_checks")
        def check_liveness(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if METRICS_ENABLED:
                metrics.increment_counter(f"{name}_total")
            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if METRICS_ENABLED:
                metrics.increment_counter(f"{name}_total")
            return await func(*args, **kwargs)

        if hasattr(func, '__await__'):
            return async_wrapper
        return wrapper
    return decorator


# ==================== Metricas Especificas ====================

def record_face_registration(tenant_id: str, success: bool, duration_ms: float):
    """Registra metrica de cadastro de face"""
    if not METRICS_ENABLED:
        return

    status = "success" if success else "failure"
    metrics.increment_counter("face_registrations_total", labels={"tenant": tenant_id, "status": status})
    metrics.observe_histogram("face_registration_duration_ms", duration_ms, labels={"tenant": tenant_id})


def record_face_recognition(tenant_id: str, granted: bool, duration_ms: float, confidence: float):
    """Registra metrica de reconhecimento facial"""
    if not METRICS_ENABLED:
        return

    status = "granted" if granted else "denied"
    metrics.increment_counter("face_recognitions_total", labels={"tenant": tenant_id, "status": status})
    metrics.observe_histogram("face_recognition_duration_ms", duration_ms, labels={"tenant": tenant_id})
    metrics.observe_histogram("face_recognition_confidence", confidence, labels={"tenant": tenant_id})


def record_liveness_check(tenant_id: str, passed: bool, score: float):
    """Registra metrica de verificacao de liveness"""
    if not METRICS_ENABLED:
        return

    status = "passed" if passed else "failed"
    metrics.increment_counter("liveness_checks_total", labels={"tenant": tenant_id, "status": status})
    metrics.observe_histogram("liveness_scores", score, labels={"tenant": tenant_id})


def record_api_error(tenant_id: str, endpoint: str, error_type: str):
    """Registra erro de API"""
    if not METRICS_ENABLED:
        return

    metrics.increment_counter("api_errors_total", labels={
        "tenant": tenant_id or "unknown",
        "endpoint": endpoint,
        "error_type": error_type
    })


def set_active_connections(count: int):
    """Define numero de conexoes ativas"""
    if not METRICS_ENABLED:
        return

    metrics.set_gauge("active_connections", count)


def set_model_status(loaded: bool):
    """Define status do modelo"""
    if not METRICS_ENABLED:
        return

    metrics.set_gauge("model_loaded", 1.0 if loaded else 0.0)


# ==================== Prometheus Export ====================

def get_prometheus_metrics() -> str:
    """
    Gera metricas no formato Prometheus.

    Returns:
        String com metricas no formato Prometheus
    """
    if not METRICS_ENABLED:
        return "# Metrics disabled\n"

    lines = []
    all_metrics = metrics.get_all_metrics()

    # Uptime
    lines.append(f"# HELP athenaface_uptime_seconds Tempo desde o inicio do servico")
    lines.append(f"# TYPE athenaface_uptime_seconds gauge")
    lines.append(f"athenaface_uptime_seconds {all_metrics['uptime_seconds']:.2f}")
    lines.append("")

    # Counters
    for name, value in all_metrics['counters'].items():
        clean_name = name.replace("{", "_").replace("}", "").replace(",", "_").replace("=", "_")
        lines.append(f"# TYPE athenaface_{clean_name} counter")
        lines.append(f"athenaface_{clean_name} {value}")

    lines.append("")

    # Gauges
    for name, value in all_metrics['gauges'].items():
        clean_name = name.replace("{", "_").replace("}", "").replace(",", "_").replace("=", "_")
        lines.append(f"# TYPE athenaface_{clean_name} gauge")
        lines.append(f"athenaface_{clean_name} {value}")

    lines.append("")

    # Histograms (simplificado)
    for name, stats in all_metrics['histograms'].items():
        clean_name = name.replace("{", "_").replace("}", "").replace(",", "_").replace("=", "_")
        lines.append(f"# TYPE athenaface_{clean_name} summary")
        lines.append(f"athenaface_{clean_name}_count {stats['count']}")
        lines.append(f"athenaface_{clean_name}_sum {stats['sum']:.4f}")
        if stats['count'] > 0:
            lines.append(f'athenaface_{clean_name}{{quantile="0.5"}} {stats["p50"]:.4f}')
            lines.append(f'athenaface_{clean_name}{{quantile="0.95"}} {stats["p95"]:.4f}')
            lines.append(f'athenaface_{clean_name}{{quantile="0.99"}} {stats["p99"]:.4f}')

    return "\n".join(lines)


# ==================== Health Check ====================

def get_health_status() -> Dict:
    """
    Retorna status de saude do servico.
    Util para health checks do Kubernetes/Docker.
    """
    from src.services.face_service import FaceService
    from src.middleware.tenant_middleware import get_rate_limiter
    from src.services.embedding_cache import get_embedding_cache

    face_service = FaceService()
    rate_limiter = get_rate_limiter()
    cache = get_embedding_cache()

    checks = {
        "model": {
            "status": "healthy" if face_service.is_ready() else "unhealthy",
            "message": "Model loaded" if face_service.is_ready() else "Model not loaded"
        },
        "cache": {
            "status": "healthy",
            "stats": cache.get_stats()
        }
    }

    # Status geral
    all_healthy = all(c["status"] == "healthy" for c in checks.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "checks": checks
    }
