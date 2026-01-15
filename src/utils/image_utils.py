"""
Utilitários para processamento de imagens
"""

import base64
import numpy as np
from io import BytesIO
from PIL import Image
import cv2
from fastapi import HTTPException, UploadFile


def image_to_array(image_file: UploadFile) -> np.ndarray:
    """
    Converte UploadFile para numpy array (BGR)

    Args:
        image_file: Arquivo de imagem do FastAPI

    Returns:
        Numpy array no formato BGR (OpenCV)

    Raises:
        HTTPException: Se erro ao processar imagem
    """
    try:
        # Ler bytes do arquivo
        image_bytes = image_file.file.read()

        # Converter para PIL Image
        image = Image.open(BytesIO(image_bytes))

        # Converter para RGB se necessário
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Converter para numpy array
        image_array = np.array(image)

        # Converter RGB para BGR (OpenCV format)
        image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)

        return image_array

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao processar imagem: {str(e)}")


def base64_to_array(base64_string: str) -> np.ndarray:
    """
    Converte string base64 para numpy array (BGR)

    Args:
        base64_string: String base64 da imagem (com ou sem prefix)

    Returns:
        Numpy array no formato BGR (OpenCV)

    Raises:
        HTTPException: Se erro ao processar imagem
    """
    try:
        # Remover prefix se existir (data:image/png;base64,)
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]

        # Decodificar base64
        image_data = base64.b64decode(base64_string)

        # Converter para PIL Image
        image = Image.open(BytesIO(image_data))

        # Converter para RGB se necessário
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Converter para numpy array
        image_array = np.array(image)

        # Converter RGB para BGR (OpenCV format)
        image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)

        return image_array

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao processar imagem base64: {str(e)}")


def validate_image_quality(image_array: np.ndarray) -> dict:
    """
    Valida qualidade da imagem

    Args:
        image_array: Numpy array da imagem

    Returns:
        Dict com scores de qualidade
    """
    height, width = image_array.shape[:2]

    # Verificar resolução mínima
    min_resolution = 200
    resolution_ok = height >= min_resolution and width >= min_resolution

    # Calcular blur (Laplacian variance)
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    blur_ok = blur_score > 100

    # Calcular brightness
    brightness = np.mean(gray)
    brightness_ok = 40 < brightness < 220

    return {
        "resolution_ok": resolution_ok,
        "resolution": {"width": int(width), "height": int(height)},
        "blur_ok": blur_ok,
        "blur_score": float(blur_score),
        "brightness_ok": brightness_ok,
        "brightness": float(brightness),
        "quality_ok": resolution_ok and blur_ok and brightness_ok,
    }
