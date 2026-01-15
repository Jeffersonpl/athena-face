# Configuracao de Tenants - Athena Face

O Athena Face suporta multi-tenancy, permitindo que multiplas organizacoes usem o sistema de forma isolada.

## O que e um Tenant?

Um tenant representa uma organizacao/cliente com:
- Banco de dados isolado
- API Key propria
- Configuracoes personalizadas (threshold, rate limit)
- Dados completamente separados

## Criar um Novo Tenant

### 1. Definir Variaveis de Ambiente

No arquivo `.env`, adicione um bloco para cada tenant:

```bash
# =============================================================================
# TENANT: EMPRESA_ABC
# =============================================================================
TENANT_EMPRESAABC_DB_HOST=localhost
TENANT_EMPRESAABC_DB_PORT=3306
TENANT_EMPRESAABC_DB_NAME=athenaface_empresaabc
TENANT_EMPRESAABC_DB_USER=athenaface_abc
TENANT_EMPRESAABC_DB_PASS=senha_segura_aqui
TENANT_EMPRESAABC_API_KEY=abc_key_xxxxxxxxxxxxx
TENANT_EMPRESAABC_THRESHOLD=0.4
TENANT_EMPRESAABC_RATE_LIMIT=100
TENANT_EMPRESAABC_ACTIVE=true
```

### 2. Gerar API Key Segura

```bash
python scripts/generate_api_keys.py

# Output:
# Nova API Key gerada: abc_7f3d8k9l2m5n6p8q
```

### 3. Criar Banco de Dados

```bash
# Conectar ao MySQL
mysql -u root -p

# Criar banco
CREATE DATABASE athenaface_empresaabc;
CREATE USER 'athenaface_abc'@'%' IDENTIFIED BY 'senha_segura_aqui';
GRANT ALL PRIVILEGES ON athenaface_empresaabc.* TO 'athenaface_abc'@'%';
FLUSH PRIVILEGES;

# Criar tabelas
mysql -u athenaface_abc -p athenaface_empresaabc < migrations/create_tables.sql
```

### 4. Reiniciar Servico

```bash
docker-compose restart athenaface_service
```

### 5. Testar Conexao

```bash
python scripts/test_tenant_connection.py
```

## Estrutura do Banco por Tenant

Cada tenant tem sua propria tabela `face_embeddings`:

```sql
CREATE TABLE face_embeddings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    embedding JSON NOT NULL,
    turnstile_id INT DEFAULT NULL,
    event_id INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user (user_id)
);
```

## Configuracoes por Tenant

| Parametro | Descricao | Default |
|-----------|-----------|---------|
| THRESHOLD | Similaridade minima para match | 0.4 |
| RATE_LIMIT | Requisicoes por minuto | 100 |
| ACTIVE | Tenant ativo/inativo | true |

## Boas Praticas

### Seguranca

1. **API Keys unicas**: Nunca reutilize keys entre tenants
2. **Senhas fortes**: Use senhas de pelo menos 16 caracteres
3. **Usuarios separados**: Cada tenant deve ter seu proprio usuario MySQL
4. **Backups**: Configure backups por tenant

### Performance

1. **Indices**: A tabela ja tem indice em `user_id`
2. **Pool de conexoes**: O sistema gerencia automaticamente
3. **Cache**: Habilite Redis para tenants com muitas faces

### Monitoramento

```bash
# Ver tenants ativos
curl http://localhost:8001/api/tenants

# Health check
curl http://localhost:8001/health
```

## Exemplo: Multiplos Tenants

```bash
# .env com 3 tenants

# Tenant 1: Evento de Musica
TENANT_ROCK_DB_HOST=db1.exemplo.com
TENANT_ROCK_DB_NAME=athena_rock
TENANT_ROCK_API_KEY=rock_xxxx
TENANT_ROCK_RATE_LIMIT=500
TENANT_ROCK_ACTIVE=true

# Tenant 2: Empresa de Seguranca
TENANT_SEGURANCA_DB_HOST=db2.exemplo.com
TENANT_SEGURANCA_DB_NAME=athena_seg
TENANT_SEGURANCA_API_KEY=seg_xxxx
TENANT_SEGURANCA_RATE_LIMIT=1000
TENANT_SEGURANCA_ACTIVE=true

# Tenant 3: Banco (KYC)
TENANT_BANCO_DB_HOST=db3.exemplo.com
TENANT_BANCO_DB_NAME=athena_banco
TENANT_BANCO_API_KEY=banco_xxxx
TENANT_BANCO_THRESHOLD=0.5  # Mais rigoroso
TENANT_BANCO_RATE_LIMIT=200
TENANT_BANCO_ACTIVE=true
```

## Desativar Tenant

Para desativar temporariamente:

```bash
TENANT_EXEMPLO_ACTIVE=false
```

Reinicie o servico para aplicar.

## Suporte

- **Email**: jefferson@jeffersonpl.dev
- **Issues**: https://github.com/Jeffersonpl/athena-face/issues
