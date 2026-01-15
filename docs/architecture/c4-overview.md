# Arquitetura C4 - Athena Face

O modelo C4 (Context, Containers, Components, Code) oferece uma visao hierarquica da arquitetura do sistema.

## 1. Diagrama de Contexto

Visao de alto nivel mostrando o sistema e suas interacoes externas.

```mermaid
C4Context
    title Sistema Athena Face - Diagrama de Contexto

    Person(user, "Usuario Final", "Pessoa que precisa ser identificada")
    Person(admin, "Administrador", "Gerencia tenants e configuracoes")
    Person(developer, "Desenvolvedor", "Integra sistemas via API")

    System(athena, "Athena Face", "Plataforma de reconhecimento facial com liveness detection")

    System_Ext(clientApp, "Aplicacao Cliente", "App web/mobile que consome a API")
    System_Ext(database, "MySQL", "Banco de dados por tenant")
    System_Ext(redis, "Redis", "Cache e rate limiting")

    Rel(user, athena, "Registra/Verifica face", "HTTPS")
    Rel(admin, athena, "Configura sistema", "HTTPS")
    Rel(developer, athena, "Integra via API", "REST/JSON")
    Rel(clientApp, athena, "Consome API", "HTTPS + API Key")
    Rel(athena, database, "Armazena embeddings", "TCP/3306")
    Rel(athena, redis, "Cache/Rate limit", "TCP/6379")
```

### Descricao dos Atores

| Ator | Descricao | Interacao |
|------|-----------|-----------|
| **Usuario Final** | Pessoa que passa pelo processo de verificacao facial | Captura de face via webcam |
| **Administrador** | Responsavel pela gestao de tenants e API keys | Painel administrativo |
| **Desenvolvedor** | Integra o Athena Face em aplicacoes | API REST |
| **Aplicacao Cliente** | Sistema externo que consome a API | Webhooks, callbacks |

---

## 2. Diagrama de Container

Mostra os principais containers/servicos que compoem o sistema.

```mermaid
C4Container
    title Athena Face - Diagrama de Container

    Person(user, "Usuario", "Acessa via navegador")

    Container_Boundary(athena, "Athena Face") {
        Container(api, "API Service", "FastAPI/Python", "Expoe endpoints REST para reconhecimento facial")
        Container(frontend, "Frontend", "HTML/JS/CSS", "Interface de captura facial com MediaPipe")
        Container(faceService, "Face Service", "Python/InsightFace", "Processamento de embeddings faciais")
        Container(livenessService, "Liveness Service", "Python/OpenCV", "Deteccao anti-spoofing")
        Container(cacheService, "Cache Service", "Python", "Gerencia cache de embeddings")
    }

    ContainerDb(mysql, "MySQL", "Database", "Armazena embeddings e metadados por tenant")
    ContainerDb(redis, "Redis", "Cache", "Rate limiting e cache de sessao")

    Rel(user, frontend, "Acessa", "HTTPS")
    Rel(frontend, api, "Envia imagens", "REST/JSON")
    Rel(api, faceService, "Extrai embeddings", "Internal")
    Rel(api, livenessService, "Valida liveness", "Internal")
    Rel(api, cacheService, "Busca cache", "Internal")
    Rel(faceService, mysql, "Armazena/Busca", "SQL")
    Rel(cacheService, redis, "Cache ops", "Redis Protocol")
    Rel(api, redis, "Rate limit", "Redis Protocol")
```

### Descricao dos Containers

| Container | Tecnologia | Responsabilidade |
|-----------|------------|------------------|
| **API Service** | FastAPI | Roteamento, autenticacao, orquestracao |
| **Frontend** | Vanilla JS + MediaPipe | Captura facial, challenges de liveness |
| **Face Service** | InsightFace (buffalo_l) | Extracao de embeddings 512D |
| **Liveness Service** | OpenCV + NumPy | Analise anti-spoofing |
| **Cache Service** | Redis/In-Memory | Cache de embeddings para performance |
| **MySQL** | MySQL 8.0 | Persistencia por tenant |
| **Redis** | Redis 7 | Cache distribuido e rate limiting |

---

## 3. Diagrama de Componentes

Detalha os componentes internos do API Service.

```mermaid
C4Component
    title Athena Face API - Diagrama de Componentes

    Container_Boundary(api, "API Service") {
        Component(routes, "Routes", "FastAPI Routers", "Define endpoints da API")
        Component(middleware, "Middleware", "Starlette", "Auth, CORS, Rate Limit")
        Component(validators, "Validators", "Pydantic", "Validacao de requests")
        Component(tenantConfig, "Tenant Config", "Python", "Carrega config de tenants")
    }

    Container_Boundary(services, "Services Layer") {
        Component(faceService, "FaceService", "InsightFace", "Processa faces e embeddings")
        Component(livenessService, "LivenessService", "OpenCV", "Detecta spoofing")
        Component(cacheService, "EmbeddingCache", "Redis/Memory", "Cache de embeddings")
        Component(metricsService, "MetricsService", "Prometheus", "Coleta metricas")
    }

    Container_Boundary(infra, "Infrastructure") {
        Component(database, "DatabaseManager", "MySQL Connector", "Pool de conexoes")
        Component(redisClient, "RedisClient", "redis-py", "Cliente Redis")
    }

    Rel(routes, middleware, "Passa por")
    Rel(middleware, validators, "Valida")
    Rel(validators, tenantConfig, "Obtem config")
    Rel(routes, faceService, "Usa")
    Rel(routes, livenessService, "Usa")
    Rel(faceService, cacheService, "Cache")
    Rel(faceService, database, "Persiste")
    Rel(cacheService, redisClient, "Armazena")
    Rel(routes, metricsService, "Registra")
```

### Componentes Principais

#### API Layer
| Componente | Arquivo | Funcao |
|------------|---------|--------|
| Routes | `src/main.py` | Endpoints REST |
| Middleware | `src/middleware/` | Auth, CORS, Rate Limit |
| Validators | Pydantic Models | Validacao de entrada |

#### Services Layer
| Componente | Arquivo | Funcao |
|------------|---------|--------|
| FaceService | `src/services/face_service.py` | Embeddings faciais |
| LivenessService | `src/services/liveness_service.py` | Anti-spoofing |
| EmbeddingCache | `src/services/embedding_cache.py` | Cache |
| MetricsService | `src/services/metrics_service.py` | Prometheus |

---

## 4. Diagrama de Sequencia - Fluxo de Registro

```mermaid
sequenceDiagram
    participant U as Usuario
    participant F as Frontend
    participant A as API
    participant L as LivenessService
    participant FS as FaceService
    participant DB as MySQL
    participant C as Cache

    U->>F: Acessa /facial?mode=register
    F->>F: Inicia MediaPipe
    F->>U: Solicita challenge (virar cabeca)

    loop Liveness Challenges
        U->>F: Executa movimento
        F->>F: Captura frames
    end

    F->>A: POST /api/face/register
    A->>A: Valida API Key
    A->>L: Verifica liveness(frames)
    L->>L: Analisa blur, brilho, textura
    L-->>A: {passed: true, score: 0.85}

    A->>FS: Extrai embedding(image)
    FS->>FS: InsightFace.get()
    FS-->>A: embedding[512]

    A->>DB: INSERT embedding
    DB-->>A: OK

    A->>C: Cache embedding
    C-->>A: OK

    A-->>F: {success: true, user_id: 123}
    F->>U: Exibe sucesso
```

---

## 5. Diagrama de Sequencia - Fluxo de Reconhecimento

```mermaid
sequenceDiagram
    participant U as Usuario
    participant F as Frontend
    participant A as API
    participant L as LivenessService
    participant FS as FaceService
    participant C as Cache
    participant DB as MySQL

    U->>F: Acessa /facial?mode=recognize
    F->>F: Captura face

    F->>A: POST /api/face/recognize
    A->>A: Valida API Key

    A->>L: Verifica liveness
    L-->>A: {passed: true}

    A->>FS: Extrai embedding
    FS-->>A: query_embedding[512]

    A->>C: Busca cache do tenant
    alt Cache hit
        C-->>A: embeddings[]
    else Cache miss
        A->>DB: SELECT embeddings
        DB-->>A: embeddings[]
        A->>C: Popula cache
    end

    A->>FS: Compara(query, embeddings)
    FS->>FS: Calcula distancia euclidiana
    FS-->>A: matches[]

    A-->>F: {matched: true, user_id: 123, similarity: 0.92}
    F->>U: Exibe resultado
```

---

## 6. Diagrama de Deploy

```mermaid
C4Deployment
    title Athena Face - Diagrama de Deploy

    Deployment_Node(docker, "Docker Host", "Docker Compose") {
        Deployment_Node(app, "athenaface_service", "Python 3.11") {
            Container(api, "API", "FastAPI", "Porta 8001")
        }
    }

    Deployment_Node(db, "Database Server", "MySQL 8.0") {
        ContainerDb(mysql, "MySQL", "Porta 3306")
    }

    Deployment_Node(cache, "Cache Server", "Redis 7") {
        ContainerDb(redis, "Redis", "Porta 6379")
    }

    Rel(api, mysql, "TCP/3306")
    Rel(api, redis, "TCP/6379")
```

### Requisitos de Infraestrutura

| Componente | Minimo | Recomendado |
|------------|--------|-------------|
| **CPU** | 2 cores | 4+ cores |
| **RAM** | 4 GB | 8+ GB |
| **Disco** | 20 GB | 50+ GB SSD |
| **GPU** | Opcional | NVIDIA (CUDA) |

---

## 7. Decisoes Arquiteturais

### ADR-001: Modelo InsightFace buffalo_l
- **Contexto**: Necessidade de modelo preciso e rapido
- **Decisao**: Usar buffalo_l (embeddings 512D)
- **Consequencias**: +99% accuracy, ~50ms por face

### ADR-002: Multi-Tenancy via API Key
- **Contexto**: Multiplos clientes isolados
- **Decisao**: Cada tenant tem API Key e banco separado
- **Consequencias**: Isolamento total, configuracao flexivel

### ADR-003: Liveness no Frontend + Backend
- **Contexto**: Prevenir spoofing
- **Decisao**: Challenges no frontend, validacao no backend
- **Consequencias**: UX fluida, seguranca em camadas

### ADR-004: Cache de Embeddings
- **Contexto**: Performance em buscas 1:N
- **Decisao**: Cache em Redis ou memoria
- **Consequencias**: Latencia <100ms para 10k faces
