FROM python:3.9.6-alpine

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apk update && apk add --no-cache \
    postgresql-dev \
    gcc \
    python3-dev \
    musl-dev \
    libffi-dev \
    jpeg-dev \
    zlib-dev \
    linux-headers \
    cairo-dev \
    pango-dev \
    gdk-pixbuf-dev \
    pkgconfig

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN mkdir -p /app/static /app/media

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]