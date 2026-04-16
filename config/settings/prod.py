from .base import *

DEBUG = False

ALLOWED_HOSTS = ['62.171.163.171','www.s4e-elevateai.com','s4e-elevateai.com','api.s4e-elevateai.com', 'localhost', '127.0.0.1']
# Liste des domaines autorisés pour les connexions
CSRF_TRUSTED_ORIGINS = [
    "https://s4e-elevateai.com",
    "https://www.s4e-elevateai.com",
    'https://api.s4e-elevateai.com',
]

CORS_ALLOWED_ORIGINS = [
  "https://s4e-elevateai.com",
  "https://www.s4e-elevateai.com",
  "https://admin.s4e-elevateai.com",
]


# Configuration de la politique de sécurité des contenus (CSP)
CSP_HEADER = {
    'default-src': ["'self'", "s4e-elevateai.com"],
    'script-src': ["'self'", "s4e-elevateai.com"],
    'style-src': ["'self'", "s4e-elevateai.com"],
    'img-src': ["'self'", "s4e-elevateai.com"],
    'font-src': ["'self'", "s4e-elevateai.com"],  
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
        'NAME': os.environ.get('DB_NAME', 'elevateaidb'),
        'USER': os.environ.get('DB_USER', 'elevateaiuser'),
        'PASSWORD': os.environ.get('DB_PASS', 'elevateaipass'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}



# static local this code for to search file css

STATIC_ROOT = "/app/static/"


COMPRESS_ROOT = STATIC_ROOT 


MEDIA_ROOT = '/app/media'



