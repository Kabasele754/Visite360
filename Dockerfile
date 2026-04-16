FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    libffi-dev \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    pkg-config \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN mkdir -p /app/static /app/media

EXPOSE 8000

# FROM python:3.11-slim

# ENV PYTHONUNBUFFERED=1
# ENV PYTHONDONTWRITEBYTECODE=1

# WORKDIR /app

# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     gcc \
#     libpq-dev \
#     libffi-dev \
#     libcairo2-dev \
#     libpango1.0-dev \
#     libgdk-pixbuf-2.0-dev \
#     libjpeg62-turbo-dev \
#     zlib1g-dev \
#     pkg-config \
#     shared-mime-info \
#     && rm -rf /var/lib/apt/lists/*

# COPY requirements.txt /app/

# RUN pip install --upgrade pip && \
#     pip install --no-cache-dir -r requirements.txt

# COPY . /app/

# RUN mkdir -p /app/static /app/media

# EXPOSE 8000

# CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]