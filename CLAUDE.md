# Athena Face - Sistema de Verificacao Facial Multi-Tenant

## Visao Geral

Sistema de verificacao facial com deteccao de liveness (anti-spoofing) para validar se uma face e real e nao uma imagem/video falso. Utilizado para controle de acesso em eventos e sistemas.

**Renomeado de FaceSynorix para Athena Face em Janeiro/2026.**

## Stack Tecnologico

- **Backend**: FastAPI (Python 3.10+), uvicorn, Pydantic
- **AI/ML**: InsightFace (buffalo_l model), OpenCV, MediaPipe
- **Database**: MySQL (isolamento por tenant)
- **Cache**: Redis (opcional) ou em memoria
- **Frontend**: Vanilla JavaScript, Canvas API, MediaPipe Face Detection
- **Deploy**: Docker & Docker Compose
- **Metricas**: Prometheus (opcional)

## Estrutura do Projeto

```
AthenaFace/
├── src/
│   ├── main.py                    # FastAPI app, rotas principais (v1.1.0)
│   ├── __init__.py                # Versao do pacote
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # Configuracoes globais
│   │   └── tenants.py             # Definicoes de tenants (via env vars)
│   ├── middleware/
│   │   ├── __init__.py            # CORRIGIDO (era __init).py)
│   │   └── tenant_middleware.py   # Auth, rate limiting (Redis/memoria)
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py            # Connection pooling MySQL
│   ├── services/
│   │   ├── __init__.py
│   │   ├── face_service.py        # Extracao de embeddings (InsightFace)
│   │   ├── liveness_service.py    # Deteccao anti-spoofing AVANCADA
│   │   ├── embedding_cache.py     # Cache de embeddings (Redis/memoria)
│   │   └── metrics_service.py     # Metricas Prometheus (athenaface_*)
│   └── utils/
│       ├── __init__.py            # CORRIGIDO (era __init_.py)
│       └── image_utils.py         # Processamento de imagens
├── frontend/
│   ├── index.html                 # UI principal (Athena Face)
│   ├── test.html                  # Pagina de teste
│   ├── css/app.css                # Estilos
│   └── js/
│       ├── app.js                 # Logica principal (CORRIGIDO: AthenaFaceAPI)
│       ├── api.js                 # AthenaFaceAPI com validacao de inputs
│       └── mediapipe.js           # Wrapper MediaPipe
├── migrations/
│   ├── create_tables.sql          # Schema do banco
│   └── seed_data.sql              # Dados iniciais
├── scripts/
│   ├── download_models.py         # Download modelos InsightFace
│   ├── generate_api_keys.py       # Geracao de API keys
│   └── test_tenant_connection.py  # Teste de conexao
├── tests/
│   ├── test_api.py                # Testes da API (v1.1.0)
│   └── test_liveness_service.py   # Testes do liveness
├── Dockerfile
├── docker-compose.yml             # Container: athenaface_service
├── requirements.txt
├── .env.example                   # Template de configuracao
├── .env                           # Configuracoes (NAO COMMITAR!)
└── CLAUDE.md                      # Esta documentacao
```

## Historico de Mudancas

### v1.1.1 - Correcoes de Seguranca (Janeiro/2026)

**Bugs Corrigidos:**
- `src/middleware/__init).py` -> `__init__.py` (nome incorreto)
- `src/utils/__init_.py` -> `__init__.py` (nome incorreto)
- `frontend/js/app.js:99` - `Athena FaceAPI` -> `AthenaFaceAPI` (erro de sintaxe)

**Seguranca - main.py:**
- Context manager para conexoes de banco (evita leaks)
- Validacao de user_id (gt=0, le=2147483647)
- Validacao de tipo MIME de imagens
- Erros genericos em producao (sem expor stack traces)
- Hash de identificadores em logs (privacidade)
- INSERT ON DUPLICATE KEY UPDATE (evita race condition)
- Validacao de threshold > 0 (evita divisao por zero)
- Try/catch para embeddings invalidos no recognize

**Seguranca - api.js:**
- PostMessage com origin especifico (nao mais '*')
- Validacao de callback URL (HTTPS em producao)
- Sanitizacao de inputs (URL, string, email, user_id)
- Validacao de modo (register/recognize)

**Melhorias - main.py:**
- Docs desabilitados em producao (seguranca)
- Health check com verificacao de tenants
- CORS mais restritivo (credentials=False se origins='*')
- Limite de 10000 faces na query de reconhecimento
- Versao atualizada para 1.1.0

**Testes Atualizados:**
- Testes para versao 1.1.0
- Novos testes de validacao (user_id invalido)
- Testes de seguranca (dados sensiveis)

### v1.1.0 - Renomeacao para Athena Face (Janeiro/2026)

**Arquivos atualizados:**
- Backend: main.py, __init__.py, settings.py, metrics_service.py
- Frontend: index.html, app.js, api.js, test.html
- Config: docker-compose.yml, .env, .env.example
- Scripts: generate_api_keys.py, test_tenant_connection.py, download_models.py
- Tests: test_api.py
- Migrations: create_tables.sql

**Identificadores atualizados:**
- Servico: `athenaface` (antes: facesynorix)
- Container Docker: `athenaface_service`
- Volume Docker: `athenaface_models`
- Network Docker: `athenaface_network`
- Metricas Prometheus: `athenaface_*`
- PostMessage: `ATHENAFACE_RESULT`, `ATHENAFACE_CLOSE`
- LocalStorage: `athenaface_last_result`

**Compatibilidade mantida:**
- `FaceSynorixAPI` como alias para `AthenaFaceAPI`
- `window.FaceSynorixAPI` disponivel

### v1.0.0 - Implementacao Inicial

**Seguranca:**
- Credenciais removidas do codigo (via env vars)
- .env.example criado
- CORS restritivo configuravel
- Rate limiting com Redis
- Headers de rate limit

**Liveness Detection Avancado:**
- Deteccao de Blur (Laplacian)
- Analise de Brilho/Contraste
- Distribuicao de Cores (HSV)
- Deteccao de Textura/Moire (FFT)
- Analise de Frequencia
- Eye Aspect Ratio (EAR)
- Analise de Movimento

**Frontend:**
- Challenges aleatorios (pool de 7)
- Validacao de tempo minimo
- Deteccao de face estatica
- Timeout de challenge

**Performance:**
- Cache de embeddings (Redis/memoria)
- LRU Cache com eviction
- Warm-up de cache

**Monitoramento:**
- Metricas Prometheus
- Health check detalhado
- Tracking de requisicoes

## Endpoints da API

| Endpoint | Metodo | Auth | Descricao |
|----------|--------|------|-----------|
| `/` | GET | Nao | Info do servico |
| `/health` | GET | Nao | Health check (modelo + tenants) |
| `/docs` | GET | Nao* | Swagger UI (*desabilitado em prod) |
| `/redoc` | GET | Nao* | ReDoc (*desabilitado em prod) |
| `/api/tenants` | GET | Nao | Lista tenants ativos |
| `/api/face/register` | POST | X-API-Key | Cadastrar face |
| `/api/face/recognize` | POST | X-API-Key | Reconhecer face |
| `/api/face/compare` | POST | X-API-Key | Comparar duas faces |
| `/facial` | GET | Nao | UI de captura |
| `/facial/register` | GET | Nao | UI modo cadastro |
| `/facial/recognize` | GET | Nao | UI modo reconhecimento |

## Autenticacao

Header obrigatorio para endpoints protegidos:
```
X-API-Key: sua_api_key_aqui
```

A API Key identifica o tenant e suas configuracoes (threshold, rate limit, banco de dados).

## Validacoes Implementadas

### Backend (main.py)

| Campo | Validacao | Mensagem |
|-------|-----------|----------|
| user_id | > 0 e <= 2147483647 | user_id deve ser positivo |
| image | MIME: jpeg, png, webp | Formato de imagem invalido |
| turnstile_id | >= 0 (opcional) | - |
| event_id | >= 0 (opcional) | - |
| threshold | > 0 | Usa DEFAULT_THRESHOLD |

### Frontend (api.js)

| Campo | Validacao | Comportamento |
|-------|-----------|---------------|
| api_url | URL valida (http/https) | Fallback: origin atual |
| user_id | Inteiro 1-2147483647 | Retorna null se invalido |
| callback_url | URL valida + HTTPS em prod | Ignora se invalido |
| email | Formato email | Retorna null se invalido |
| mode | register ou recognize | Default: register |

## Liveness Detection

### Tecnicas Implementadas (score ponderado):

| Tecnica | Peso | Threshold | Descricao |
|---------|------|-----------|-----------|
| Blur | 20% | variance > 100 | Laplacian variance |
| Brilho | 15% | 50 < mean < 200 | Mean brightness e std > 20 |
| Cor | 15% | std > 30 | Color std e saturacao adequada |
| Textura | 25% | moire < 0.15 | Deteccao de Moire via FFT |
| Frequencia | 25% | ratio > 1.0 | Distribuicao de energia |

### Criterios de Aprovacao:
- Score total > 0.6
- Checks criticos passaram (blur, texture, frequency)

### Challenges do Frontend:
1. Vire para ESQUERDA
2. Vire para DIREITA
3. Incline para BAIXO
4. Incline para CIMA
5. Posicao CENTRAL
6. Aproxime-se
7. Afaste-se

**Regras:**
- 3 challenges aleatorios + "central" no final
- Tempo minimo de 500ms por challenge
- Timeout total de 15 segundos

## Configuracoes (.env)

```bash
# =============================================================================
# API
# =============================================================================
API_HOST=0.0.0.0
API_PORT=8001
API_RELOAD=false
LOG_LEVEL=INFO
ENVIRONMENT=development  # ou production

# =============================================================================
# MODELO INSIGHTFACE
# =============================================================================
FACE_MODEL_NAME=buffalo_l
DEFAULT_THRESHOLD=0.4

# =============================================================================
# LIVENESS DETECTION
# =============================================================================
ENABLE_LIVENESS_CHECK=true
LIVENESS_BLUR_THRESHOLD=100.0
LIVENESS_BRIGHTNESS_MIN=50
LIVENESS_BRIGHTNESS_MAX=200
LIVENESS_BLINK_ENABLED=true
LIVENESS_BLINK_MIN_COUNT=2
LIVENESS_MOTION_ENABLED=true
LIVENESS_MOTION_MIN_FRAMES=10
LIVENESS_TEXTURE_ENABLED=true
LIVENESS_CHALLENGE_TIMEOUT_MS=10000
LIVENESS_MIN_CHALLENGE_TIME_MS=500

# =============================================================================
# CORS (EM PRODUCAO, NUNCA USE *)
# =============================================================================
CORS_ORIGINS=https://seu-dominio.com,https://app.seu-dominio.com
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST
CORS_ALLOW_HEADERS=Content-Type,X-API-Key

# =============================================================================
# REDIS (recomendado para producao)
# =============================================================================
REDIS_ENABLED=false
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# =============================================================================
# CACHE DE EMBEDDINGS
# =============================================================================
EMBEDDING_CACHE_ENABLED=true
EMBEDDING_CACHE_TTL=3600

# =============================================================================
# METRICAS
# =============================================================================
METRICS_ENABLED=true
METRICS_PORT=9090

# =============================================================================
# SEGURANCA
# =============================================================================
MAX_UPLOAD_SIZE=10485760  # 10MB
MIN_FACE_SIZE=10000       # pixels

# =============================================================================
# TENANT EXEMPLO
# =============================================================================
TENANT_XX_DB_HOST=localhost
TENANT_XX_DB_PORT=3306
TENANT_XX_DB_NAME=database_name
TENANT_XX_DB_USER=app_user
TENANT_XX_DB_PASS=secure_password
TENANT_XX_API_KEY=generated_api_key
TENANT_XX_THRESHOLD=0.4
TENANT_XX_RATE_LIMIT=100
TENANT_XX_ACTIVE=true
```

## Comandos Uteis

```bash
# Iniciar servico
docker-compose up -d

# Ver logs
docker-compose logs -f athenaface_service

# Rebuild apos mudancas
docker-compose up -d --build

# Gerar nova API key
python scripts/generate_api_keys.py

# Testar conexao dos tenants
python scripts/test_tenant_connection.py

# Download dos modelos
python scripts/download_models.py

# Rodar testes
pytest tests/ -v

# Rodar apenas testes de API
pytest tests/test_api.py -v

# Rodar apenas testes de liveness
pytest tests/test_liveness_service.py -v
```

## Integracao via Frontend

### URL com parametros:
```
http://localhost:8001/facial?api_key=KEY&tenant_id=TENANT&user_id=123&mode=register
```

### Parametros:
- `api_key`: API Key do tenant (obrigatorio)
- `tenant_id`: ID do tenant (obrigatorio)
- `user_id`: ID do usuario (obrigatorio para register, deve ser > 0)
- `mode`: `register` ou `recognize`
- `callback_url`: URL para webhook (opcional, deve ser HTTPS em producao)
- `user_name`, `user_email`, `user_phone`: Dados do usuario (opcional)

### Recebendo resultado via postMessage:
```javascript
window.addEventListener('message', (event) => {
    // IMPORTANTE: Validar origin em producao
    if (event.origin !== 'https://seu-dominio.com') return;

    if (event.data.type === 'ATHENAFACE_RESULT') {
        console.log(event.data.result);
        // { success: true, data: { ... } }
    }
});
```

### Fechando o modal:
```javascript
// Enviar para fechar
popup.postMessage({ type: 'ATHENAFACE_CLOSE' }, 'https://seu-dominio.com');
```

## Notas Tecnicas

- **Modelo InsightFace**: buffalo_l (embedding 512 dimensoes)
- **Distancia**: Euclidiana (< threshold = match)
- **Formato embedding**: JSON array no MySQL
- **Frontend**: Single Page Application vanilla JS
- **Challenges**: Selecionados aleatoriamente, sempre termina com "center"
- **Seguranca**: Tempo minimo de 500ms por challenge
- **Context Manager**: Todas conexoes DB usam context manager
- **Logging**: Identificadores hasheados para privacidade

## Problemas Conhecidos (Resolvidos)

1. ~~Arquivo __init).py: Nome incorreto em src/middleware/~~ **CORRIGIDO**
2. ~~Arquivo __init_.py: Nome incorreto em src/utils/~~ **CORRIGIDO**
3. ~~Erro de sintaxe: `Athena FaceAPI` em app.js~~ **CORRIGIDO**
4. ~~PostMessage com '*': Inseguro~~ **CORRIGIDO** (usa origin especifico)
5. ~~Conexoes DB sem cleanup: Potencial leak~~ **CORRIGIDO** (context manager)
6. ~~Race condition no registro: SELECT + INSERT~~ **CORRIGIDO** (ON DUPLICATE KEY)

## Proximos Passos Sugeridos

1. **Integrar SDK de Liveness comercial** (Iproov, BioID)
2. **Migrar para banco vetorial** (Milvus, Pinecone)
3. **Adicionar Face Mesh** para deteccao de blink real
4. **Implementar webhook** para notificacoes em tempo real
5. **Adicionar dashboard** de metricas (Grafana)
6. **Implementar logging estruturado** (JSON logs)
7. **Adicionar testes de integracao**
8. **Configurar CI/CD** (GitHub Actions)
9. **Documentar API com exemplos** (Postman collection)
10. **Adicionar autenticacao JWT** para maior seguranca
