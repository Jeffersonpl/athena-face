# API Reference - Athena Face

Documentacao completa da API REST do Athena Face.

## Base URL

```
Desenvolvimento: http://localhost:8001
Producao: https://api.seudominio.com
```

---

## Autenticacao

Todas as requisicoes aos endpoints protegidos devem incluir o header `X-API-Key`.

```http
X-API-Key: sua_api_key_aqui
```

### Exemplo com cURL

```bash
curl -X POST http://localhost:8001/api/face/recognize \
  -H "X-API-Key: sua_api_key" \
  -H "Content-Type: multipart/form-data" \
  -F "image=@foto.jpg"
```

### Erros de Autenticacao

| Codigo | Mensagem | Causa |
|--------|----------|-------|
| 401 | API Key ausente | Header X-API-Key nao enviado |
| 403 | API Key invalida | Chave nao reconhecida |
| 403 | Tenant inativo | Tenant desabilitado |
| 429 | Rate limit excedido | Muitas requisicoes |

---

## Endpoints Publicos

### GET /

Informacoes basicas do servico.

**Request**
```http
GET / HTTP/1.1
Host: localhost:8001
```

**Response 200**
```json
{
  "service": "Athena Face",
  "version": "2.0.0",
  "status": "running"
}
```

---

### GET /health

Health check detalhado.

**Request**
```http
GET /health HTTP/1.1
Host: localhost:8001
```

**Response 200**
```json
{
  "status": "healthy",
  "model": "buffalo_l",
  "model_loaded": true,
  "tenants_active": 3,
  "timestamp": "2026-01-15T10:30:00Z"
}
```

---

### GET /api/tenants

Lista tenants ativos (sem dados sensiveis).

**Request**
```http
GET /api/tenants HTTP/1.1
Host: localhost:8001
```

**Response 200**
```json
{
  "tenants": [
    {
      "id": "empresa_a",
      "active": true,
      "rate_limit": 100
    },
    {
      "id": "empresa_b",
      "active": true,
      "rate_limit": 200
    }
  ]
}
```

---

## Endpoints Protegidos

### POST /api/face/register

Cadastra uma nova face no sistema.

**Headers**
```http
X-API-Key: sua_api_key
Content-Type: multipart/form-data
```

**Body (form-data)**

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| image | file | Sim | Imagem da face (JPEG, PNG, WebP) |
| user_id | integer | Sim | ID do usuario (> 0) |
| turnstile_id | integer | Nao | ID do totem/catraca |
| event_id | integer | Nao | ID do evento |

**Request**
```bash
curl -X POST http://localhost:8001/api/face/register \
  -H "X-API-Key: sua_api_key" \
  -F "image=@foto.jpg" \
  -F "user_id=123" \
  -F "event_id=456"
```

**Response 200 - Sucesso**
```json
{
  "success": true,
  "message": "Face cadastrada com sucesso",
  "data": {
    "user_id": 123,
    "face_quality": 0.92,
    "liveness_score": 0.87,
    "registered_at": "2026-01-15T10:30:00Z"
  }
}
```

**Response 400 - Face nao detectada**
```json
{
  "success": false,
  "error": "Nenhuma face detectada na imagem",
  "code": "NO_FACE_DETECTED"
}
```

**Response 400 - Multiplas faces**
```json
{
  "success": false,
  "error": "Multiplas faces detectadas. Envie imagem com apenas uma face.",
  "code": "MULTIPLE_FACES"
}
```

**Response 400 - Liveness falhou**
```json
{
  "success": false,
  "error": "Verificacao de liveness falhou",
  "code": "LIVENESS_FAILED",
  "details": {
    "score": 0.45,
    "reason": "Possivel imagem de tela detectada"
  }
}
```

---

### POST /api/face/recognize

Busca uma face no banco de dados (1:N).

**Headers**
```http
X-API-Key: sua_api_key
Content-Type: multipart/form-data
```

**Body (form-data)**

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| image | file | Sim | Imagem da face |
| threshold | float | Nao | Threshold customizado (default: config do tenant) |
| limit | integer | Nao | Max resultados (default: 1) |

**Request**
```bash
curl -X POST http://localhost:8001/api/face/recognize \
  -H "X-API-Key: sua_api_key" \
  -F "image=@foto.jpg" \
  -F "threshold=0.4"
```

**Response 200 - Match encontrado**
```json
{
  "success": true,
  "matched": true,
  "data": {
    "user_id": 123,
    "similarity": 0.92,
    "threshold_used": 0.4,
    "liveness_passed": true,
    "processing_time_ms": 145
  }
}
```

**Response 200 - Nenhum match**
```json
{
  "success": true,
  "matched": false,
  "data": {
    "best_match": {
      "user_id": 456,
      "similarity": 0.35
    },
    "threshold_used": 0.4,
    "message": "Similaridade abaixo do threshold"
  }
}
```

---

### POST /api/face/compare

Compara duas faces (1:1).

**Headers**
```http
X-API-Key: sua_api_key
Content-Type: multipart/form-data
```

**Body (form-data)**

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| image1 | file | Sim | Primeira imagem |
| image2 | file | Sim | Segunda imagem |
| threshold | float | Nao | Threshold customizado |

**Request**
```bash
curl -X POST http://localhost:8001/api/face/compare \
  -H "X-API-Key: sua_api_key" \
  -F "image1=@documento.jpg" \
  -F "image2=@selfie.jpg"
```

**Response 200 - Faces correspondem**
```json
{
  "success": true,
  "match": true,
  "data": {
    "similarity": 0.94,
    "threshold_used": 0.4,
    "processing_time_ms": 230
  }
}
```

**Response 200 - Faces diferentes**
```json
{
  "success": true,
  "match": false,
  "data": {
    "similarity": 0.28,
    "threshold_used": 0.4,
    "message": "Faces nao correspondem"
  }
}
```

---

## Frontend Routes

### GET /facial

Interface de captura facial.

**Query Parameters**

| Parametro | Tipo | Obrigatorio | Descricao |
|-----------|------|-------------|-----------|
| api_key | string | Sim | API Key do tenant |
| tenant_id | string | Sim | ID do tenant |
| user_id | integer | Sim* | ID do usuario (*obrigatorio para register) |
| mode | string | Nao | `register` ou `recognize` (default: register) |
| callback_url | string | Nao | URL para webhook |

**Exemplo**
```
http://localhost:8001/facial?api_key=KEY&tenant_id=TENANT&user_id=123&mode=register
```

### Comunicacao via postMessage

```javascript
// Receber resultado
window.addEventListener('message', (event) => {
  if (event.origin !== 'http://localhost:8001') return;

  if (event.data.type === 'ATHENAFACE_RESULT') {
    console.log(event.data.result);
    // { success: true, data: { ... } }
  }
});

// Fechar modal
iframe.contentWindow.postMessage(
  { type: 'ATHENAFACE_CLOSE' },
  'http://localhost:8001'
);
```

---

## Codigos de Erro

### Erros de Validacao (4xx)

| Codigo | Constante | Descricao |
|--------|-----------|-----------|
| 400 | NO_FACE_DETECTED | Nenhuma face na imagem |
| 400 | MULTIPLE_FACES | Mais de uma face detectada |
| 400 | LIVENESS_FAILED | Falha na verificacao de liveness |
| 400 | INVALID_IMAGE | Formato de imagem invalido |
| 400 | IMAGE_TOO_SMALL | Resolucao muito baixa |
| 401 | API_KEY_MISSING | Header X-API-Key ausente |
| 403 | API_KEY_INVALID | Chave invalida |
| 403 | TENANT_INACTIVE | Tenant desabilitado |
| 422 | INVALID_USER_ID | user_id deve ser > 0 |
| 429 | RATE_LIMIT_EXCEEDED | Limite de requisicoes |

### Erros de Servidor (5xx)

| Codigo | Constante | Descricao |
|--------|-----------|-----------|
| 500 | INTERNAL_ERROR | Erro interno |
| 500 | MODEL_ERROR | Erro no modelo ML |
| 503 | SERVICE_UNAVAILABLE | Servico indisponivel |

---

## Rate Limiting

Headers retornados em cada resposta:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705320000
```

Quando excedido:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60

{
  "error": "Rate limit excedido",
  "retry_after": 60
}
```

---

## Exemplos de Integracao

### Python

```python
import requests

API_URL = "http://localhost:8001"
API_KEY = "sua_api_key"

def register_face(user_id: int, image_path: str):
    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{API_URL}/api/face/register",
            headers={"X-API-Key": API_KEY},
            files={"image": f},
            data={"user_id": user_id}
        )
    return response.json()

def recognize_face(image_path: str):
    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{API_URL}/api/face/recognize",
            headers={"X-API-Key": API_KEY},
            files={"image": f}
        )
    return response.json()

# Uso
result = register_face(123, "foto.jpg")
print(result)
```

### JavaScript/Node.js

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const API_URL = 'http://localhost:8001';
const API_KEY = 'sua_api_key';

async function recognizeFace(imagePath) {
  const form = new FormData();
  form.append('image', fs.createReadStream(imagePath));

  const response = await axios.post(
    `${API_URL}/api/face/recognize`,
    form,
    {
      headers: {
        'X-API-Key': API_KEY,
        ...form.getHeaders()
      }
    }
  );

  return response.data;
}

// Uso
recognizeFace('./foto.jpg')
  .then(result => console.log(result))
  .catch(err => console.error(err));
```

### cURL

```bash
# Registrar
curl -X POST http://localhost:8001/api/face/register \
  -H "X-API-Key: sua_api_key" \
  -F "image=@foto.jpg" \
  -F "user_id=123"

# Reconhecer
curl -X POST http://localhost:8001/api/face/recognize \
  -H "X-API-Key: sua_api_key" \
  -F "image=@foto.jpg"

# Comparar
curl -X POST http://localhost:8001/api/face/compare \
  -H "X-API-Key: sua_api_key" \
  -F "image1=@foto1.jpg" \
  -F "image2=@foto2.jpg"
```

---

## Webhooks (Callback)

Se `callback_url` for fornecido, o sistema enviara o resultado via POST:

```http
POST https://seu-sistema.com/webhook/athenaface
Content-Type: application/json

{
  "event": "face_recognized",
  "timestamp": "2026-01-15T10:30:00Z",
  "data": {
    "user_id": 123,
    "similarity": 0.92,
    "tenant_id": "empresa_a"
  }
}
```

---

## Suporte

- **Email**: jefferson@jeffersonpl.dev
- **Docs Online**: http://localhost:8001/docs
- **Issues**: https://github.com/Jeffersonpl/athena-face/issues
