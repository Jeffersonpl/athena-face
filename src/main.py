"""
Athena Face - API Principal Multi-Tenant
"""
import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Dict, Any, Generator

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
import uvicorn

from src.config.settings import (
    API_HOST, API_PORT, API_RELOAD, CORS_ORIGINS,
    CORS_ALLOW_METHODS, CORS_ALLOW_HEADERS, CORS_ALLOW_CREDENTIALS,
    DEFAULT_THRESHOLD, ENABLE_LIVENESS_CHECK, BASE_DIR,
    MIN_FACE_SIZE, MAX_UPLOAD_SIZE, is_production
)
from src.config.tenants import list_active_tenants
from src.middleware.tenant_middleware import verify_tenant_api_key, get_tenant_from_request
from src.models.database import get_tenant_db_connection, test_tenant_connection
from src.services.face_service import FaceService
from src.services.liveness_service import LivenessService
from src.utils.image_utils import image_to_array

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar serviços
face_service = FaceService()
liveness_service = LivenessService()


# ==================== CONTEXT MANAGERS ====================

@contextmanager
def get_db_cursor(tenant_config: Dict, dictionary: bool = False) -> Generator:
    """
    Context manager para conexão segura com o banco de dados.
    Garante que conexões são fechadas mesmo em caso de erro.
    """
    conn = None
    cursor = None
    try:
        conn = get_tenant_db_connection(tenant_config)
        cursor = conn.cursor(dictionary=dictionary) if dictionary else conn.cursor()
        yield conn, cursor
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ==================== VALIDATION MODELS ====================

class RegisterFaceRequest(BaseModel):
    """Modelo de validação para registro de face"""
    user_id: int = Field(..., gt=0, le=2147483647, description="ID do usuário (positivo)")
    check_liveness: bool = Field(True, description="Verificar liveness")

    @validator('user_id')
    def validate_user_id(cls, v):
        if v <= 0:
            raise ValueError('user_id deve ser positivo')
        return v


# ==================== HELPER FUNCTIONS ====================

def generate_error_id() -> str:
    """Gera ID único para rastreamento de erros"""
    return str(uuid.uuid4())[:8]


def safe_error_response(error: Exception, error_id: str) -> str:
    """
    Retorna mensagem de erro segura.
    Em produção, não expõe detalhes internos.
    """
    if is_production():
        return f"Erro interno (ID: {error_id}). Contate o suporte com este ID."
    return f"Erro: {str(error)}"


def validate_image_upload(image: UploadFile) -> None:
    """Valida upload de imagem"""
    # Verificar tipo MIME
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    if image.content_type and image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de imagem inválido. Permitidos: {', '.join(allowed_types)}"
        )


def hash_identifier(identifier: Any) -> str:
    """Hash de identificadores para logging seguro"""
    import hashlib
    return hashlib.sha256(str(identifier).encode()).hexdigest()[:12]


# ==================== FASTAPI APP ====================

# Configurar docs baseado no ambiente
docs_config = {}
if is_production():
    # Em produção, desabilitar docs públicos
    docs_config = {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None
    }
else:
    docs_config = {
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

app = FastAPI(
    title="Athena Face - Facial Recognition API",
    version="2.0.0",
    description="Serviço Multi-Tenant de Reconhecimento Facial com InsightFace e Liveness Detection Avançado",
    **docs_config
)

# CORS - Configuração mais segura
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS else [],
    allow_credentials=CORS_ALLOW_CREDENTIALS if "*" not in CORS_ORIGINS else False,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
)

# Montar arquivos estáticos do frontend
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    logger.info(f"Frontend montado em /static")


# ==================== LIFECYCLE EVENTS ====================

@app.on_event("startup")
async def startup_event():
    """Executado na inicialização do serviço"""
    logger.info("=" * 60)
    logger.info("Athena Face iniciando...")
    logger.info("=" * 60)

    # Carregar modelo
    success = face_service.initialize()

    if not success:
        logger.error("Falha ao carregar modelo InsightFace")
        logger.error("Execute: python scripts/download_models.py")

    # Listar tenants ativos
    tenants = list_active_tenants()
    logger.info(f"Tenants ativos: {len(tenants)}")
    for tenant_id, tenant_name in tenants.items():
        logger.info(f"  - {tenant_id}: {tenant_name}")

    # Validar configuração CORS
    if "*" in CORS_ORIGINS and is_production():
        logger.warning("CORS configurado com '*' em produção! Configure CORS_ORIGINS com domínios específicos.")

    logger.info("Athena Face pronto!")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Executado ao desligar o serviço"""
    logger.info("Athena Face encerrando...")
    # Cleanup de recursos se necessário


# ==================== PUBLIC ROUTES ====================

@app.get("/")
def read_root() -> Dict[str, Any]:
    """Informações do serviço"""
    tenants = list_active_tenants()

    return {
        "service": "Athena Face - Facial Recognition API",
        "version": "2.0.0",
        "status": "running",
        "model": {
            "name": face_service.model_name,
            "loaded": face_service.is_ready()
        },
        "features": {
            "multi_tenant": True,
            "liveness_detection": ENABLE_LIVENESS_CHECK,
            "liveness_version": "2.0",
            "depth_3d_detection": True,
            "eye_reflection_detection": True,
            "skin_texture_analysis": True,
            "challenge_response": True,
            "rate_limiting": True,
            "frontend": True,
            "metrics": True
        },
        "tenants_count": len(tenants),
        "docs": "/docs" if not is_production() else None,
        "frontend": "/facial",
        "metrics": "/api/metrics/prometheus"
    }


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """
    Health check endpoint com verificação de componentes.
    Útil para Kubernetes/Docker health probes.
    """
    model_status = "loaded" if face_service.is_ready() else "not_loaded"

    # Verificar se há tenants configurados
    tenants = list_active_tenants()
    tenants_status = "configured" if len(tenants) > 0 else "no_tenants"

    # Status geral
    is_healthy = model_status == "loaded" and tenants_status == "configured"

    return {
        "status": "healthy" if is_healthy else "degraded",
        "service": "athenaface",
        "checks": {
            "model": model_status,
            "tenants": tenants_status
        },
        "timestamp": datetime.now().isoformat()
    }


# ==================== FRONTEND ROUTES ====================

@app.get("/facial", response_class=HTMLResponse)
@app.get("/facial/register", response_class=HTMLResponse)
@app.get("/facial/recognize", response_class=HTMLResponse)
async def serve_frontend():
    """
    Serve a interface web de reconhecimento facial

    Parâmetros via query string:
    - api_key: API Key do tenant (obrigatório)
    - tenant_id: ID do tenant (obrigatório)
    - user_id: ID do usuário (obrigatório para register)
    - mode: 'register' ou 'recognize' (default: register)
    - callback_url: URL para callback (opcional)
    - user_name: Nome do usuário (opcional)
    - user_email: Email do usuário (opcional)
    """
    index_path = FRONTEND_DIR / "index.html"

    if not index_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend não encontrado. Verifique se a pasta 'frontend' existe."
        )

    return FileResponse(str(index_path))


# ==================== API ROUTES ====================

@app.post("/api/face/register")
async def register_face(
        request: Request,
        user_id: int = Form(..., gt=0, le=2147483647, description="ID do usuário"),
        image: UploadFile = File(..., description="Imagem com face"),
        check_liveness: bool = Form(True, description="Verificar liveness"),
        tenant_data: dict = Depends(verify_tenant_api_key)
):
    """
    Cadastra face de usuário

    **Requer Header:** `X-API-Key: your_tenant_api_key`

    **Validações:**
    - user_id deve ser positivo
    - Imagem deve ser JPEG, PNG ou WebP
    - Apenas uma face deve estar presente na imagem
    """
    start_time = datetime.now()
    error_id = generate_error_id()

    # Verificar se modelo está carregado
    if not face_service.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Modelo não carregado. Execute: python scripts/download_models.py"
        )

    # Validar imagem
    validate_image_upload(image)

    tenant_id = tenant_data["tenant_id"]
    tenant_config = tenant_data["config"]

    # Log seguro (sem expor user_id real em produção)
    logger.info(f"Cadastro de face - Tenant: {tenant_id}, User: {hash_identifier(user_id)}")

    try:
        # Converter imagem
        image_array = image_to_array(image)

        # Extrair embedding
        face_data = face_service.extract_embedding(image_array)

        if not face_data:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma face detectada na imagem"
            )

        # Verificar se múltiplas faces
        if face_data.get("multiple_faces"):
            raise HTTPException(
                status_code=400,
                detail="Múltiplas faces detectadas. Envie imagem com apenas uma face."
            )

        embedding = face_data["embedding"]
        quality_score = face_data["quality_score"]

        # Liveness check
        liveness_result = {"passed": True, "score": 1.0}
        if check_liveness and ENABLE_LIVENESS_CHECK:
            liveness_result = liveness_service.check_liveness(image_array)

            if not liveness_result["passed"]:
                logger.warning(f"Liveness falhou - User: {hash_identifier(user_id)}")

        # Salvar no banco do tenant usando context manager
        with get_db_cursor(tenant_config) as (conn, cursor):
            # Usar INSERT ... ON DUPLICATE KEY UPDATE para evitar race condition
            cursor.execute(
                """
                INSERT INTO facial_recognitions
                (user_id, face_embedding, confidence_score, liveness_passed,
                 liveness_score, verified_at, image_path, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                    face_embedding = VALUES(face_embedding),
                    confidence_score = VALUES(confidence_score),
                    liveness_passed = VALUES(liveness_passed),
                    liveness_score = VALUES(liveness_score),
                    verified_at = VALUES(verified_at),
                    updated_at = NOW()
                """,
                (
                    user_id,
                    json.dumps(embedding),
                    quality_score,
                    liveness_result["passed"],
                    liveness_result["score"],
                    datetime.now() if liveness_result["passed"] else None,
                    f"faces/{tenant_id}/user_{user_id}.jpg"
                )
            )

            # Atualizar flag do usuário
            cursor.execute(
                "UPDATE users SET has_facial_recognition = TRUE WHERE id = %s",
                (user_id,)
            )

            conn.commit()
            logger.info(f"Face cadastrada/atualizada - User: {hash_identifier(user_id)}")

        # Calcular tempo de processamento
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return {
            "success": True,
            "message": "Face cadastrada com sucesso",
            "data": {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "confidence_score": quality_score,
                "liveness": liveness_result,
                "embedding_dimensions": len(embedding),
                "processing_time_ms": int(processing_time)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no cadastro (ID: {error_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=safe_error_response(e, error_id))


@app.post("/api/face/recognize")
async def recognize_face(
        request: Request,
        image: UploadFile = File(..., description="Imagem com face para reconhecimento"),
        turnstile_id: Optional[int] = Form(None, ge=0, description="ID da catraca"),
        event_id: Optional[int] = Form(None, ge=0, description="ID do evento"),
        tenant_data: dict = Depends(verify_tenant_api_key)
):
    """
    Reconhece face e libera acesso

    **Requer Header:** `X-API-Key: your_tenant_api_key`
    """
    start_time = datetime.now()
    error_id = generate_error_id()

    if not face_service.is_ready():
        raise HTTPException(status_code=503, detail="Modelo não carregado")

    # Validar imagem
    validate_image_upload(image)

    tenant_id = tenant_data["tenant_id"]
    tenant_config = tenant_data["config"]
    threshold = tenant_config.get("threshold", DEFAULT_THRESHOLD)

    # Validar threshold para evitar divisão por zero
    if threshold <= 0:
        threshold = DEFAULT_THRESHOLD

    logger.info(f"Reconhecimento - Tenant: {tenant_id}, Catraca: {turnstile_id}")

    try:
        # Converter imagem
        image_array = image_to_array(image)

        # Extrair embedding
        face_data = face_service.extract_embedding(image_array)

        if not face_data:
            return {
                "granted": False,
                "message": "Nenhuma face detectada",
                "user": None,
                "confidence": 0
            }

        test_embedding = face_data["embedding"]

        # Buscar faces cadastradas do tenant usando context manager
        with get_db_cursor(tenant_config, dictionary=True) as (conn, cursor):
            # Query com LIMIT para performance
            cursor.execute(
                """
                SELECT fr.*, u.name, u.email
                FROM facial_recognitions fr
                JOIN users u ON u.id = fr.user_id
                WHERE fr.liveness_passed = TRUE
                LIMIT 10000
                """
            )

            registered_faces = cursor.fetchall()

            if not registered_faces:
                return {
                    "granted": False,
                    "message": "Nenhuma face cadastrada no sistema",
                    "user": None,
                    "confidence": 0
                }

            # Encontrar melhor match
            best_match = None
            best_distance = float('inf')

            for registered in registered_faces:
                try:
                    embedding = json.loads(registered['face_embedding'])
                    distance = face_service.calculate_distance(test_embedding, embedding)

                    if distance < best_distance:
                        best_distance = distance
                        best_match = registered
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Embedding inválido para user_id={registered.get('user_id')}: {e}")
                    continue

            if best_match is None:
                return {
                    "granted": False,
                    "message": "Erro ao processar faces cadastradas",
                    "user": None,
                    "confidence": 0
                }

            # Verificar se passou no threshold
            granted = best_distance < threshold
            confidence = face_service.calculate_similarity(best_distance, threshold)
            status = 'granted' if granted else 'denied'

            # Calcular tempo de processamento
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # Log de acesso
            cursor.execute(
                """
                INSERT INTO access_logs
                (user_id, event_id, turnstile_id, recognition_method,
                 match_confidence, match_distance, status, notes,
                 processing_time_ms, ip_address, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (
                    best_match['user_id'] if granted else None,
                    event_id,
                    turnstile_id,
                    'facial',
                    confidence,
                    best_distance,
                    status,
                    f"Threshold: {threshold}",
                    int(processing_time),
                    request.client.host if request.client else None
                )
            )

            conn.commit()

        logger.info(
            f"{'ACESSO LIBERADO' if granted else 'ACESSO NEGADO'} - "
            f"User: {hash_identifier(best_match['user_id']) if granted else 'N/A'}, "
            f"Distance: {best_distance:.4f}, "
            f"Confidence: {confidence:.2%}"
        )

        return {
            "granted": granted,
            "message": "Acesso liberado" if granted else "Acesso negado - Face não reconhecida",
            "user": {
                "id": best_match['user_id'],
                "name": best_match['name'],
                "email": best_match['email']
            } if granted else None,
            "confidence": float(confidence),
            "distance": float(best_distance),
            "threshold": threshold,
            "processing_time_ms": int(processing_time)
        }

    except Exception as e:
        logger.error(f"Erro no reconhecimento (ID: {error_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=safe_error_response(e, error_id))


@app.post("/api/face/compare")
async def compare_faces(
        image1: UploadFile = File(..., description="Primeira imagem"),
        image2: UploadFile = File(..., description="Segunda imagem"),
        tenant_data: dict = Depends(verify_tenant_api_key)
):
    """
    Compara duas faces

    **Requer Header:** `X-API-Key: your_tenant_api_key`
    """
    error_id = generate_error_id()

    if not face_service.is_ready():
        raise HTTPException(status_code=503, detail="Modelo não carregado")

    # Validar imagens
    validate_image_upload(image1)
    validate_image_upload(image2)

    tenant_config = tenant_data["config"]
    threshold = tenant_config.get("threshold", DEFAULT_THRESHOLD)

    # Validar threshold
    if threshold <= 0:
        threshold = DEFAULT_THRESHOLD

    try:
        # Processar imagem 1
        image1_array = image_to_array(image1)
        face1_data = face_service.extract_embedding(image1_array)

        if not face1_data:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma face detectada na imagem 1"
            )

        # Processar imagem 2
        image2_array = image_to_array(image2)
        face2_data = face_service.extract_embedding(image2_array)

        if not face2_data:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma face detectada na imagem 2"
            )

        # Comparar
        comparison = face_service.compare_embeddings(
            face1_data["embedding"],
            face2_data["embedding"],
            threshold
        )

        return {
            "success": True,
            "is_same_person": comparison["is_match"],
            "similarity": comparison["similarity"],
            "distance": comparison["distance"],
            "threshold": threshold
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na comparação (ID: {error_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=safe_error_response(e, error_id))


@app.get("/api/tenants")
def list_tenants() -> Dict[str, Any]:
    """
    Lista tenants ativos (endpoint público)
    """
    tenants = list_active_tenants()

    return {
        "success": True,
        "count": len(tenants),
        "tenants": [
            {"id": tenant_id, "name": name}
            for tenant_id, name in tenants.items()
        ]
    }


# ==================== METRICS ROUTES ====================

# Contadores globais para métricas
_metrics = {
    "requests_total": 0,
    "register_total": 0,
    "recognize_total": 0,
    "compare_total": 0,
    "errors_total": 0,
    "liveness_passed": 0,
    "liveness_failed": 0,
    "access_granted": 0,
    "access_denied": 0,
    "start_time": datetime.now().isoformat()
}


def increment_metric(name: str, value: int = 1):
    """Incrementa uma métrica"""
    if name in _metrics:
        _metrics[name] += value


@app.get("/api/metrics")
async def get_metrics(
    request: Request,
    tenant_data: dict = Depends(verify_tenant_api_key)
) -> Dict[str, Any]:
    """
    Retorna métricas do sistema

    **Requer Header:** `X-API-Key: your_tenant_api_key`

    Métricas disponíveis:
    - Estatísticas de requisições
    - Status do modelo
    - Informações do tenant
    - Estatísticas de liveness
    - Estatísticas de acesso
    """
    tenant_id = tenant_data["tenant_id"]
    tenant_config = tenant_data["config"]

    # Métricas do modelo
    model_info = {
        "name": face_service.model_name,
        "is_ready": face_service.is_ready(),
        "det_size": face_service.det_size
    }

    # Estatísticas do tenant
    tenant_stats = {
        "tenant_id": tenant_id,
        "threshold": tenant_config.get("threshold", DEFAULT_THRESHOLD)
    }

    # Tentar obter estatísticas do banco
    db_stats = {}
    try:
        with get_db_cursor(tenant_config, dictionary=True) as (conn, cursor):
            # Total de faces cadastradas
            cursor.execute(
                "SELECT COUNT(*) as total FROM facial_recognitions WHERE liveness_passed = TRUE"
            )
            result = cursor.fetchone()
            db_stats["registered_faces"] = result["total"] if result else 0

            # Total de usuários com facial
            cursor.execute(
                "SELECT COUNT(*) as total FROM users WHERE has_facial_recognition = TRUE"
            )
            result = cursor.fetchone()
            db_stats["users_with_facial"] = result["total"] if result else 0

            # Acessos hoje
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'granted' THEN 1 ELSE 0 END) as granted,
                    SUM(CASE WHEN status = 'denied' THEN 1 ELSE 0 END) as denied,
                    AVG(processing_time_ms) as avg_processing_time
                FROM access_logs
                WHERE DATE(created_at) = CURDATE()
                """
            )
            result = cursor.fetchone()
            if result:
                db_stats["today"] = {
                    "total_accesses": result["total"] or 0,
                    "granted": result["granted"] or 0,
                    "denied": result["denied"] or 0,
                    "avg_processing_time_ms": float(result["avg_processing_time"]) if result["avg_processing_time"] else 0
                }
    except Exception as e:
        logger.debug(f"Error getting DB stats: {e}")
        db_stats = {"error": "Unable to fetch database statistics"}

    # Liveness service stats
    liveness_stats = {
        "active_sessions": len(liveness_service.sessions),
        "version": "2.0"
    }

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "uptime_since": _metrics["start_time"],
        "model": model_info,
        "tenant": tenant_stats,
        "database": db_stats,
        "liveness": liveness_stats,
        "counters": {
            "requests_total": _metrics["requests_total"],
            "register_total": _metrics["register_total"],
            "recognize_total": _metrics["recognize_total"],
            "compare_total": _metrics["compare_total"],
            "errors_total": _metrics["errors_total"]
        }
    }


@app.get("/api/metrics/prometheus")
async def get_prometheus_metrics() -> str:
    """
    Retorna métricas no formato Prometheus

    Endpoint público para scraping do Prometheus.
    """
    from fastapi.responses import PlainTextResponse

    tenants = list_active_tenants()
    model_ready = 1 if face_service.is_ready() else 0

    metrics_text = f"""# HELP athenaface_model_ready Model loaded status
# TYPE athenaface_model_ready gauge
athenaface_model_ready {model_ready}

# HELP athenaface_tenants_total Total number of active tenants
# TYPE athenaface_tenants_total gauge
athenaface_tenants_total {len(tenants)}

# HELP athenaface_liveness_sessions_active Active liveness sessions
# TYPE athenaface_liveness_sessions_active gauge
athenaface_liveness_sessions_active {len(liveness_service.sessions)}

# HELP athenaface_requests_total Total requests by type
# TYPE athenaface_requests_total counter
athenaface_requests_total{{type="register"}} {_metrics["register_total"]}
athenaface_requests_total{{type="recognize"}} {_metrics["recognize_total"]}
athenaface_requests_total{{type="compare"}} {_metrics["compare_total"]}

# HELP athenaface_errors_total Total errors
# TYPE athenaface_errors_total counter
athenaface_errors_total {_metrics["errors_total"]}

# HELP athenaface_access_total Access attempts by result
# TYPE athenaface_access_total counter
athenaface_access_total{{result="granted"}} {_metrics["access_granted"]}
athenaface_access_total{{result="denied"}} {_metrics["access_denied"]}

# HELP athenaface_liveness_total Liveness checks by result
# TYPE athenaface_liveness_total counter
athenaface_liveness_total{{result="passed"}} {_metrics["liveness_passed"]}
athenaface_liveness_total{{result="failed"}} {_metrics["liveness_failed"]}
"""

    return PlainTextResponse(content=metrics_text, media_type="text/plain")


# ==================== MAIN ====================

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=API_RELOAD
    )
