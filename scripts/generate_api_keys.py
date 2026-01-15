"""
Script para gerar API Keys únicas para tenants
"""
import secrets
import string
from datetime import datetime


def generate_api_key(prefix: str, length: int = 32) -> str:
    """
    Gera API Key segura

    Args:
        prefix: Prefixo da key (ex: 'ig_prod', 'sv_prod')
        length: Tamanho da parte aleatória

    Returns:
        API Key no formato: prefix_randomstring
    """
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(length))

    return f"{prefix}_{random_part}"


def generate_tenant_keys():
    """
    Gera API Keys para todos os tenants
    """
    tenants = [
        {"id": "ingressoglobal", "prefix": "ig_prod"},
        {"id": "synorix", "prefix": "sv_prod"},
    ]

    print("=" * 70)
    print("🔑 Gerador de API Keys - Athena Face")
    print("=" * 70)
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print("⚠️  ATENÇÃO: Guarde estas chaves em local seguro!")
    print("⚠️  Não commite estas chaves no Git!")
    print()
    print("=" * 70)
    print()

    for tenant in tenants:
        api_key = generate_api_key(tenant["prefix"])

        print(f"Tenant: {tenant['id']}")
        print(f"API Key: {api_key}")
        print()
        print(f"# Adicione ao .env:")
        print(f"TENANT_{tenant['prefix'].upper()}_API_KEY={api_key}")
        print()
        print("-" * 70)
        print()

    print("=" * 70)
    print("✅ API Keys geradas com sucesso!")
    print("=" * 70)
    print()
    print("📋 Próximos passos:")
    print("1. Copie as API Keys geradas acima")
    print("2. Adicione ao arquivo .env")
    print("3. Reinicie o serviço: docker-compose restart")
    print("4. Envie as API Keys para os respectivos clientes (via canal seguro)")
    print()


if __name__ == "__main__":
    generate_tenant_keys()