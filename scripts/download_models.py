"""
Script para download automático dos modelos InsightFace
"""
import os
import sys
from pathlib import Path
import urllib.request
import zipfile
import shutil

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import MODELS_DIR, FACE_MODEL_NAME

MODELS_URLS = {
    "buffalo_l": "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
    "buffalo_sc": "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip",
}


def download_model(model_name: str = FACE_MODEL_NAME):
    """
    Baixa modelo InsightFace

    Args:
        model_name: Nome do modelo (buffalo_l ou buffalo_sc)
    """
    print(f" Iniciando download do modelo: {model_name}")

    if model_name not in MODELS_URLS:
        print(f"❌ Modelo {model_name} não encontrado")
        print(f"Modelos disponíveis: {list(MODELS_URLS.keys())}")
        return False

    # Criar diretório de modelos
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / model_name

    # Verificar se modelo já existe
    if model_path.exists():
        print(f"✅ Modelo {model_name} já existe em {model_path}")

        # Validar arquivos
        required_files = ["det_10g.onnx", "w600k_r50.onnx", "genderage.onnx"]
        missing = [f for f in required_files if not (model_path / f).exists()]

        if not missing:
            print("✅ Todos os arquivos do modelo estão presentes")
            return True
        else:
            print(f"⚠️ Arquivos faltando: {missing}")
            print("Removendo modelo corrompido...")
            shutil.rmtree(model_path)

    # Download
    url = MODELS_URLS[model_name]
    zip_path = MODELS_DIR / f"{model_name}.zip"

    try:
        print(f" Baixando de: {url}")
        urllib.request.urlretrieve(url, zip_path)
        print(f"✅ Download concluído: {zip_path}")

        # Extrair
        print(f" Extraindo para: {MODELS_DIR}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(MODELS_DIR)

        # Limpar zip
        os.remove(zip_path)
        print(f"✅ Modelo {model_name} instalado com sucesso!")

        return True

    except Exception as e:
        print(f"❌ Erro ao baixar modelo: {e}")
        if zip_path.exists():
            os.remove(zip_path)
        return False


def verify_model(model_name: str = FACE_MODEL_NAME):
    """
    Verifica integridade do modelo

    Args:
        model_name: Nome do modelo
    """
    model_path = MODELS_DIR / model_name

    if not model_path.exists():
        return False

    required_files = [
        "det_10g.onnx",
        "w600k_r50.onnx",
        "genderage.onnx",
        "2d106det.onnx"
    ]

    for file in required_files:
        file_path = model_path / file
        if not file_path.exists():
            print(f"❌ Arquivo faltando: {file}")
            return False

        # Verificar tamanho (arquivos corrompidos geralmente são pequenos)
        size_mb = file_path.stat().st_size / (1024 * 1024)
        print(f"  {file}: {size_mb:.2f} MB")

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Athena Face - Download de Modelos InsightFace")
    print("=" * 60)

    # Download
    success = download_model()

    if success:
        print("\n Verificando modelo...")
        if verify_model():
            print("✅ Modelo validado com sucesso!")
        else:
            print("❌ Modelo pode estar corrompido")
            sys.exit(1)
    else:
        print("❌ Falha no download")
        sys.exit(1)
