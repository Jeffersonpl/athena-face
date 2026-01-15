"""
Testes unitarios para o LivenessService
"""

import cv2
import numpy as np
import pytest

from src.services.liveness_service import LivenessService


class TestLivenessService:
    """Testes para LivenessService"""

    @pytest.fixture
    def service(self):
        """Cria instancia do servico para testes"""
        return LivenessService()

    @pytest.fixture
    def real_face_image(self):
        """
        Cria uma imagem simulando uma face real.
        Imagem colorida com boa variacao de textura e cor.
        """
        # Criar imagem com variacao de cor e textura
        img = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)

        # Adicionar gradiente para simular iluminacao natural
        for i in range(480):
            img[i, :, :] = img[i, :, :] * (0.7 + 0.3 * (i / 480))

        # Adicionar ruido para textura
        noise = np.random.normal(0, 15, img.shape).astype(np.int8)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        return img

    @pytest.fixture
    def blurry_image(self):
        """Cria uma imagem borrada"""
        img = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
        # Aplicar blur forte
        img = cv2.GaussianBlur(img, (31, 31), 0)
        return img

    @pytest.fixture
    def dark_image(self):
        """Cria uma imagem muito escura"""
        return np.random.randint(0, 30, (480, 640, 3), dtype=np.uint8)

    @pytest.fixture
    def bright_image(self):
        """Cria uma imagem muito clara"""
        return np.random.randint(220, 255, (480, 640, 3), dtype=np.uint8)

    @pytest.fixture
    def low_color_image(self):
        """Cria uma imagem com pouca variacao de cor (simula foto impressa)"""
        # Imagem quase monocromatica
        base_color = np.array([120, 120, 120], dtype=np.uint8)
        img = np.tile(base_color, (480, 640, 1))
        # Adicionar pequena variacao
        noise = np.random.randint(-5, 5, (480, 640, 3), dtype=np.int8)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        return img

    # ==================== Testes de Blur ====================

    def test_check_blur_good_image(self, service, real_face_image):
        """Testa deteccao de blur em imagem nitida"""
        gray = cv2.cvtColor(real_face_image, cv2.COLOR_BGR2GRAY)
        result = service._check_blur(gray)

        assert result["passed"] is True
        assert result["score"] > 0.5
        assert result["variance"] > service.blur_threshold

    def test_check_blur_blurry_image(self, service, blurry_image):
        """Testa deteccao de blur em imagem borrada"""
        gray = cv2.cvtColor(blurry_image, cv2.COLOR_BGR2GRAY)
        result = service._check_blur(gray)

        assert result["passed"] is False
        assert result["score"] < 0.5

    # ==================== Testes de Brilho ====================

    def test_check_brightness_good_image(self, service, real_face_image):
        """Testa verificacao de brilho em imagem bem iluminada"""
        gray = cv2.cvtColor(real_face_image, cv2.COLOR_BGR2GRAY)
        result = service._check_brightness(gray)

        assert result["passed"] is True
        assert result["in_range"] is True
        assert result["has_contrast"] is True

    def test_check_brightness_dark_image(self, service, dark_image):
        """Testa verificacao de brilho em imagem escura"""
        gray = cv2.cvtColor(dark_image, cv2.COLOR_BGR2GRAY)
        result = service._check_brightness(gray)

        assert result["passed"] is False
        assert result["mean"] < service.brightness_min

    def test_check_brightness_bright_image(self, service, bright_image):
        """Testa verificacao de brilho em imagem muito clara"""
        gray = cv2.cvtColor(bright_image, cv2.COLOR_BGR2GRAY)
        result = service._check_brightness(gray)

        assert result["passed"] is False
        assert result["mean"] > service.brightness_max

    # ==================== Testes de Cor ====================

    def test_check_color_distribution_good_image(self, service, real_face_image):
        """Testa distribuicao de cores em imagem real"""
        result = service._check_color_distribution(real_face_image)

        assert result["passed"] is True
        assert result["score"] > 0.5
        assert result["color_std"] > 30

    def test_check_color_distribution_low_color(self, service, low_color_image):
        """Testa distribuicao de cores em imagem com pouca variacao"""
        result = service._check_color_distribution(low_color_image)

        assert result["passed"] is False
        assert result["color_std"] < 30

    # ==================== Testes de Textura ====================

    def test_check_texture_good_image(self, service, real_face_image):
        """Testa analise de textura em imagem real"""
        gray = cv2.cvtColor(real_face_image, cv2.COLOR_BGR2GRAY)
        result = service._check_texture(gray)

        assert result["passed"] is True
        assert result["moire_score"] < service.MOIRE_THRESHOLD

    def test_detect_moire_pattern(self, service, real_face_image):
        """Testa deteccao de padrao Moire"""
        gray = cv2.cvtColor(real_face_image, cv2.COLOR_BGR2GRAY)
        moire_score = service._detect_moire_pattern(gray)

        assert 0 <= moire_score <= 1
        assert moire_score < service.MOIRE_THRESHOLD

    # ==================== Testes de Frequencia ====================

    def test_check_frequency_domain_good_image(self, service, real_face_image):
        """Testa analise de frequencia em imagem real"""
        gray = cv2.cvtColor(real_face_image, cv2.COLOR_BGR2GRAY)
        result = service._check_frequency_domain(gray)

        assert "low_freq_energy" in result
        assert "mid_freq_energy" in result
        assert "high_freq_energy" in result
        assert "energy_ratio" in result

    # ==================== Testes de Liveness Completo ====================

    def test_check_liveness_good_image(self, service, real_face_image):
        """Testa verificacao completa de liveness em imagem real"""
        result = service.check_liveness(real_face_image)

        assert "passed" in result
        assert "score" in result
        assert "details" in result
        assert "recommendation" in result

        assert 0 <= result["score"] <= 1

        # Verificar detalhes
        details = result["details"]
        assert "blur" in details
        assert "brightness" in details
        assert "color" in details
        assert "texture" in details
        assert "frequency" in details

    def test_check_liveness_blurry_image(self, service, blurry_image):
        """Testa que imagem borrada falha no liveness"""
        result = service.check_liveness(blurry_image)

        assert result["passed"] is False
        assert result["details"]["blur"]["passed"] is False

    # ==================== Testes de Multiplas Faces ====================

    def test_check_multiple_faces_one_face(self, service):
        """Testa verificacao com uma face"""
        result = service.check_multiple_faces(1)

        assert result["passed"] is True
        assert result["faces_count"] == 1
        assert result["message"] == "OK"

    def test_check_multiple_faces_many_faces(self, service):
        """Testa verificacao com multiplas faces"""
        result = service.check_multiple_faces(3)

        assert result["passed"] is False
        assert result["faces_count"] == 3
        assert "Multiplas" in result["message"]

    def test_check_multiple_faces_no_face(self, service):
        """Testa verificacao sem faces"""
        result = service.check_multiple_faces(0)

        assert result["passed"] is False
        assert result["faces_count"] == 0
        assert "Nenhuma" in result["message"]

    # ==================== Testes de Frame Sequence ====================

    def test_analyze_frame_sequence_insufficient_frames(self, service):
        """Testa analise com frames insuficientes"""
        frames = [
            {"position": {"x": 0.5, "y": 0.5}, "size": 0.1, "time": 0},
            {"position": {"x": 0.5, "y": 0.5}, "size": 0.1, "time": 100},
        ]

        result = service.analyze_frame_sequence(frames)

        assert result["passed"] is False
        assert "insuficientes" in result.get("reason", "").lower()

    def test_analyze_frame_sequence_with_movement(self, service):
        """Testa analise com movimento natural"""
        frames = [
            {"position": {"x": 0.5, "y": 0.5}, "size": 0.1, "time": 0},
            {"position": {"x": 0.52, "y": 0.48}, "size": 0.11, "time": 100},
            {"position": {"x": 0.48, "y": 0.52}, "size": 0.10, "time": 200},
            {"position": {"x": 0.55, "y": 0.45}, "size": 0.12, "time": 300},
            {"position": {"x": 0.50, "y": 0.50}, "size": 0.11, "time": 400},
            {"position": {"x": 0.45, "y": 0.55}, "size": 0.10, "time": 500},
        ]

        result = service.analyze_frame_sequence(frames)

        assert "score" in result
        assert "details" in result
        assert result["details"]["frames_analyzed"] == 6

    # ==================== Testes de EAR (Eye Aspect Ratio) ====================

    def test_calculate_ear_open_eye(self, service):
        """Testa calculo de EAR para olho aberto"""
        # Landmarks simulando olho aberto (formato horizontal alongado)
        eye_landmarks = [
            (0.0, 0.5),  # p1 - canto esquerdo
            (0.2, 0.3),  # p2 - superior esquerdo
            (0.4, 0.3),  # p3 - superior direito
            (0.6, 0.5),  # p4 - canto direito
            (0.4, 0.7),  # p5 - inferior direito
            (0.2, 0.7),  # p6 - inferior esquerdo
        ]

        ear = service.calculate_ear(eye_landmarks)

        assert 0 < ear < 1
        assert ear > service.EAR_THRESHOLD  # Olho aberto

    def test_calculate_ear_closed_eye(self, service):
        """Testa calculo de EAR para olho fechado"""
        # Landmarks simulando olho fechado (muito achatado)
        eye_landmarks = [
            (0.0, 0.5),  # p1 - canto esquerdo
            (0.2, 0.48),  # p2 - superior esquerdo
            (0.4, 0.48),  # p3 - superior direito
            (0.6, 0.5),  # p4 - canto direito
            (0.4, 0.52),  # p5 - inferior direito
            (0.2, 0.52),  # p6 - inferior esquerdo
        ]

        ear = service.calculate_ear(eye_landmarks)

        assert ear < service.EAR_THRESHOLD  # Olho fechado

    def test_calculate_ear_invalid_landmarks(self, service):
        """Testa calculo de EAR com landmarks invalidos"""
        # Apenas 3 pontos (invalido)
        eye_landmarks = [
            (0.0, 0.5),
            (0.3, 0.3),
            (0.6, 0.5),
        ]

        ear = service.calculate_ear(eye_landmarks)

        assert ear == 1.0  # Valor padrao para landmarks invalidos

    # ==================== Testes de Blink Detection ====================

    def test_detect_blink_sequence(self, service):
        """Testa deteccao de blink em sequencia"""
        service.reset_blink_counter()

        # Simular sequencia: aberto -> aberto -> fechado -> aberto
        ear_sequence = [0.3, 0.32, 0.15, 0.31]

        blinks_detected = 0
        for ear in ear_sequence:
            is_blink, count = service.detect_blink(ear, ear)
            if is_blink:
                blinks_detected += 1

        # Deve detectar pelo menos 1 blink
        assert service.blink_counter >= 1

    def test_reset_blink_counter(self, service):
        """Testa reset do contador de blinks"""
        service.blink_counter = 5
        service.ear_history.append(0.3)

        service.reset_blink_counter()

        assert service.blink_counter == 0
        assert len(service.ear_history) == 0

    # ==================== Testes de Validacao de Challenges ====================

    def test_validate_challenges_normal_timing(self, service):
        """Testa validacao de challenges com timing normal"""
        challenge_data = {
            "challenges": [
                {"time": 0},
                {"time": 1500},
                {"time": 3000},
                {"time": 4500},
            ]
        }

        score = service._validate_challenges(challenge_data)

        assert score == 1.0  # Tempo normal

    def test_validate_challenges_too_fast(self, service):
        """Testa validacao de challenges muito rapidos"""
        challenge_data = {
            "challenges": [
                {"time": 0},
                {"time": 100},
                {"time": 200},
                {"time": 300},
            ]
        }

        score = service._validate_challenges(challenge_data)

        assert score == 0.3  # Suspeito - muito rapido

    def test_validate_challenges_empty(self, service):
        """Testa validacao sem challenges"""
        score = service._validate_challenges({})
        assert score == 0.0

        score = service._validate_challenges(None)
        assert score == 0.0

    # ==================== Testes de Recomendacao ====================

    def test_get_recommendation_good(self, service):
        """Testa recomendacao para resultados bons"""
        blur_result = {"passed": True}
        brightness_result = {"passed": True, "mean": 127, "has_contrast": True}
        texture_result = {"passed": True, "moire_score": 0.05}

        recommendation = service._get_recommendation(blur_result, brightness_result, texture_result)

        assert recommendation == "Qualidade adequada"

    def test_get_recommendation_blur_issue(self, service):
        """Testa recomendacao para problema de blur"""
        blur_result = {"passed": False}
        brightness_result = {"passed": True, "mean": 127, "has_contrast": True}
        texture_result = {"passed": True, "moire_score": 0.05}

        recommendation = service._get_recommendation(blur_result, brightness_result, texture_result)

        assert "borrada" in recommendation.lower()

    def test_get_recommendation_dark_image(self, service):
        """Testa recomendacao para imagem escura"""
        blur_result = {"passed": True}
        brightness_result = {"passed": False, "mean": 30, "has_contrast": True}
        texture_result = {"passed": True, "moire_score": 0.05}

        recommendation = service._get_recommendation(blur_result, brightness_result, texture_result)

        assert "escuro" in recommendation.lower()


class TestLivenessServiceIntegration:
    """Testes de integracao para LivenessService"""

    @pytest.fixture
    def service(self):
        return LivenessService()

    def test_full_liveness_pipeline(self, service):
        """Testa pipeline completo de liveness"""
        # Criar imagem de teste
        img = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
        noise = np.random.normal(0, 15, img.shape).astype(np.int8)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # Executar liveness check
        result = service.check_liveness(img)

        # Verificar estrutura completa
        assert isinstance(result, dict)
        assert "passed" in result
        assert "score" in result
        assert "details" in result
        assert "recommendation" in result

        # Verificar tipos
        assert isinstance(result["passed"], bool)
        assert isinstance(result["score"], float)
        assert isinstance(result["details"], dict)
        assert isinstance(result["recommendation"], str)

        # Verificar limites
        assert 0 <= result["score"] <= 1

    def test_service_is_stateless_for_liveness_check(self, service):
        """Testa que check_liveness e stateless"""
        img = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)

        result1 = service.check_liveness(img)
        result2 = service.check_liveness(img)

        # Resultados devem ser identicos
        assert result1["score"] == result2["score"]
        assert result1["passed"] == result2["passed"]
