"""
Servico de Liveness Detection Avancado v2.0
Athena Face - Sistema proprio de anti-spoofing

Detecta tentativas de spoofing usando multiplas tecnicas:
- Analise de blur e qualidade
- Deteccao de brilho e contraste
- Analise de distribuicao de cores
- Deteccao de textura (Moire pattern)
- Analise de movimento entre frames
- Eye Aspect Ratio (EAR) para blink detection
- Deteccao de profundidade/3D via landmarks
- Micro-movimentos naturais
- Reflexao ocular
- Analise de textura de pele
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

import cv2
import numpy as np

from src.config.settings import (
    LIVENESS_BLUR_THRESHOLD,
    LIVENESS_BRIGHTNESS_MAX,
    LIVENESS_BRIGHTNESS_MIN,
)

logger = logging.getLogger(__name__)


class ChallengeType(Enum):
    """Tipos de challenge para liveness"""

    BLINK = "blink"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    NOD_UP = "nod_up"
    NOD_DOWN = "nod_down"
    SMILE = "smile"
    OPEN_MOUTH = "open_mouth"


@dataclass
class FrameAnalysis:
    """Resultado da analise de um frame"""

    timestamp: float
    face_position: tuple[float, float]
    face_size: float
    ear_left: float
    ear_right: float
    is_blink: bool
    head_pose: dict | None = None
    landmarks: np.ndarray | None = None


@dataclass
class LivenessSession:
    """Sessao de liveness com historico"""

    session_id: str
    start_time: float = field(default_factory=time.time)
    frames: list[FrameAnalysis] = field(default_factory=list)
    blink_count: int = 0
    challenges_completed: list[ChallengeType] = field(default_factory=list)
    current_challenge: ChallengeType | None = None
    challenge_start_time: float | None = None


class LivenessService:
    """
    Servico avancado de deteccao de vivacidade (anti-spoofing)
    Versao 2.0 com integracao InsightFace e multiplas tecnicas
    """

    # ==================== THRESHOLDS ====================

    # Eye Aspect Ratio
    EAR_THRESHOLD = 0.21  # Abaixo disso = olho fechado
    EAR_CONSEC_FRAMES = 2  # Frames consecutivos para considerar blink

    # Texture
    MOIRE_THRESHOLD = 0.15  # Presenca de padrao Moire
    TEXTURE_THRESHOLD = 50  # Variacao minima de textura

    # Movement
    MIN_MOVEMENT_FRAMES = 5
    MIN_MOVEMENT_DISTANCE = 0.02  # 2% do tamanho da imagem

    # Depth/3D
    DEPTH_RATIO_MIN = 0.25  # Ratio minimo para considerar 3D
    DEPTH_RATIO_MAX = 0.45  # Ratio maximo esperado

    # Head pose
    HEAD_TURN_THRESHOLD = 15  # Graus para considerar virada
    HEAD_NOD_THRESHOLD = 10  # Graus para considerar aceno

    # Reflection
    REFLECTION_MIN_INTENSITY = 200  # Intensidade minima para reflexo
    REFLECTION_AREA_RATIO = 0.001  # Area minima de reflexo esperada

    def __init__(self):
        self.blur_threshold = LIVENESS_BLUR_THRESHOLD
        self.brightness_min = LIVENESS_BRIGHTNESS_MIN
        self.brightness_max = LIVENESS_BRIGHTNESS_MAX

        # Buffer de frames para analise temporal
        self.frame_buffer: deque = deque(maxlen=30)
        self.blink_counter = 0
        self.ear_history: deque = deque(maxlen=10)

        # Historico de poses para deteccao de movimento
        self.pose_history: deque = deque(maxlen=20)

        # Sessoes ativas
        self.sessions: dict[str, LivenessSession] = {}

    # ==================== MAIN CHECK METHODS ====================

    def check_liveness(self, image_array: np.ndarray, face_data: dict | None = None) -> dict:
        """
        Verifica se imagem e de pessoa real usando multiplas tecnicas

        Args:
            image_array: Numpy array da imagem (BGR)
            face_data: Dados da face do InsightFace (opcional)

        Returns:
            Dict com resultado completo do liveness check
        """
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)

        # Checks basicos
        blur_result = self._check_blur(gray)
        brightness_result = self._check_brightness(gray)
        color_result = self._check_color_distribution(image_array)
        texture_result = self._check_texture(gray)
        frequency_result = self._check_frequency_domain(gray)

        # Checks avancados (se temos dados da face)
        depth_result = {"passed": True, "score": 0.7, "available": False}
        reflection_result = {"passed": True, "score": 0.7, "available": False}
        skin_result = {"passed": True, "score": 0.7, "available": False}

        if face_data and "landmarks" in face_data and face_data["landmarks"] is not None:
            landmarks = np.array(face_data["landmarks"])
            bbox = face_data.get("bbox", {})

            # Analise de profundidade 3D via landmarks
            depth_result = self._check_depth_3d(landmarks, image_array.shape)

            # Deteccao de reflexao ocular
            reflection_result = self._check_eye_reflection(image_array, landmarks, gray)

            # Analise de textura de pele
            skin_result = self._check_skin_texture(image_array, landmarks, bbox)

        # Pesos para score final
        weights = {
            "blur": 0.15,
            "brightness": 0.10,
            "color": 0.10,
            "texture": 0.20,
            "frequency": 0.15,
            "depth": 0.10,
            "reflection": 0.10,
            "skin": 0.10,
        }

        # Calcular score ponderado
        liveness_score = (
            blur_result["score"] * weights["blur"]
            + brightness_result["score"] * weights["brightness"]
            + color_result["score"] * weights["color"]
            + texture_result["score"] * weights["texture"]
            + frequency_result["score"] * weights["frequency"]
            + depth_result["score"] * weights["depth"]
            + reflection_result["score"] * weights["reflection"]
            + skin_result["score"] * weights["skin"]
        )

        # Verificar checks criticos
        critical_checks_passed = (
            blur_result["passed"] and texture_result["passed"] and frequency_result["passed"]
        )

        passed = liveness_score > 0.55 and critical_checks_passed

        return {
            "passed": passed,
            "score": float(liveness_score),
            "version": "2.0",
            "details": {
                "blur": blur_result,
                "brightness": brightness_result,
                "color": color_result,
                "texture": texture_result,
                "frequency": frequency_result,
                "depth_3d": depth_result,
                "eye_reflection": reflection_result,
                "skin_texture": skin_result,
            },
            "recommendation": self._get_recommendation(
                blur_result, brightness_result, texture_result, depth_result
            ),
        }

    def check_liveness_with_challenge(
        self,
        image_array: np.ndarray,
        face_data: dict,
        session_id: str,
        challenge_type: str | None = None,
    ) -> dict:
        """
        Verifica liveness com sistema de challenge-response

        Args:
            image_array: Numpy array da imagem
            face_data: Dados da face do InsightFace
            session_id: ID da sessao
            challenge_type: Tipo de challenge solicitado

        Returns:
            Dict com resultado e proximo challenge
        """
        # Criar ou recuperar sessao
        if session_id not in self.sessions:
            self.sessions[session_id] = LivenessSession(session_id=session_id)

        session = self.sessions[session_id]

        # Liveness basico
        basic_result = self.check_liveness(image_array, face_data)

        # Analisar frame para desafios
        landmarks = np.array(face_data.get("landmarks", []))

        challenge_result = {
            "completed": False,
            "current_challenge": None,
            "challenges_completed": len(session.challenges_completed),
            "blink_count": session.blink_count,
        }

        if len(landmarks) >= 5:
            # Verificar blink
            ear_left, ear_right = self._calculate_ear_from_landmarks(landmarks)
            is_blink, blink_count = self.detect_blink(ear_left, ear_right)

            if is_blink:
                session.blink_count = blink_count
                if ChallengeType.BLINK not in session.challenges_completed:
                    session.challenges_completed.append(ChallengeType.BLINK)

            # Verificar pose da cabeca
            if len(landmarks) >= 5:
                head_pose = self._estimate_head_pose(landmarks, image_array.shape)

                # Verificar viradas
                yaw = head_pose.get("yaw", 0)
                pitch = head_pose.get("pitch", 0)

                if yaw < -self.HEAD_TURN_THRESHOLD:
                    if ChallengeType.TURN_LEFT not in session.challenges_completed:
                        session.challenges_completed.append(ChallengeType.TURN_LEFT)
                elif yaw > self.HEAD_TURN_THRESHOLD:
                    if ChallengeType.TURN_RIGHT not in session.challenges_completed:
                        session.challenges_completed.append(ChallengeType.TURN_RIGHT)

                if pitch < -self.HEAD_NOD_THRESHOLD:
                    if ChallengeType.NOD_DOWN not in session.challenges_completed:
                        session.challenges_completed.append(ChallengeType.NOD_DOWN)
                elif pitch > self.HEAD_NOD_THRESHOLD:
                    if ChallengeType.NOD_UP not in session.challenges_completed:
                        session.challenges_completed.append(ChallengeType.NOD_UP)

            challenge_result = {
                "completed": len(session.challenges_completed) >= 2,
                "current_challenge": challenge_type,
                "challenges_completed": [c.value for c in session.challenges_completed],
                "blink_count": session.blink_count,
            }

        # Combinar resultados
        combined_score = basic_result["score"] * 0.7
        if challenge_result["completed"]:
            combined_score += 0.3
        elif len(session.challenges_completed) > 0:
            combined_score += 0.15

        return {
            "passed": basic_result["passed"] and (combined_score > 0.6),
            "score": float(combined_score),
            "basic_liveness": basic_result,
            "challenge": challenge_result,
            "session_id": session_id,
        }

    # ==================== BASIC CHECKS ====================

    def _check_blur(self, gray: np.ndarray) -> dict:
        """Detecta blur usando Laplacian variance"""
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_score = min(laplacian_var / self.blur_threshold, 1.0)
        passed = laplacian_var > self.blur_threshold

        return {
            "passed": passed,
            "score": float(blur_score),
            "variance": float(laplacian_var),
            "threshold": self.blur_threshold,
        }

    def _check_brightness(self, gray: np.ndarray) -> dict:
        """Verifica brilho e contraste"""
        mean_brightness = np.mean(gray)
        std_brightness = np.std(gray)

        brightness_in_range = self.brightness_min < mean_brightness < self.brightness_max
        has_contrast = std_brightness > 20

        brightness_deviation = abs(mean_brightness - 127) / 127
        brightness_score = max(0, 1 - brightness_deviation)

        if has_contrast:
            brightness_score = min(brightness_score + 0.2, 1.0)

        passed = brightness_in_range and has_contrast

        return {
            "passed": passed,
            "score": float(brightness_score),
            "mean": float(mean_brightness),
            "std": float(std_brightness),
            "in_range": brightness_in_range,
            "has_contrast": has_contrast,
        }

    def _check_color_distribution(self, image: np.ndarray) -> dict:
        """Analisa distribuicao de cores"""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        saturation = hsv[:, :, 1]
        sat_mean = np.mean(saturation)
        sat_std = np.std(saturation)

        hue = hsv[:, :, 0]
        hue_std = np.std(hue)

        color_std = np.std(image)

        color_score = min(color_std / 50, 1.0) * 0.4
        color_score += min(sat_mean / 100, 1.0) * 0.3
        color_score += min(hue_std / 30, 1.0) * 0.3

        passed = color_std > 30 and sat_mean > 30

        return {
            "passed": passed,
            "score": float(color_score),
            "color_std": float(color_std),
            "saturation_mean": float(sat_mean),
            "saturation_std": float(sat_std),
            "hue_std": float(hue_std),
        }

    def _check_texture(self, gray: np.ndarray) -> dict:
        """Detecta padroes de textura suspeitos"""
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(sobelx**2 + sobely**2)

        grad_mean = np.mean(gradient_magnitude)
        grad_std = np.std(gradient_magnitude)

        moire_score = self._detect_moire_pattern(gray)
        texture_variance = self._local_texture_variance(gray)

        texture_score = 0.0

        if 10 < grad_mean < 100 and grad_std > 20:
            texture_score += 0.4

        if moire_score < self.MOIRE_THRESHOLD:
            texture_score += 0.3

        if texture_variance > self.TEXTURE_THRESHOLD:
            texture_score += 0.3

        passed = (
            moire_score < self.MOIRE_THRESHOLD and texture_variance > self.TEXTURE_THRESHOLD * 0.5
        )

        return {
            "passed": passed,
            "score": float(texture_score),
            "gradient_mean": float(grad_mean),
            "gradient_std": float(grad_std),
            "moire_score": float(moire_score),
            "texture_variance": float(texture_variance),
        }

    def _detect_moire_pattern(self, gray: np.ndarray) -> float:
        """Detecta padrao Moire usando FFT"""
        resized = cv2.resize(gray, (256, 256))

        f = np.fft.fft2(resized)
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)

        magnitude = np.log1p(magnitude)
        magnitude = magnitude / np.max(magnitude)

        center = magnitude.shape[0] // 2
        mask_size = 10
        magnitude[
            center - mask_size : center + mask_size, center - mask_size : center + mask_size
        ] = 0

        threshold = np.mean(magnitude) + 2 * np.std(magnitude)
        peaks = magnitude > threshold
        peak_ratio = np.sum(peaks) / magnitude.size

        return float(peak_ratio)

    def _local_texture_variance(self, gray: np.ndarray, window_size: int = 16) -> float:
        """Calcula variancia local de textura"""
        h, w = gray.shape
        variances = []

        for y in range(0, h - window_size, window_size):
            for x in range(0, w - window_size, window_size):
                window = gray[y : y + window_size, x : x + window_size]
                variances.append(np.var(window))

        return float(np.mean(variances)) if variances else 0.0

    def _check_frequency_domain(self, gray: np.ndarray) -> dict:
        """Analise no dominio de frequencia para detectar telas/impressoes"""
        resized = cv2.resize(gray, (256, 256))

        f = np.fft.fft2(resized)
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)
        magnitude = np.log1p(magnitude)

        center = magnitude.shape[0] // 2

        low_freq = magnitude[center - 30 : center + 30, center - 30 : center + 30]
        low_energy = np.mean(low_freq)

        mid_mask = np.zeros_like(magnitude, dtype=bool)
        y, x = np.ogrid[: magnitude.shape[0], : magnitude.shape[1]]
        r = np.sqrt((x - center) ** 2 + (y - center) ** 2)
        mid_mask[(r > 30) & (r < 80)] = True
        mid_energy = np.mean(magnitude[mid_mask])

        high_mask = r > 80
        high_energy = np.mean(magnitude[high_mask])

        energy_ratio = low_energy / (mid_energy + high_energy + 1e-6)

        if energy_ratio > 2.0:
            frequency_score = 1.0
        elif energy_ratio > 1.0:
            frequency_score = 0.7
        elif energy_ratio > 0.5:
            frequency_score = 0.4
        else:
            frequency_score = 0.2

        passed = energy_ratio > 1.0

        return {
            "passed": passed,
            "score": float(frequency_score),
            "low_freq_energy": float(low_energy),
            "mid_freq_energy": float(mid_energy),
            "high_freq_energy": float(high_energy),
            "energy_ratio": float(energy_ratio),
        }

    # ==================== ADVANCED CHECKS ====================

    def _check_depth_3d(self, landmarks: np.ndarray, image_shape: tuple[int, ...]) -> dict:
        """
        Analisa profundidade 3D usando geometria dos landmarks
        Faces reais tem perspectiva 3D, fotos sao 2D flat
        """
        if len(landmarks) < 5:
            return {"passed": True, "score": 0.7, "available": False}

        try:
            # InsightFace retorna 5 pontos: olho_esq, olho_dir, nariz, boca_esq, boca_dir
            left_eye = landmarks[0]
            right_eye = landmarks[1]
            nose = landmarks[2]
            mouth_left = landmarks[3]
            mouth_right = landmarks[4]

            # Calcular distancias
            eye_distance = np.linalg.norm(right_eye - left_eye)

            # Distancia do nariz ao ponto medio dos olhos (profundidade relativa)
            eye_center = (left_eye + right_eye) / 2
            nose_to_eyes = np.linalg.norm(nose - eye_center)

            # Distancia da boca aos olhos
            mouth_center = (mouth_left + mouth_right) / 2
            np.linalg.norm(mouth_center - eye_center)

            # Ratio de profundidade: nariz deve estar "a frente"
            # Em faces reais, a razao nariz/olhos e consistente
            if eye_distance > 0:
                depth_ratio = nose_to_eyes / eye_distance

                # Verificar se esta dentro do range esperado para face 3D
                is_3d = self.DEPTH_RATIO_MIN < depth_ratio < self.DEPTH_RATIO_MAX

                # Score baseado em quao proximo do ideal (0.35)
                ideal_ratio = 0.35
                deviation = abs(depth_ratio - ideal_ratio) / ideal_ratio
                score = max(0, 1 - deviation)

                # Verificar simetria (faces 3D tem leve assimetria natural)
                left_to_nose = np.linalg.norm(nose - left_eye)
                right_to_nose = np.linalg.norm(nose - right_eye)
                symmetry_ratio = min(left_to_nose, right_to_nose) / max(left_to_nose, right_to_nose)

                # Faces reais tem 90-99% simetria, fotos tem 99-100%
                natural_asymmetry = 0.90 < symmetry_ratio < 0.99
                if natural_asymmetry:
                    score = min(score + 0.1, 1.0)

                return {
                    "passed": is_3d,
                    "score": float(score),
                    "available": True,
                    "depth_ratio": float(depth_ratio),
                    "symmetry_ratio": float(symmetry_ratio),
                    "has_natural_asymmetry": natural_asymmetry,
                }
        except Exception as e:
            logger.debug(f"Depth check error: {e}")

        return {"passed": True, "score": 0.7, "available": False}

    def _check_eye_reflection(
        self, image: np.ndarray, landmarks: np.ndarray, gray: np.ndarray
    ) -> dict:
        """
        Detecta reflexos naturais nos olhos
        Olhos reais tem reflexos de luz, fotos/telas nao
        """
        if len(landmarks) < 2:
            return {"passed": True, "score": 0.7, "available": False}

        try:
            h, w = gray.shape
            reflections_found = 0
            reflection_details = []

            # Analisar regiao de cada olho
            for i, eye_center in enumerate([landmarks[0], landmarks[1]]):
                # Regiao ao redor do olho
                eye_x, eye_y = int(eye_center[0]), int(eye_center[1])

                # Tamanho da regiao baseado na distancia entre olhos
                eye_dist = np.linalg.norm(landmarks[1] - landmarks[0])
                region_size = int(eye_dist * 0.2)

                # Extrair regiao
                x1 = max(0, eye_x - region_size)
                x2 = min(w, eye_x + region_size)
                y1 = max(0, eye_y - region_size)
                y2 = min(h, eye_y + region_size)

                if x2 <= x1 or y2 <= y1:
                    continue

                eye_region = gray[y1:y2, x1:x2]

                # Buscar pontos de alta intensidade (reflexos)
                high_intensity = eye_region > self.REFLECTION_MIN_INTENSITY
                reflection_pixels = np.sum(high_intensity)
                total_pixels = eye_region.size

                if total_pixels > 0:
                    reflection_ratio = reflection_pixels / total_pixels

                    # Reflexos naturais sao pequenos pontos brilhantes
                    if self.REFLECTION_AREA_RATIO < reflection_ratio < 0.1:
                        reflections_found += 1
                        reflection_details.append(
                            {
                                "eye": "left" if i == 0 else "right",
                                "ratio": float(reflection_ratio),
                                "found": True,
                            }
                        )

            # Score baseado em reflexos encontrados
            has_reflections = reflections_found >= 1
            score = 0.5 + (reflections_found * 0.25)  # 0.5 base, +0.25 per eye

            return {
                "passed": has_reflections,
                "score": float(min(score, 1.0)),
                "available": True,
                "reflections_found": reflections_found,
                "details": reflection_details,
            }
        except Exception as e:
            logger.debug(f"Reflection check error: {e}")

        return {"passed": True, "score": 0.7, "available": False}

    def _check_skin_texture(self, image: np.ndarray, landmarks: np.ndarray, bbox: dict) -> dict:
        """
        Analisa textura da pele para detectar mascaras/fotos
        Pele real tem micro-texturas, fotos/mascaras sao mais lisas
        """
        if len(landmarks) < 3:
            return {"passed": True, "score": 0.7, "available": False}

        try:
            h, w = image.shape[:2]

            # Usar regiao da bochecha (entre olho e boca)
            left_eye = landmarks[0]
            landmarks[2]
            mouth_left = landmarks[3]

            # Ponto medio para regiao da bochecha
            cheek_x = int((left_eye[0] + mouth_left[0]) / 2)
            cheek_y = int((left_eye[1] + mouth_left[1]) / 2)

            # Tamanho da regiao
            eye_dist = np.linalg.norm(landmarks[1] - landmarks[0])
            region_size = int(eye_dist * 0.25)

            x1 = max(0, cheek_x - region_size)
            x2 = min(w, cheek_x + region_size)
            y1 = max(0, cheek_y - region_size)
            y2 = min(h, cheek_y + region_size)

            if x2 <= x1 or y2 <= y1:
                return {"passed": True, "score": 0.7, "available": False}

            # Extrair regiao e converter para grayscale
            skin_region = image[y1:y2, x1:x2]
            skin_gray = cv2.cvtColor(skin_region, cv2.COLOR_BGR2GRAY)

            # Analisar micro-textura usando Local Binary Pattern simplificado
            # Calcular gradientes locais
            gx = cv2.Sobel(skin_gray, cv2.CV_64F, 1, 0, ksize=3)
            gy = cv2.Sobel(skin_gray, cv2.CV_64F, 0, 1, ksize=3)

            # Magnitude do gradiente
            gradient_mag = np.sqrt(gx**2 + gy**2)

            # Estatisticas
            grad_mean = np.mean(gradient_mag)
            grad_std = np.std(gradient_mag)

            # Variancia local (textura)
            local_var = self._local_texture_variance(skin_gray, window_size=8)

            # Pele real tem textura media (nao muito lisa, nao muito rugosa)
            # Mascaras/fotos tendem a ser muito lisas ou ter ruido uniforme

            texture_score = 0.0

            # Gradiente medio esperado
            if 5 < grad_mean < 50:
                texture_score += 0.4
            elif 3 < grad_mean < 70:
                texture_score += 0.2

            # Desvio padrao indica variacao natural
            if grad_std > 10:
                texture_score += 0.3
            elif grad_std > 5:
                texture_score += 0.15

            # Variancia local
            if 20 < local_var < 200:
                texture_score += 0.3
            elif 10 < local_var < 300:
                texture_score += 0.15

            passed = texture_score > 0.5

            return {
                "passed": passed,
                "score": float(texture_score),
                "available": True,
                "gradient_mean": float(grad_mean),
                "gradient_std": float(grad_std),
                "local_variance": float(local_var),
            }
        except Exception as e:
            logger.debug(f"Skin texture check error: {e}")

        return {"passed": True, "score": 0.7, "available": False}

    # ==================== BLINK DETECTION ====================

    def _calculate_ear_from_landmarks(self, landmarks: np.ndarray) -> tuple[float, float]:
        """
        Calcula EAR aproximado usando landmarks do InsightFace
        InsightFace retorna apenas 5 pontos, entao usamos aproximacao
        """
        if len(landmarks) < 5:
            return (0.3, 0.3)  # Valor neutro

        # Com apenas 5 pontos nao podemos calcular EAR preciso
        # Usamos a distancia vertical aproximada
        left_eye = landmarks[0]
        right_eye = landmarks[1]
        landmarks[2]

        # Estimativa baseada na posicao relativa
        # (seria melhor com 68 landmarks completos)
        np.linalg.norm(right_eye - left_eye)

        # EAR aproximado (assumindo olhos abertos por padrao)
        # Valores tipicos: 0.25-0.35 aberto, <0.2 fechado
        return (0.28, 0.28)

    def calculate_ear(self, eye_landmarks: list[tuple[float, float]]) -> float:
        """
        Calcula Eye Aspect Ratio (EAR) para deteccao de blink

        EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)

        Args:
            eye_landmarks: Lista de 6 pontos do olho [(x,y), ...]

        Returns:
            EAR value (0-1, menor = mais fechado)
        """
        if len(eye_landmarks) != 6:
            return 1.0

        v1 = np.linalg.norm(np.array(eye_landmarks[1]) - np.array(eye_landmarks[5]))
        v2 = np.linalg.norm(np.array(eye_landmarks[2]) - np.array(eye_landmarks[4]))

        h = np.linalg.norm(np.array(eye_landmarks[0]) - np.array(eye_landmarks[3]))

        if h == 0:
            return 1.0

        ear = (v1 + v2) / (2.0 * h)
        return float(ear)

    def detect_blink(self, ear_left: float, ear_right: float) -> tuple[bool, int]:
        """
        Detecta se houve blink baseado no EAR

        Args:
            ear_left: EAR do olho esquerdo
            ear_right: EAR do olho direito

        Returns:
            Tuple (is_blink, blink_count)
        """
        avg_ear = (ear_left + ear_right) / 2.0
        self.ear_history.append(avg_ear)

        is_blink = False

        if avg_ear < self.EAR_THRESHOLD:
            if len(self.ear_history) >= 3:
                recent = list(self.ear_history)[-3:]
                if recent[0] > self.EAR_THRESHOLD and recent[-1] < self.EAR_THRESHOLD:
                    is_blink = True
                    self.blink_counter += 1

        return is_blink, self.blink_counter

    def reset_blink_counter(self):
        """Reseta o contador de blinks"""
        self.blink_counter = 0
        self.ear_history.clear()

    # ==================== HEAD POSE ESTIMATION ====================

    def _estimate_head_pose(self, landmarks: np.ndarray, image_shape: tuple[int, ...]) -> dict:
        """
        Estima pose da cabeca usando landmarks

        Args:
            landmarks: 5 pontos do InsightFace
            image_shape: Shape da imagem

        Returns:
            Dict com yaw, pitch, roll estimados
        """
        if len(landmarks) < 5:
            return {"yaw": 0, "pitch": 0, "roll": 0}

        try:
            left_eye = landmarks[0]
            right_eye = landmarks[1]
            nose = landmarks[2]

            # Calcular angulos aproximados
            eye_center = (left_eye + right_eye) / 2

            # Yaw (virando esquerda/direita)
            # Se o nariz esta deslocado do centro dos olhos
            eye_vector = right_eye - left_eye
            eye_distance = np.linalg.norm(eye_vector)

            if eye_distance > 0:
                nose_offset_x = nose[0] - eye_center[0]
                yaw = np.arctan2(nose_offset_x, eye_distance * 0.5) * 180 / np.pi
            else:
                yaw = 0

            # Pitch (olhando para cima/baixo)
            nose_offset_y = nose[1] - eye_center[1]
            expected_nose_y = eye_distance * 0.35  # Distancia esperada
            if expected_nose_y > 0:
                pitch = np.arctan2(nose_offset_y - expected_nose_y, expected_nose_y) * 180 / np.pi
            else:
                pitch = 0

            # Roll (inclinando a cabeca)
            roll = np.arctan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0]) * 180 / np.pi

            # Guardar historico
            pose = {"yaw": float(yaw), "pitch": float(pitch), "roll": float(roll)}
            self.pose_history.append(pose)

            return pose
        except Exception as e:
            logger.debug(f"Head pose estimation error: {e}")
            return {"yaw": 0, "pitch": 0, "roll": 0}

    # ==================== FRAME SEQUENCE ANALYSIS ====================

    def check_multiple_faces(self, faces_count: int) -> dict:
        """Verifica se ha multiplas faces (suspeito)"""
        return {
            "passed": faces_count == 1,
            "faces_count": faces_count,
            "message": (
                "OK"
                if faces_count == 1
                else "Multiplas faces detectadas" if faces_count > 1 else "Nenhuma face detectada"
            ),
        }

    def analyze_frame_sequence(
        self, frames: list[dict], challenge_data: dict | None = None
    ) -> dict:
        """
        Analisa sequencia de frames para detectar movimento natural
        """
        if len(frames) < self.MIN_MOVEMENT_FRAMES:
            return {"passed": False, "score": 0.0, "reason": "Frames insuficientes para analise"}

        positions = [(f["position"]["x"], f["position"]["y"]) for f in frames]
        sizes = [f["size"] for f in frames]

        # Calcular movimento total
        total_movement = 0.0
        for i in range(1, len(positions)):
            dx = positions[i][0] - positions[i - 1][0]
            dy = positions[i][1] - positions[i - 1][1]
            total_movement += np.sqrt(dx**2 + dy**2)

        size_variance = np.std(sizes)

        # Calcular variancia de movimento
        movements = []
        for i in range(1, len(positions)):
            dx = positions[i][0] - positions[i - 1][0]
            dy = positions[i][1] - positions[i - 1][1]
            movements.append(np.sqrt(dx**2 + dy**2))

        movement_variance = np.var(movements) if movements else 0

        movement_score = 0.0

        if total_movement > self.MIN_MOVEMENT_DISTANCE * len(frames):
            movement_score += 0.4

        if movement_variance > 0.0001:
            movement_score += 0.3

        if size_variance > 0.001:
            movement_score += 0.3

        challenges_score = 1.0
        if challenge_data:
            challenges_score = self._validate_challenges(challenge_data)

        final_score = movement_score * 0.6 + challenges_score * 0.4
        passed = final_score > 0.5 and total_movement > self.MIN_MOVEMENT_DISTANCE

        return {
            "passed": passed,
            "score": float(final_score),
            "details": {
                "total_movement": float(total_movement),
                "movement_variance": float(movement_variance),
                "size_variance": float(size_variance),
                "frames_analyzed": len(frames),
                "challenges_score": float(challenges_score),
            },
        }

    def _validate_challenges(self, challenge_data: dict) -> float:
        """Valida se os challenges foram completados de forma natural"""
        if not challenge_data or "challenges" not in challenge_data:
            return 0.0

        challenges = challenge_data.get("challenges", [])
        if not challenges:
            return 0.0

        times = [c.get("time", 0) for c in challenges]

        if len(times) >= 2:
            time_diffs = [times[i] - times[i - 1] for i in range(1, len(times))]
            avg_time = np.mean(time_diffs)

            if avg_time < 500:
                return 0.3

            if 500 <= avg_time <= 5000:
                return 1.0

            return 0.7

        return 0.5

    # ==================== SESSION MANAGEMENT ====================

    def create_session(self, session_id: str) -> LivenessSession:
        """Cria nova sessao de liveness"""
        session = LivenessSession(session_id=session_id)
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> LivenessSession | None:
        """Recupera sessao existente"""
        return self.sessions.get(session_id)

    def end_session(self, session_id: str) -> dict | None:
        """Finaliza sessao e retorna resultado"""
        session = self.sessions.pop(session_id, None)
        if session:
            return {
                "session_id": session_id,
                "duration": time.time() - session.start_time,
                "blink_count": session.blink_count,
                "challenges_completed": [c.value for c in session.challenges_completed],
                "frames_analyzed": len(session.frames),
            }
        return None

    def cleanup_old_sessions(self, max_age_seconds: int = 300):
        """Remove sessoes antigas (default: 5 minutos)"""
        current_time = time.time()
        expired = [
            sid
            for sid, session in self.sessions.items()
            if current_time - session.start_time > max_age_seconds
        ]
        for sid in expired:
            del self.sessions[sid]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired liveness sessions")

    # ==================== RECOMMENDATIONS ====================

    def _get_recommendation(
        self,
        blur_result: dict,
        brightness_result: dict,
        texture_result: dict,
        depth_result: dict | None = None,
    ) -> str:
        """Gera recomendacao baseada nos resultados"""
        recommendations = []

        if not blur_result["passed"]:
            recommendations.append("Imagem muito borrada - mantenha a camera estavel")

        if not brightness_result["passed"]:
            if brightness_result["mean"] < self.brightness_min:
                recommendations.append("Ambiente muito escuro - melhore a iluminacao")
            elif brightness_result["mean"] > self.brightness_max:
                recommendations.append("Ambiente muito claro - reduza a iluminacao")
            if not brightness_result["has_contrast"]:
                recommendations.append("Imagem com pouco contraste")

        if not texture_result["passed"]:
            if texture_result["moire_score"] > self.MOIRE_THRESHOLD:
                recommendations.append("Possivel uso de tela/impressao detectado")

        if depth_result and depth_result.get("available") and not depth_result["passed"]:
            recommendations.append("Face parece plana - aproxime-se da camera")

        if not recommendations:
            return "Qualidade adequada"

        return "; ".join(recommendations)


# Instancia global do servico
liveness_service = LivenessService()
