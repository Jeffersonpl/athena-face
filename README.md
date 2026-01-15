# Athena Face

**Plataforma Enterprise de Reconhecimento Facial Multi-Tenant**

Sistema de reconhecimento facial de alta performance com liveness detection (anti-spoofing), projetado para controle de acesso, verificacao de identidade (KYC) e autenticacao biometrica.

[![CI](https://github.com/Jeffersonpl/athena-face/actions/workflows/ci.yml/badge.svg)](https://github.com/Jeffersonpl/athena-face/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Features

- **Multi-Tenancy**: Isolamento total de dados por cliente
- **Reconhecimento Facial**: InsightFace buffalo_l (embeddings 512D, 99%+ accuracy)
- **Liveness Detection**: Anti-spoofing com analise de blur, textura, frequencia
- **API RESTful**: FastAPI com documentacao automatica (Swagger/ReDoc)
- **Rate Limiting**: Protecao contra abuso (Redis ou in-memory)
- **Cache de Embeddings**: Performance otimizada para buscas 1:N
- **Docker Ready**: Deploy simplificado com Docker Compose
- **Metricas Prometheus**: Observabilidade completa

---

## Quick Start

### 1. Clonar e Configurar

```bash
git clone https://github.com/Jeffersonpl/athena-face.git
cd athena-face
cp .env.example .env
```

### 2. Iniciar com Docker

```bash
docker-compose up -d
```

### 3. Verificar

```bash
curl http://localhost:8001/health
# {"status": "healthy", "model": "buffalo_l"}
```

### 4. Acessar Interface

```
http://localhost:8001/facial?api_key=demo_api_key_12345&tenant_id=DEMO&user_id=1&mode=register
```

---

## Documentacao

| Documento | Descricao |
|-----------|-----------|
| [Guia de Instalacao](docs/guides/installation.md) | Setup completo |
| [Quick Start](docs/guides/quickstart.md) | Inicio rapido |
| [Arquitetura C4](docs/architecture/c4-overview.md) | Diagramas de arquitetura |
| [Casos de Uso](docs/architecture/use-cases.md) | Exemplos de aplicacao |
| [API Reference](docs/api/reference.md) | Documentacao da API |
| [Configuracao de Tenants](docs/guides/tenants.md) | Multi-tenancy |
| [Liveness Detection](docs/guides/liveness.md) | Anti-spoofing |

---

## Arquitetura

```
                    +------------------+
                    |    Cliente       |
                    | (Web/Mobile/API) |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    |   Athena Face    |
                    |    (FastAPI)     |
                    +--------+---------+
                             |
        +--------------------+--------------------+
        |                    |                    |
+-------v-------+    +-------v-------+    +------v------+
|    Liveness   |    |     Face      |    |    Cache    |
|    Service    |    |   Service     |    |   Service   |
+---------------+    +---------------+    +-------------+
| Anti-spoofing |    | InsightFace   |    | Redis/Mem   |
| Blur/Texture  |    | buffalo_l     |    | Embeddings  |
+---------------+    +-------+-------+    +------+------+
                             |                   |
                    +--------v---------+---------v----+
                    |              MySQL              |
                    |     (Banco por Tenant)         |
                    +--------------------------------+
```

---

## API Endpoints

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/health` | GET | Health check |
| `/api/tenants` | GET | Lista tenants |
| `/api/face/register` | POST | Cadastra face |
| `/api/face/recognize` | POST | Reconhece face (1:N) |
| `/api/face/compare` | POST | Compara faces (1:1) |
| `/facial` | GET | Interface de captura |

### Exemplo: Registrar Face

```bash
curl -X POST http://localhost:8001/api/face/register \
  -H "X-API-Key: sua_api_key" \
  -F "image=@foto.jpg" \
  -F "user_id=123"
```

### Exemplo: Reconhecer Face

```bash
curl -X POST http://localhost:8001/api/face/recognize \
  -H "X-API-Key: sua_api_key" \
  -F "image=@foto.jpg"
```

---

## Casos de Uso

- **Controle de Acesso**: Eventos, predios, areas restritas
- **Verificacao de Identidade (KYC)**: Onboarding bancario, fintech
- **Autenticacao Biometrica**: Login sem senha
- **Registro de Ponto**: Controle de frequencia
- **Anti-Fraude**: Verificacao em atendimento

---

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend | FastAPI (Python 3.11+) |
| ML/AI | InsightFace buffalo_l |
| Database | MySQL 8.0 |
| Cache | Redis / In-Memory |
| Frontend | Vanilla JS + MediaPipe |
| Deploy | Docker + Docker Compose |
| CI/CD | GitHub Actions |

---

## Desenvolvimento

```bash
# Setup local
make dev
make hooks  # Instala pre-commit

# Rodar testes
make test

# Verificar codigo
make check  # lint + typecheck + security

# Formatar codigo
make format
```

---

## Contribuicao

1. Fork o repositorio
2. Crie uma branch (`git checkout -b feat/minha-feature`)
3. Commit suas mudancas (`git commit -m 'feat: adiciona feature'`)
4. Push para a branch (`git push origin feat/minha-feature`)
5. Abra um Pull Request

---

## Licenca

MIT License - veja [LICENSE](LICENSE) para detalhes.

---

## Contato

- **Email**: jefferson@jeffersonpl.dev
- **Issues**: https://github.com/Jeffersonpl/athena-face/issues

---

## Acknowledgments

- [InsightFace](https://github.com/deepinsight/insightface) - Modelo de reconhecimento facial
- [FastAPI](https://fastapi.tiangolo.com/) - Framework web
- [MediaPipe](https://mediapipe.dev/) - Deteccao facial no frontend
