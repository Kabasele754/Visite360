from .base import *

DEBUG = False

ALLOWED_HOSTS = ['62.171.163.171','www.twinscopes.com','twinscopes.com','api.twinscopes.com', 'localhost', '127.0.0.1']
# Liste des domaines autorisés pour les connexions
CSRF_TRUSTED_ORIGINS = [
    "https://twinscopes.com",
    "https://www.twinscopes.com",
    'https://api.twinscopes.com',
]

CORS_ALLOWED_ORIGINS = [
  "https://twinscopes.com",
  "https://www.twinscopes.com",
  "https://admin.twinscopes.com",
]


# Configuration de la politique de sécurité des contenus (CSP)
CSP_HEADER = {
    'default-src': ["'self'", "twinscopes.com"],
    'script-src': ["'self'", "twinscopes.com"],
    'style-src': ["'self'", "twinscopes.com"],
    'img-src': ["'self'", "twinscopes.com"],
    'font-src': ["'self'", "twinscopes.com"],  
}



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



