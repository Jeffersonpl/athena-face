"""
Script para testar conexão com bancos de dados dos tenants
"""
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.tenants import TENANTS_CONFIG
from src.models.database import test_tenant_connection


def test_all_tenants():
    """
    Testa conexão com todos os tenants ativos
    """
    print("=" * 70)
    print("🧪 Teste de Conexão - Tenants Athena Face")
    print("=" * 70)
    print()

    results = []

    for tenant_id, config in TENANTS_CONFIG.items():
        if not config.get("active", False):
            print(f"⏭️  {tenant_id}: INATIVO (pulando)")
            print()
            continue

        print(f"🔍 Testando: {config['name']} ({tenant_id})")
        print(f"   Host: {config['db_host']}:{config['db_port']}")
        print(f"   Database: {config['db_name']}")
        print(f"   User: {config['db_user']}")

        success = test_tenant_connection(config)

        if success:
            print(f"   ✅ CONEXÃO OK")
            results.append({"tenant": tenant_id, "status": "OK"})
        else:
            print(f"   ❌ FALHA NA CONEXÃO")
            results.append({"tenant": tenant_id, "status": "FALHA"})

        print()

    print("=" * 70)
    print("📊 Resumo dos Testes")
    print("=" * 70)
    print()

    total = len(results)
    success_count = sum(1 for r in results if r["status"] == "OK")
    fail_count = total - success_count

    for result in results:
        status_icon = "✅" if result["status"] == "OK" else "❌"
        print(f"{status_icon} {result['tenant']}: {result['status']}")

    print()
    print(f"Total: {total} | ✅ Sucesso: {success_count} | ❌ Falha: {fail_count}")
    print()

    if fail_count > 0:
        print("⚠️  Alguns tenants falharam. Verifique as configurações no .env")
        sys.exit(1)
    else:
        print("✅ Todos os tenants estão conectados!")
        sys.exit(0)


if __name__ == "__main__":
    test_all_tenants()