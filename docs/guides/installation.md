# Guia de Instalacao - Athena Face

Este guia cobre todas as opcoes de instalacao do Athena Face.

## Requisitos do Sistema

### Hardware Minimo
| Componente | Minimo | Recomendado |
|------------|--------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Disco | 20 GB | 50 GB SSD |
| GPU | - | NVIDIA CUDA |

### Software
- Docker 24.0+
- Docker Compose 2.0+
- Python 3.11+ (para dev local)
- Git

---

## Opcao 1: Docker Compose (Recomendado)

### 1.1 Clonar Repositorio

```bash
git clone https://github.com/Jeffersonpl/athena-face.git
cd athena-face
```

### 1.2 Configurar Ambiente

```bash
# Copiar arquivo de exemplo
cp .env.example .env

# Editar configuracoes
nano .env
```

### 1.3 Configuracao Minima (.env)

```bash
# =============================================================================
# CONFIGURACOES BASICAS
# =============================================================================
API_HOST=0.0.0.0
API_PORT=8001
LOG_LEVEL=INFO

# =============================================================================
# MODELO
# =============================================================================
FACE_MODEL_NAME=buffalo_l
DEFAULT_THRESHOLD=0.4

# =============================================================================
# LIVENESS
# =============================================================================
ENABLE_LIVENESS_CHECK=true

# =============================================================================
# CORS (ajuste para seu dominio)
# =============================================================================
CORS_ORIGINS=http://localhost:3000,http://localhost:8001

# =============================================================================
# TENANT EXEMPLO
# =============================================================================
TENANT_DEMO_DB_HOST=mysql
TENANT_DEMO_DB_PORT=3306
TENANT_DEMO_DB_NAME=athenaface_demo
TENANT_DEMO_DB_USER=athenaface
TENANT_DEMO_DB_PASS=sua_senha_segura
TENANT_DEMO_API_KEY=demo_api_key_12345
TENANT_DEMO_THRESHOLD=0.4
TENANT_DEMO_RATE_LIMIT=100
TENANT_DEMO_ACTIVE=true
```

### 1.4 Iniciar com Docker Compose

```bash
# Subir todos os servicos
docker-compose up -d

# Verificar status
docker-compose ps

# Ver logs
docker-compose logs -f athenaface_service
```

### 1.5 Verificar Instalacao

```bash
# Health check
curl http://localhost:8001/health

# Resposta esperada:
# {"status":"healthy","model":"buffalo_l","tenants_active":1}
```

---

## Opcao 2: Docker Compose com Banco Local

Para desenvolvimento com MySQL e Redis locais:

### 2.1 Criar docker-compose.override.yml

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
```

### 2.2 Conteudo do Override

```yaml
services:
  athenaface_service:
    environment:
      - API_RELOAD=true
      - LOG_LEVEL=DEBUG
    volumes:
      - ./src:/app/src:ro

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root_password
      MYSQL_DATABASE: athenaface_demo
      MYSQL_USER: athenaface
      MYSQL_PASSWORD: sua_senha_segura
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./migrations:/docker-entrypoint-initdb.d:ro

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  mysql_data:
```

### 2.3 Atualizar .env

```bash
# Apontar para containers locais
TENANT_DEMO_DB_HOST=mysql
REDIS_ENABLED=true
REDIS_HOST=redis
```

### 2.4 Iniciar

```bash
docker-compose up -d
```

---

## Opcao 3: Desenvolvimento Local (Python)

### 3.1 Criar Ambiente Virtual

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate   # Windows
```

### 3.2 Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 3.3 Baixar Modelos

```bash
python scripts/download_models.py
```

### 3.4 Configurar Banco de Dados

```bash
# Criar banco MySQL
mysql -u root -p < migrations/create_tables.sql

# Ou usar Docker apenas para MySQL
docker run -d \
  --name athena-mysql \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=athenaface \
  -p 3306:3306 \
  mysql:8.0
```

### 3.5 Iniciar Servico

```bash
# Desenvolvimento (com reload)
uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload

# Producao
uvicorn src.main:app --host 0.0.0.0 --port 8001 --workers 4
```

---

## Opcao 4: Kubernetes

### 4.1 Pre-requisitos
- Cluster Kubernetes (GKE, EKS, AKS, ou local)
- kubectl configurado
- Helm 3.x

### 4.2 Criar Namespace

```bash
kubectl create namespace athenaface
```

### 4.3 Criar Secrets

```bash
kubectl create secret generic athenaface-secrets \
  --namespace athenaface \
  --from-literal=db-password=sua_senha \
  --from-literal=redis-password=redis_senha \
  --from-literal=api-key=sua_api_key
```

### 4.4 Deploy com Manifests

```bash
kubectl apply -f infrastructure/kubernetes/ -n athenaface
```

### 4.5 Verificar Deploy

```bash
kubectl get pods -n athenaface
kubectl get svc -n athenaface
```

---

## Pos-Instalacao

### Gerar API Key

```bash
python scripts/generate_api_keys.py
```

### Testar Conexao

```bash
python scripts/test_tenant_connection.py
```

### Acessar Interface

- **API Docs**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc
- **Frontend**: http://localhost:8001/facial

---

## Troubleshooting

### Modelo nao carrega

```bash
# Verificar se modelo foi baixado
ls ~/.insightface/models/buffalo_l/

# Re-baixar modelo
python scripts/download_models.py
```

### Erro de conexao MySQL

```bash
# Verificar se MySQL esta rodando
docker-compose ps mysql

# Testar conexao
mysql -h localhost -P 3306 -u athenaface -p
```

### Erro de memoria (OOM)

```bash
# Aumentar limite de memoria do Docker
# No docker-compose.yml:
services:
  athenaface_service:
    deploy:
      resources:
        limits:
          memory: 4G
```

### Liveness sempre falha

```bash
# Verificar configuracoes
grep LIVENESS .env

# Ajustar thresholds se necessario
LIVENESS_BLUR_THRESHOLD=50.0  # Diminuir para aceitar mais blur
```

---

## Proximos Passos

1. [Configurar Tenants](tenants.md)
2. [Configurar Liveness](liveness.md)
3. [Integrar via API](../api/reference.md)

---

## Suporte

- **Email**: jefferson@jeffersonpl.dev
- **Issues**: https://github.com/Jeffersonpl/athena-face/issues
