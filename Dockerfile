FROM python:3.12-slim

# =============================================================================
# PYTHON
# =============================================================================

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app


# =============================================================================
# DEPENDENCIES SYSTÈME
# =============================================================================

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    curl \
    wget \
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
    ffmpeg \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*


# =============================================================================
# PIP
# =============================================================================

RUN python -m pip install --upgrade \
    pip \
    setuptools \
    wheel


# =============================================================================
# REQUIREMENTS DU PROJET
# =============================================================================

COPY requirements.txt /app/requirements.txt
COPY requirements-ai-full.txt /app/requirements-ai-full.txt

RUN python -m pip install \
    --no-cache-dir \
    -r /app/requirements.txt

# Optional Florence-2 / PaddleOCR Python stack for the dedicated AI worker.
# PaddlePaddle itself must match the target CPU/GPU platform and is installed separately.
ARG INSTALL_FULL_AI=false
RUN if [ "$INSTALL_FULL_AI" = "true" ]; then \
      python -m pip install --no-cache-dir -r /app/requirements-ai-full.txt; \
    fi


# =============================================================================
# PYTORCH CPU
# =============================================================================

RUN python -m pip install \
    --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch \
    torchvision


# =============================================================================
# ULTRALYTICS
# =============================================================================

RUN python -m pip install \
    --no-cache-dir \
    ultralytics \
    opencv-python-headless


# =============================================================================
# CODE DU PROJET
# =============================================================================

COPY . /app/


# =============================================================================
# DOSSIERS
# =============================================================================

RUN mkdir -p \
    /app/staticfiles \
    /app/media \
    /app/model_weights \
    /app/logs \
    /var/run/celery


# =============================================================================
# PORT
# =============================================================================

EXPOSE 8000