import os
import sys
import json
import base64
import numpy as np
from io import BytesIO
from datetime import datetime
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

import cv2
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import mysql.connector
from mysql.connector import Error

# Carregar .env
load_dotenv()

# Configurações MySQL
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'database': os.getenv('DB_DATABASE', 'laravel'),
    'user': os.getenv('DB_USERNAME', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
}

# FastAPI
app = FastAPI(
    title="Athena Face - Facial Recognition API",
    version="1.0.0",
    description="Serviço de reconhecimento facial com InsightFace"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar InsightFace (lazy loading)
face_app = None
DEFAULT_THRESHOLD = float(os.getenv('DEFAULT_THRESHOLD', '0.4'))


def init_face_app():
    """Inicializa InsightFace apenas quando necessário"""
    global face_app

    if face_app is not None:
        return face_app

    try:
        print("🔄 Carregando modelo InsightFace...")

        # Importar aqui para evitar erro se modelo não existir
        from insightface.app import FaceAnalysis

        # Verificar se modelos existem
        models_path = Path.home() / ".insightface" / "models" / "buffalo_l"

        if not models_path.exists():
            print(f"❌ Modelos não encontrados em {models_path}")
            print("Execute: python download_models.py")
            return None

        face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
        face_app.prepare(ctx_id=0, det_size=(640, 640))

        print("✅ Modelo InsightFace carregado!")
        return face_app

    except Exception as e:
        print(f"❌ Erro ao carregar InsightFace: {e}")
        return None


def get_db_connection():
    """Cria conexão com MySQL"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"❌ Erro MySQL: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao conectar ao banco: {str(e)}")


def calculate_distance(embedding1, embedding2):
    """Distância euclidiana"""
    return float(np.linalg.norm(np.array(embedding1) - np.array(embedding2)))


def calculate_similarity(distance, threshold=DEFAULT_THRESHOLD):
    """Score de similaridade"""
    return float(max(0, 1 - (distance / threshold)))


def check_liveness_basic(image_array):
    """Liveness detection básico"""
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)

    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    blur_score = min(laplacian_var / 100, 1.0)

    mean_brightness = np.mean(gray)
    std_brightness = np.std(gray)
    brightness_score = 1.0 if 40 < mean_brightness < 200 and std_brightness > 20 else 0.5

    liveness_score = (blur_score * 0.6 + brightness_score * 0.4)

    return {
        'passed': liveness_score > 0.6,
        'score': float(liveness_score),
        'blur_score': float(blur_score),
        'brightness_score': float(brightness_score)
    }


def image_to_array(image_file):
    """Converte imagem para numpy array"""
    try:
        if isinstance(image_file, str):
            image_data = base64.b64decode(image_file.split(',')[1] if ',' in image_file else image_file)
            image = Image.open(BytesIO(image_data))
        else:
            image = Image.open(BytesIO(image_file.file.read()))

        if image.mode != 'RGB':
            image = image.convert('RGB')

        image_array = np.array(image)
        image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)

        return image_array
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao processar imagem: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """Executado na inicialização"""
    print("🚀 Athena Face iniciando...")
    init_face_app()


@app.get("/")
def read_root():
    return {
        "service": "Athena Face - Facial Recognition API",
        "version": "1.0.0",
        "status": "running",
        "model": "buffalo_l" if face_app else "not_loaded",
        "github": "https://github.com/your-repo/athenaface"
    }


@app.get("/health")
def health_check():
    """Health check"""
    db_status = "ok"
    try:
        conn = get_db_connection()
        conn.close()
    except:
        db_status = "error"

    model_status = "loaded" if face_app else "not_loaded"

    return {
        "status": "ok" if (db_status == "ok" and model_status == "loaded") else "degraded",
        "service": "athenaface",
        "database": db_status,
        "model": model_status,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/face/register")
async def register_face(
        user_id: int = Form(...),
        image: UploadFile = File(...),
        check_liveness: bool = Form(True)
):
    """Cadastra face"""
    app_instance = init_face_app()

    if not app_instance:
        raise HTTPException(
            status_code=503,
            detail="Modelo não carregado. Execute: python download_models.py"
        )

    try:
        image_array = image_to_array(image)
        faces = app_instance.get(image_array)

        if len(faces) == 0:
            raise HTTPException(status_code=400, detail="Nenhuma face detectada")

        if len(faces) > 1:
            raise HTTPException(status_code=400, detail="Múltiplas faces detectadas")

        face = faces[0]
        embedding = face.embedding.tolist()

        bbox = face.bbox
        face_size = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        image_size = image_array.shape[0] * image_array.shape[1]
        quality_score = min(face_size / image_size * 10, 1.0)

        liveness_result = {'passed': True, 'score': 1.0}
        if check_liveness:
            liveness_result = check_liveness_basic(image_array)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM facial_recognitions WHERE user_id = %s", (user_id,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                """
                UPDATE facial_recognitions
                SET face_embedding   = %s,
                    confidence_score = %s,
                    liveness_passed  = %s,
                    verified_at      = %s,
                    updated_at       = NOW()
                WHERE user_id = %s
                """,
                (json.dumps(embedding), quality_score, liveness_result['passed'],
                 datetime.now() if liveness_result['passed'] else None, user_id)
            )
        else:
            cursor.execute(
                """
                INSERT INTO facial_recognitions
                (user_id, face_embedding, confidence_score, liveness_passed,
                 verified_at, image_path, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (user_id, json.dumps(embedding), quality_score, liveness_result['passed'],
                 datetime.now() if liveness_result['passed'] else None, f"faces/user_{user_id}.jpg")
            )

        cursor.execute("UPDATE users SET has_facial_recognition = TRUE WHERE id = %s", (user_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "success": True,
            "message": "Face cadastrada com sucesso",
            "data": {
                "user_id": user_id,
                "confidence_score": float(quality_score),
                "liveness": liveness_result,
                "embedding_dimensions": len(embedding)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


@app.post("/api/face/recognize")
async def recognize_face(
        image: UploadFile = File(...),
        turnstile_id: Optional[int] = Form(None),
        threshold: float = Form(DEFAULT_THRESHOLD)
):
    """Reconhece face"""
    app_instance = init_face_app()

    if not app_instance:
        raise HTTPException(status_code=503, detail="Modelo não carregado")

    try:
        image_array = image_to_array(image)
        faces = app_instance.get(image_array)

        if len(faces) == 0:
            return {"granted": False, "message": "Nenhuma face detectada", "user": None, "confidence": 0}

        if len(faces) > 1:
            return {"granted": False, "message": "Múltiplas faces detectadas", "user": None, "confidence": 0}

        face = faces[0]
        test_embedding = face.embedding.tolist()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT fr.*, u.name, u.email
            FROM facial_recognitions fr
                     JOIN users u ON u.id = fr.user_id
            WHERE fr.liveness_passed = TRUE
            """
        )

        registered_faces = cursor.fetchall()

        if not registered_faces:
            cursor.close()
            conn.close()
            return {"granted": False, "message": "Nenhuma face cadastrada", "user": None, "confidence": 0}

        best_match = None
        best_distance = float('inf')

        for registered in registered_faces:
            embedding = json.loads(registered['face_embedding'])
            distance = calculate_distance(test_embedding, embedding)

            if distance < best_distance:
                best_distance = distance
                best_match = registered

        granted = best_distance < threshold
        confidence = calculate_similarity(best_distance, threshold)

        status = 'granted' if granted else 'denied'

        cursor.execute(
            """
            INSERT INTO access_logs
            (user_id, turnstile_id, recognition_method, match_confidence,
             status, notes, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (best_match['user_id'] if granted else None, turnstile_id, 'facial',
             confidence, status, f"Distance: {best_distance:.4f}")
        )

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "granted": granted,
            "message": "Acesso liberado" if granted else "Acesso negado",
            "user": {
                "id": best_match['user_id'],
                "name": best_match['name'],
                "email": best_match['email']
            } if granted else None,
            "confidence": float(confidence),
            "distance": float(best_distance),
            "threshold": threshold
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


@app.post("/api/face/compare")
async def compare_faces(
        image1: UploadFile = File(...),
        image2: UploadFile = File(...)
):
    """Compara duas faces"""
    app_instance = init_face_app()

    if not app_instance:
        raise HTTPException(status_code=503, detail="Modelo não carregado")

    try:
        image1_array = image_to_array(image1)
        faces1 = app_instance.get(image1_array)

        if len(faces1) == 0:
            raise HTTPException(status_code=400, detail="Nenhuma face na imagem 1")

        image2_array = image_to_array(image2)
        faces2 = app_instance.get(image2_array)

        if len(faces2) == 0:
            raise HTTPException(status_code=400, detail="Nenhuma face na imagem 2")

        embedding1 = faces1[0].embedding
        embedding2 = faces2[0].embedding

        distance = calculate_distance(embedding1, embedding2)
        similarity = calculate_similarity(distance)
        is_same_person = distance < DEFAULT_THRESHOLD

        return {
            "success": True,
            "is_same_person": is_same_person,
            "similarity": float(similarity),
            "distance": float(distance),
            "threshold": DEFAULT_THRESHOLD
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        "facial_recognition_service:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )