FROM python:3.10-slim

# Evitar prompts interativos
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    wget \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements primeiro (cache layer)
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Criar diretórios necessários
RUN mkdir -p /app/logs

# Download de modelos (opcional, fallback no startup)
RUN python scripts/download_models.py 2>/dev/null || echo "⚠️ Modelos serão baixados no startup"

# Expor porta
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/health', timeout=5).raise_for_status()" || exit 1

# Comando de inicialização
CMD ["sh", "-c", "python scripts/download_models.py 2>/dev/null || true && uvicorn src.main:app --host 0.0.0.0 --port 8001"]