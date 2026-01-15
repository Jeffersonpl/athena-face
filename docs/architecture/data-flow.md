# Fluxo de Dados - Athena Face

Este documento descreve como os dados fluem atraves do sistema.

## Visao Geral

```mermaid
flowchart LR
    subgraph Input
        A[Imagem Facial]
        B[API Key]
        C[User ID]
    end

    subgraph Processing
        D[Validacao]
        E[Liveness Check]
        F[Face Detection]
        G[Embedding Extraction]
    end

    subgraph Storage
        H[(MySQL)]
        I[(Redis Cache)]
    end

    subgraph Output
        J[Resultado JSON]
    end

    A --> D
    B --> D
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    G --> I
    H --> J
    I --> J
```

## Fluxo de Registro

```mermaid
sequenceDiagram
    participant C as Cliente
    participant API as API Gateway
    participant MW as Middleware
    participant LS as Liveness Service
    participant FS as Face Service
    participant DB as MySQL
    participant Cache as Redis

    Note over C,Cache: 1. Recepcao do Request
    C->>API: POST /api/face/register
    API->>MW: Valida Headers

    Note over MW,API: 2. Autenticacao
    MW->>MW: Extrai X-API-Key
    MW->>MW: Busca config do tenant
    MW-->>API: Tenant validado

    Note over LS,API: 3. Validacao de Liveness
    API->>LS: Analisa imagem
    LS->>LS: Check blur
    LS->>LS: Check brightness
    LS->>LS: Check texture
    LS->>LS: Check frequency
    LS-->>API: Score: 0.85 (passed)

    Note over FS,API: 4. Extracao de Embedding
    API->>FS: Processa face
    FS->>FS: Detecta face (RetinaFace)
    FS->>FS: Extrai embedding (ArcFace)
    FS-->>API: embedding[512]

    Note over DB,Cache: 5. Persistencia
    API->>DB: INSERT embedding
    API->>Cache: SET embedding (TTL: 1h)

    Note over C,API: 6. Resposta
    API-->>C: {success: true, user_id: 123}
```

## Fluxo de Reconhecimento

```mermaid
sequenceDiagram
    participant C as Cliente
    participant API as API Gateway
    participant FS as Face Service
    participant Cache as Redis
    participant DB as MySQL

    Note over C,DB: 1. Request e Validacao
    C->>API: POST /api/face/recognize
    API->>API: Valida API Key
    API->>API: Verifica liveness

    Note over FS,API: 2. Extracao de Query Embedding
    API->>FS: Extrai embedding da imagem
    FS-->>API: query_embedding[512]

    Note over Cache,DB: 3. Busca de Embeddings
    API->>Cache: GET embeddings:{tenant_id}
    alt Cache Hit
        Cache-->>API: embeddings[]
    else Cache Miss
        API->>DB: SELECT * FROM face_embeddings
        DB-->>API: embeddings[]
        API->>Cache: SET embeddings (TTL: 1h)
    end

    Note over FS,API: 4. Comparacao
    API->>FS: Compara query vs embeddings
    FS->>FS: Calcula distancia euclidiana
    FS->>FS: Filtra por threshold
    FS-->>API: matches[{user_id, similarity}]

    Note over C,API: 5. Resposta
    API-->>C: {matched: true, user_id: X, similarity: 0.92}
```

## Estrutura de Dados

### Embedding Facial

```json
{
  "id": 1,
  "user_id": 123,
  "embedding": [0.123, -0.456, 0.789, ...],  // 512 floats
  "turnstile_id": 1,
  "event_id": 100,
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-01-15T10:00:00Z"
}
```

### Resultado de Liveness

```json
{
  "passed": true,
  "score": 0.85,
  "details": {
    "blur": {
      "passed": true,
      "variance": 156.3,
      "threshold": 100.0
    },
    "brightness": {
      "passed": true,
      "mean": 128,
      "std": 45,
      "min_threshold": 50,
      "max_threshold": 200
    },
    "color": {
      "passed": true,
      "std": 42.5,
      "saturation_mean": 0.35
    },
    "texture": {
      "passed": true,
      "moire_score": 0.08,
      "threshold": 0.15
    },
    "frequency": {
      "passed": true,
      "energy_ratio": 1.5,
      "threshold": 1.0
    }
  }
}
```

### Request de Registro

```
POST /api/face/register
Content-Type: multipart/form-data

image: <binary>
user_id: 123
turnstile_id: 1 (opcional)
event_id: 100 (opcional)
```

### Response de Registro

```json
{
  "success": true,
  "message": "Face cadastrada com sucesso",
  "data": {
    "user_id": 123,
    "face_quality": 0.92,
    "liveness_score": 0.85,
    "registered_at": "2026-01-15T10:00:00Z"
  }
}
```

## Ciclo de Vida do Cache

```mermaid
stateDiagram-v2
    [*] --> Empty: Inicio
    Empty --> Loading: Cache Miss
    Loading --> Cached: Dados carregados
    Cached --> Stale: TTL expirado
    Stale --> Loading: Nova requisicao
    Cached --> Invalidated: Novo registro
    Invalidated --> Loading: Proxima requisicao
```

### Estrategia de Cache

| Evento | Acao |
|--------|------|
| GET embeddings | Busca cache, fallback para DB |
| POST register | Invalida cache do tenant |
| TTL expira | Remove entrada do cache |

## Isolamento de Dados

```mermaid
flowchart TB
    subgraph Tenant A
        A1[(DB Tenant A)]
        A2[Cache: tenant_a:*]
    end

    subgraph Tenant B
        B1[(DB Tenant B)]
        B2[Cache: tenant_b:*]
    end

    subgraph API
        API1[API Service]
    end

    API1 --> A1
    API1 --> A2
    API1 --> B1
    API1 --> B2

    A1 x--x B1
    A2 x--x B2
```

**Garantias**:
- Cada tenant tem banco separado
- Cache usa prefixo por tenant
- Impossivel cruzar dados entre tenants

## Metricas Coletadas

```mermaid
flowchart LR
    subgraph Requisicoes
        R1[request_count]
        R2[request_latency]
        R3[request_errors]
    end

    subgraph Faces
        F1[faces_registered]
        F2[faces_matched]
        F3[faces_not_matched]
    end

    subgraph Liveness
        L1[liveness_passed]
        L2[liveness_failed]
        L3[liveness_score_histogram]
    end

    subgraph Sistema
        S1[model_load_time]
        S2[cache_hit_rate]
        S3[db_query_time]
    end
```

## Diagrama de Entidade-Relacionamento

```mermaid
erDiagram
    TENANT ||--o{ FACE_EMBEDDING : contains
    TENANT {
        string id PK
        string api_key
        float threshold
        int rate_limit
        boolean active
    }
    FACE_EMBEDDING {
        int id PK
        int user_id UK
        json embedding
        int turnstile_id
        int event_id
        timestamp created_at
        timestamp updated_at
    }
```

## Suporte

- **Email**: jefferson@jeffersonpl.dev
- **Issues**: https://github.com/Jeffersonpl/athena-face/issues
