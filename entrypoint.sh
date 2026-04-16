# #!/bin/sh

# python manage.py migrate --no-input
# python manage.py collectstatic --no-input

# DJANGO_SUPERUSER_PASSWORD=$SUPER_USER_PASSWORD python manage.py createsuperuser --email $SUPER_USER_EMAIL --noinput

# # gunicorn parameter.wsgi:application --bind 0.0.0.0:8000
# # daphne parameter.asgi:application --bind 0.0.0.0:8000


#!/bin/sh

# Choisissez l'utilisateur approprié en fonction de la variable d'environnement
if [ "$SERVICE_USER" = "gunicorn" ]; then
    USER=gunicorn
elif [ "$SERVICE_USER" = "daphne" ]; then
    USER=daphne
elif [ "$SERVICE_USER" = "celery" ]; then
    USER=celery
elif [ "$SERVICE_USER" = "django" ]; then
    USER=django
else
    USER=gunicorn  # Utilisateur par défaut
fi

# Exécutez la commande en tant que l'utilisateur choisi
exec su-exec $USER "$@"