# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm

# =============================================================================
# BUILD ARGUMENTS
# =============================================================================

ARG INSTALL_FULL_AI=false
ARG PADDLEPADDLE_VERSION=3.3.0

# =============================================================================
# PYTHON / AI RUNTIME
# =============================================================================

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    MPLCONFIGDIR=/root/.cache/matplotlib \
    HF_HOME=/root/.cache/huggingface \
    PADDLE_HOME=/root/.paddleocr

WORKDIR /app

# =============================================================================
# SYSTEM DEPENDENCIES
# =============================================================================

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    curl \
    wget \
    ca-certificates \
    pkg-config \
    libpq-dev \
    libffi-dev \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libopenblas0 \
    ffmpeg \
    shared-mime-info \
    fontconfig \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# PYTHON DEPENDENCIES
# =============================================================================

RUN python -m pip install --upgrade pip setuptools wheel

COPY requirements.txt /app/requirements.txt
COPY requirements-ai-full.txt /app/requirements-ai-full.txt

# Install the official CPU wheels before Ultralytics / sentence-transformers so
# pip does not pull a CUDA-enabled or incompatible PyTorch build indirectly.
RUN python -m pip install \
    --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch \
    torchvision

RUN python -m pip install \
    --no-cache-dir \
    -r /app/requirements.txt

# PaddleOCR / Florence-2 are installed only in the dedicated AI worker image.
# The production VPS is x86_64 CPU; fail clearly on an unsupported architecture.
RUN if [ "${INSTALL_FULL_AI}" = "true" ]; then \
      ARCH="$(uname -m)"; \
      case "${ARCH}" in \
        x86_64|amd64) ;; \
        *) echo "Full PaddlePaddle CPU image requires x86_64; detected ${ARCH}." >&2; exit 1 ;; \
      esac; \
      python -m pip install \
        --no-cache-dir \
        "paddlepaddle==${PADDLEPADDLE_VERSION}" \
        -i https://www.paddlepaddle.org.cn/packages/stable/cpu/; \
      python -m pip install \
        --no-cache-dir \
        -r /app/requirements-ai-full.txt; \
    fi

RUN python -m pip check

# =============================================================================
# APPLICATION CODE
# =============================================================================

COPY . /app/

RUN mkdir -p \
    /app/staticfiles \
    /app/media \
    /app/model_weights \
    /app/logs \
    /root/.cache/matplotlib \
    /root/.cache/huggingface \
    /root/.paddleocr \
    /var/run/celery

RUN python -m compileall -q /app/apps /app/config

EXPOSE 8000
