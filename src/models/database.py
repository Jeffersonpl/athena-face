"""
Gerenciador de conexões MySQL por tenant
"""
import mysql.connector
from mysql.connector import pooling
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Pool de conexões por tenant
connection_pools: Dict[str, pooling.MySQLConnectionPool] = {}


def get_tenant_db_pool(tenant_config: dict) -> pooling.MySQLConnectionPool:
    """
    Obtém pool de conexões para o tenant

    Args:
        tenant_config: Configuração do tenant

    Returns:
        Pool de conexões MySQL
    """
    tenant_id = tenant_config.get("db_name", "default")

    # Se pool já existe, retornar
    if tenant_id in connection_pools:
        return connection_pools[tenant_id]

    # Criar novo pool
    try:
        pool = pooling.MySQLConnectionPool(
            pool_name=f"pool_{tenant_id}",
            pool_size=5,
            host=tenant_config["db_host"],
            port=tenant_config["db_port"],
            database=tenant_config["db_name"],
            user=tenant_config["db_user"],
            password=tenant_config["db_pass"],
            autocommit=False
        )

        connection_pools[tenant_id] = pool
        logger.info(f"✅ Pool de conexões criado para tenant: {tenant_id}")

        return pool

    except Exception as e:
        logger.error(f"❌ Erro ao criar pool para {tenant_id}: {e}")
        raise


def get_tenant_db_connection(tenant_config: dict):
    """
    Obtém conexão do pool do tenant

    Args:
        tenant_config: Configuração do tenant

    Returns:
        Conexão MySQL
    """
    pool = get_tenant_db_pool(tenant_config)
    return pool.get_connection()


def close_all_pools():
    """
    Fecha todos os pools de conexão
    """
    for tenant_id, pool in connection_pools.items():
        try:
            # Pools não têm método close direto, apenas as conexões
            logger.info(f"Pool {tenant_id} será limpo automaticamente")
        except Exception as e:
            logger.error(f"Erro ao fechar pool {tenant_id}: {e}")

    connection_pools.clear()


def test_tenant_connection(tenant_config: dict) -> bool:
    """
    Testa conexão com banco do tenant

    Args:
        tenant_config: Configuração do tenant

    Returns:
        True se conexão OK, False caso contrário
    """
    try:
        conn = get_tenant_db_connection(tenant_config)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao testar conexão: {e}")
        return False
