from .base import *

DEBUG = False

ALLOWED_HOSTS = ['95.111.247.13','www.s4e-elevatai.com','s4e-elevatai.com','api.s4e-elevatai.com', 'localhost', '127.0.0.1']
# Liste des domaines autorisés pour les connexions
CSRF_TRUSTED_ORIGINS = [
    "https://s4e-elevatai.com",
    "https://www.s4e-elevatai.com",
    'https://api.s4e-elevatai.com',
]

CORS_ALLOWED_ORIGINS = [
  "https://s4e-elevatai.com",
  "https://www.s4e-elevatai.com",
  "https://admin.s4e-elevatai.com",
]


# Configuration de la politique de sécurité des contenus (CSP)
CSP_HEADER = {
    'default-src': ["'self'", "s4e-elevatai.com"],
    'script-src': ["'self'", "s4e-elevatai.com"],
    'style-src': ["'self'", "s4e-elevatai.com"],
    'img-src': ["'self'", "s4e-elevatai.com"],
    'font-src': ["'self'", "s4e-elevatai.com"],
    
}

import os

def read_secret(path, default=""):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return default

DB_PASSWORD = os.getenv("DB_PASS")
DB_PASS_FILE = os.getenv("DB_PASS_FILE")
if DB_PASS_FILE and not DB_PASSWORD:
    DB_PASSWORD = read_secret(DB_PASS_FILE)

# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.getenv("DB_NAME", "richcorpdb"),
#         "USER": os.getenv("DB_USER", "richcorpuser"),
#         "PASSWORD": DB_PASSWORD or "richcorppass",
#         "HOST": os.getenv("DB_HOST", "db"),
#         "PORT": os.getenv("DB_PORT", "5432"),
#     }
# }


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'elevataidb'),
        'USER': os.environ.get('DB_USER', 'elevataiuser'),
        'PASSWORD': os.environ.get('DB_PASS', 'elevataipass'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}



# static local this code for to search file css

STATIC_ROOT = "/app/static/"


COMPRESS_ROOT = STATIC_ROOT 


MEDIA_ROOT = '/app/media'



