"""
Configuracao Multi-Tenant
Cada tenant tem seu proprio banco de dados e API key

IMPORTANTE: Todas as credenciais devem vir de variaveis de ambiente!
Nunca commitar credenciais no codigo.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Valores padrao seguros (sem credenciais reais)
_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = "3306"
_DEFAULT_USER = "app_user"
_DEFAULT_PASS = ""  # Vazio por padrao - deve ser configurado via env
_DEFAULT_API_KEY = ""  # Vazio por padrao - deve ser gerado
_DEFAULT_THRESHOLD = "0.4"
_DEFAULT_RATE_LIMIT = "100"


def _load_tenant_from_env(prefix: str, name: str) -> dict | None:
    """
    Carrega configuracao de um tenant a partir de variaveis de ambiente.

    Args:
        prefix: Prefixo das variaveis (ex: TENANT_IG)
        name: Nome do tenant

    Returns:
        Dict com configuracao ou None se incompleto
    """
    # Verificar se as variaveis obrigatorias existem
    api_key = os.getenv(f"{prefix}_API_KEY", "")
    db_pass = os.getenv(f"{prefix}_DB_PASS", "")

    # Se nao tem API key configurada, tenant nao esta ativo
    if not api_key:
        return None

    config = {
        "name": name,
        "db_host": os.getenv(f"{prefix}_DB_HOST", _DEFAULT_HOST),
        "db_port": int(os.getenv(f"{prefix}_DB_PORT", _DEFAULT_PORT)),
        "db_name": os.getenv(f"{prefix}_DB_NAME", ""),
        "db_user": os.getenv(f"{prefix}_DB_USER", _DEFAULT_USER),
        "db_pass": db_pass,
        "api_key": api_key,
        "threshold": float(os.getenv(f"{prefix}_THRESHOLD", _DEFAULT_THRESHOLD)),
        "rate_limit": int(os.getenv(f"{prefix}_RATE_LIMIT", _DEFAULT_RATE_LIMIT)),
        "active": os.getenv(f"{prefix}_ACTIVE", "true").lower() == "true",
    }

    # Validar configuracao minima
    if not config["db_name"]:
        logger.warning(f"Tenant {name}: DB_NAME nao configurado")
        return None

    return config


def _build_tenants_config() -> dict[str, dict]:
    """
    Constroi a configuracao de todos os tenants a partir das variaveis de ambiente.

    Returns:
        Dict com todas as configuracoes de tenants
    """
    tenants = {}

    # Tenant 1: Ingresso Global
    ig_config = _load_tenant_from_env("TENANT_IG", "Ingresso Global")
    if ig_config:
        tenants["ingressoglobal"] = ig_config

    # Tenant 2: Synorix
    sv_config = _load_tenant_from_env("TENANT_SV", "Synorix")
    if sv_config:
        tenants["synorix"] = sv_config

    # Carregar tenants dinamicos (TENANT_01, TENANT_02, etc.)
    for i in range(1, 100):
        prefix = f"TENANT_{i:02d}"
        name = os.getenv(f"{prefix}_NAME", f"Tenant {i}")
        config = _load_tenant_from_env(prefix, name)
        if config:
            tenant_id = os.getenv(f"{prefix}_ID", f"tenant_{i}").lower()
            tenants[tenant_id] = config

    return tenants


# Carregar configuracao na inicializacao
TENANTS_CONFIG = _build_tenants_config()


def reload_tenants_config():
    """
    Recarrega a configuracao dos tenants.
    Util para recarregar apos mudancas em variaveis de ambiente.
    """
    global TENANTS_CONFIG
    TENANTS_CONFIG = _build_tenants_config()
    logger.info(f"Configuracao de tenants recarregada: {len(TENANTS_CONFIG)} tenants")


def get_tenant_config(tenant_id: str) -> dict | None:
    """
    Retorna configuracao do tenant

    Args:
        tenant_id: ID do tenant

    Returns:
        Dict com configuracao ou None se nao encontrado
    """
    config = TENANTS_CONFIG.get(tenant_id)

    if not config:
        return None

    if not config.get("active", False):
        return None

    return config


def get_tenant_by_api_key(api_key: str) -> dict | None:
    """
    Busca tenant pela API Key

    Args:
        api_key: API Key do header

    Returns:
        Dict com tenant_id e config ou None
    """
    if not api_key:
        return None

    for tenant_id, config in TENANTS_CONFIG.items():
        if config.get("api_key") == api_key and config.get("active", False):
            return {"tenant_id": tenant_id, "config": config}

    return None


def list_active_tenants() -> dict[str, str]:
    """
    Lista todos os tenants ativos

    Returns:
        Dict com tenant_id e nome
    """
    return {
        tenant_id: config["name"]
        for tenant_id, config in TENANTS_CONFIG.items()
        if config.get("active", False)
    }


def validate_tenant_config(tenant_id: str) -> dict:
    """
    Valida a configuracao de um tenant e retorna status detalhado.

    Args:
        tenant_id: ID do tenant

    Returns:
        Dict com status da validacao
    """
    config = TENANTS_CONFIG.get(tenant_id)

    if not config:
        return {"valid": False, "errors": ["Tenant nao encontrado"]}

    errors = []
    warnings = []

    # Verificar campos obrigatorios
    if not config.get("db_host"):
        errors.append("DB_HOST nao configurado")
    if not config.get("db_name"):
        errors.append("DB_NAME nao configurado")
    if not config.get("db_pass"):
        warnings.append("DB_PASS vazio - verifique se e intencional")
    if not config.get("api_key"):
        errors.append("API_KEY nao configurada")

    # Verificar threshold
    threshold = config.get("threshold", 0.4)
    if threshold < 0.1 or threshold > 1.0:
        warnings.append(f"Threshold ({threshold}) fora do range recomendado (0.1-1.0)")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "config_summary": {
            "db_host": config.get("db_host"),
            "db_name": config.get("db_name"),
            "threshold": config.get("threshold"),
            "rate_limit": config.get("rate_limit"),
            "active": config.get("active"),
        },
    }
