"""
Servico de Reconhecimento Facial v2.0
Athena Face - InsightFace Integration
"""

import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
import hashlib

from src.config.settings import MODELS_DIR, FACE_MODEL_NAME, FACE_DET_SIZE

logger = logging.getLogger(__name__)


class FaceQuality(Enum):
    """Niveis de qualidade da face"""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    REJECTED = "rejected"


@dataclass
class FaceResult:
    """Resultado da deteccao de face"""

    embedding: List[float]
    bbox: Dict[str, float]
    landmarks: Optional[List[List[float]]]
    quality_score: float
    quality_level: FaceQuality
    det_score: float
    face_size: int
    face_ratio: float


class FaceService:
    """
    Servico de reconhecimento facial usando InsightFace
    Versao 2.0 com melhorias de qualidade e validacao
    """

    # Thresholds de qualidade
    QUALITY_EXCELLENT = 0.15  # Face ocupa >15% da imagem
    QUALITY_GOOD = 0.08  # Face ocupa >8% da imagem
    QUALITY_ACCEPTABLE = 0.04  # Face ocupa >4% da imagem
    QUALITY_MIN = 0.02  # Minimo para aceitar

    # Detection score minimo
    MIN_DET_SCORE = 0.5

    # Tamanho minimo da face em pixels
    MIN_FACE_SIZE = 80 * 80  # 80x80 pixels

    def __init__(self):
        self.face_app = None
        self.model_name = FACE_MODEL_NAME
        self.det_size = FACE_DET_SIZE
        self._model_hash: Optional[str] = None

    def initialize(self) -> bool:
        """
        Inicializa o modelo InsightFace

        Returns:
            True se carregado com sucesso, False caso contrario
        """
        if self.face_app is not None:
            logger.info("Modelo ja esta carregado")
            return True

        try:
            logger.info(f"Carregando modelo InsightFace: {self.model_name}")

            from insightface.app import FaceAnalysis

            model_path = MODELS_DIR / self.model_name

            if not model_path.exists():
                logger.error(f"Modelos nao encontrados em {model_path}")
                logger.error("Execute: python scripts/download_models.py")
                return False

            required_files = ["det_10g.onnx", "w600k_r50.onnx"]
            for file in required_files:
                if not (model_path / file).exists():
                    logger.error(f"Arquivo essencial nao encontrado: {file}")
                    return False

            # Calcular hash do modelo para verificacao de integridade
            self._model_hash = self._calculate_model_hash(model_path)

            self.face_app = FaceAnalysis(name=self.model_name, providers=["CPUExecutionProvider"])

            self.face_app.prepare(ctx_id=0, det_size=self.det_size)

            logger.info("Modelo InsightFace carregado com sucesso!")
            logger.info(f"Model hash: {self._model_hash[:16]}...")
            return True

        except Exception as e:
            logger.error(f"Erro ao carregar InsightFace: {e}")
            self.face_app = None
            return False

    def _calculate_model_hash(self, model_path: Path) -> str:
        """Calcula hash do modelo para verificacao de integridade"""
        try:
            det_file = model_path / "det_10g.onnx"
            if det_file.exists():
                with open(det_file, "rb") as f:
                    # Ler apenas os primeiros 1MB para performance
                    content = f.read(1024 * 1024)
                    return hashlib.sha256(content).hexdigest()
        except Exception:
            pass
        return "unknown"

    def is_ready(self) -> bool:
        """Verifica se modelo esta carregado"""
        return self.face_app is not None

    def get_model_info(self) -> Dict:
        """Retorna informacoes do modelo"""
        return {
            "name": self.model_name,
            "det_size": self.det_size,
            "is_ready": self.is_ready(),
            "model_hash": self._model_hash[:16] if self._model_hash else None,
            "embedding_size": 512,
            "version": "2.0",
        }

    def detect_faces(self, image_array: np.ndarray, max_faces: int = 10) -> List[Any]:
        """
        Detecta faces na imagem

        Args:
            image_array: Numpy array da imagem (BGR)
            max_faces: Numero maximo de faces a retornar

        Returns:
            Lista de faces detectadas
        """
        if not self.is_ready():
            raise RuntimeError("Modelo nao esta carregado. Chame initialize() primeiro.")

        faces = self.face_app.get(image_array)

        # Ordenar por tamanho (maior primeiro) e limitar
        if len(faces) > 1:
            faces = sorted(
                faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True
            )

        return faces[:max_faces]

    def extract_embedding(
        self,
        image_array: np.ndarray,
        allow_multiple: bool = False,
        min_quality: FaceQuality = FaceQuality.ACCEPTABLE,
    ) -> Optional[Dict]:
        """
        Extrai embedding da face detectada

        Args:
            image_array: Numpy array da imagem (BGR)
            allow_multiple: Se True, nao falha com multiplas faces
            min_quality: Qualidade minima aceitavel

        Returns:
            Dict com embedding e informacoes ou None
        """
        faces = self.detect_faces(image_array)

        if len(faces) == 0:
            return None

        if len(faces) > 1 and not allow_multiple:
            logger.warning(f"Multiplas faces detectadas: {len(faces)}")
            return {
                "error": "multiple_faces",
                "faces_count": len(faces),
                "message": "Multiplas faces detectadas. Use allow_multiple=True ou capture apenas uma face.",
            }

        # Usar a maior face (primeira apos ordenacao)
        face = faces[0]

        # Validar detection score
        det_score = float(face.det_score) if hasattr(face, "det_score") else 0.0
        if det_score < self.MIN_DET_SCORE:
            return {
                "error": "low_detection_score",
                "det_score": det_score,
                "message": f"Detection score muito baixo: {det_score:.2f}",
            }

        # Calcular metricas de qualidade
        bbox = face.bbox
        face_width = bbox[2] - bbox[0]
        face_height = bbox[3] - bbox[1]
        face_size = int(face_width * face_height)

        # Validar tamanho minimo
        if face_size < self.MIN_FACE_SIZE:
            return {
                "error": "face_too_small",
                "face_size": face_size,
                "min_size": self.MIN_FACE_SIZE,
                "message": "Face muito pequena. Aproxime-se da camera.",
            }

        image_height, image_width = image_array.shape[:2]
        image_size = image_height * image_width
        face_ratio = face_size / image_size

        # Determinar nivel de qualidade
        quality_level = self._determine_quality_level(face_ratio)
        quality_score = min(face_ratio * 10, 1.0)

        # Validar qualidade minima
        quality_order = [
            FaceQuality.REJECTED,
            FaceQuality.POOR,
            FaceQuality.ACCEPTABLE,
            FaceQuality.GOOD,
            FaceQuality.EXCELLENT,
        ]

        if quality_order.index(quality_level) < quality_order.index(min_quality):
            return {
                "error": "low_quality",
                "quality_level": quality_level.value,
                "min_quality": min_quality.value,
                "message": f"Qualidade {quality_level.value} abaixo do minimo {min_quality.value}",
            }

        # Processar landmarks
        landmarks = None
        if hasattr(face, "kps") and face.kps is not None:
            landmarks = face.kps.tolist()

        return {
            "embedding": face.embedding.tolist(),
            "bbox": {
                "x1": float(bbox[0]),
                "y1": float(bbox[1]),
                "x2": float(bbox[2]),
                "y2": float(bbox[3]),
                "width": float(face_width),
                "height": float(face_height),
            },
            "quality_score": float(quality_score),
            "quality_level": quality_level.value,
            "face_size": face_size,
            "face_ratio": float(face_ratio),
            "landmarks": landmarks,
            "det_score": det_score,
            "faces_detected": len(faces),
        }

    def extract_all_embeddings(
        self, image_array: np.ndarray, min_quality: FaceQuality = FaceQuality.POOR
    ) -> List[Dict]:
        """
        Extrai embeddings de todas as faces na imagem

        Args:
            image_array: Numpy array da imagem (BGR)
            min_quality: Qualidade minima para incluir

        Returns:
            Lista de dicts com embeddings
        """
        faces = self.detect_faces(image_array)
        results = []

        image_height, image_width = image_array.shape[:2]
        image_size = image_height * image_width

        for i, face in enumerate(faces):
            bbox = face.bbox
            face_width = bbox[2] - bbox[0]
            face_height = bbox[3] - bbox[1]
            face_size = int(face_width * face_height)
            face_ratio = face_size / image_size

            quality_level = self._determine_quality_level(face_ratio)
            quality_score = min(face_ratio * 10, 1.0)

            det_score = float(face.det_score) if hasattr(face, "det_score") else 0.0

            # Filtrar por qualidade
            quality_order = [
                FaceQuality.REJECTED,
                FaceQuality.POOR,
                FaceQuality.ACCEPTABLE,
                FaceQuality.GOOD,
                FaceQuality.EXCELLENT,
            ]

            if quality_order.index(quality_level) < quality_order.index(min_quality):
                continue

            if det_score < self.MIN_DET_SCORE:
                continue

            landmarks = None
            if hasattr(face, "kps") and face.kps is not None:
                landmarks = face.kps.tolist()

            results.append(
                {
                    "index": i,
                    "embedding": face.embedding.tolist(),
                    "bbox": {
                        "x1": float(bbox[0]),
                        "y1": float(bbox[1]),
                        "x2": float(bbox[2]),
                        "y2": float(bbox[3]),
                    },
                    "quality_score": float(quality_score),
                    "quality_level": quality_level.value,
                    "face_size": face_size,
                    "landmarks": landmarks,
                    "det_score": det_score,
                }
            )

        return results

    def _determine_quality_level(self, face_ratio: float) -> FaceQuality:
        """Determina nivel de qualidade baseado no ratio da face"""
        if face_ratio >= self.QUALITY_EXCELLENT:
            return FaceQuality.EXCELLENT
        elif face_ratio >= self.QUALITY_GOOD:
            return FaceQuality.GOOD
        elif face_ratio >= self.QUALITY_ACCEPTABLE:
            return FaceQuality.ACCEPTABLE
        elif face_ratio >= self.QUALITY_MIN:
            return FaceQuality.POOR
        else:
            return FaceQuality.REJECTED

    def calculate_distance(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calcula distancia euclidiana entre dois embeddings

        Args:
            embedding1: Primeiro embedding
            embedding2: Segundo embedding

        Returns:
            Distancia euclidiana
        """
        return float(np.linalg.norm(np.array(embedding1) - np.array(embedding2)))

    def calculate_cosine_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """
        Calcula similaridade de cosseno entre dois embeddings

        Args:
            embedding1: Primeiro embedding
            embedding2: Segundo embedding

        Returns:
            Similaridade de cosseno (-1 a 1)
        """
        e1 = np.array(embedding1)
        e2 = np.array(embedding2)

        dot_product = np.dot(e1, e2)
        norm1 = np.linalg.norm(e1)
        norm2 = np.linalg.norm(e2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def calculate_similarity(self, distance: float, threshold: float) -> float:
        """
        Converte distancia em score de similaridade (0-1)

        Args:
            distance: Distancia euclidiana
            threshold: Threshold de aceitacao

        Returns:
            Score de similaridade (0-1)
        """
        return float(max(0, 1 - (distance / threshold)))

    def compare_embeddings(
        self, embedding1: List[float], embedding2: List[float], threshold: float
    ) -> Dict:
        """
        Compara dois embeddings

        Args:
            embedding1: Primeiro embedding
            embedding2: Segundo embedding
            threshold: Threshold de aceitacao

        Returns:
            Dict com resultado da comparacao
        """
        distance = self.calculate_distance(embedding1, embedding2)
        similarity = self.calculate_similarity(distance, threshold)
        cosine_sim = self.calculate_cosine_similarity(embedding1, embedding2)
        is_match = distance < threshold

        # Nivel de confianca baseado na distancia
        if distance < threshold * 0.5:
            confidence = "high"
        elif distance < threshold * 0.75:
            confidence = "medium"
        elif distance < threshold:
            confidence = "low"
        else:
            confidence = "no_match"

        return {
            "is_match": is_match,
            "distance": distance,
            "similarity": similarity,
            "cosine_similarity": cosine_sim,
            "threshold": threshold,
            "confidence": confidence,
        }

    def find_best_match(
        self, target_embedding: List[float], candidates: List[Dict], threshold: float
    ) -> Optional[Dict]:
        """
        Encontra o melhor match entre candidatos

        Args:
            target_embedding: Embedding alvo
            candidates: Lista de candidatos com 'embedding' e 'id'
            threshold: Threshold de aceitacao

        Returns:
            Melhor candidato ou None
        """
        best_match = None
        best_distance = float("inf")

        for candidate in candidates:
            if "embedding" not in candidate:
                continue

            distance = self.calculate_distance(target_embedding, candidate["embedding"])

            if distance < threshold and distance < best_distance:
                best_distance = distance
                best_match = {
                    **candidate,
                    "distance": distance,
                    "similarity": self.calculate_similarity(distance, threshold),
                }

        return best_match

    def validate_embedding(self, embedding: List[float]) -> Tuple[bool, str]:
        """
        Valida se um embedding e valido

        Args:
            embedding: Lista de floats

        Returns:
            Tuple (is_valid, message)
        """
        if not embedding:
            return False, "Embedding vazio"

        if len(embedding) != 512:
            return False, f"Tamanho invalido: {len(embedding)} (esperado: 512)"

        # Verificar se e um array de floats
        try:
            arr = np.array(embedding, dtype=np.float32)
        except (ValueError, TypeError):
            return False, "Embedding deve conter apenas numeros"

        # Verificar se nao e tudo zero
        if np.all(arr == 0):
            return False, "Embedding invalido (todos zeros)"

        # Verificar range (embeddings normalizados devem estar entre -1 e 1 na maioria)
        if np.max(np.abs(arr)) > 100:
            return False, "Valores fora do range esperado"

        return True, "Embedding valido"


# Instancia global do servico
face_service = FaceService()
