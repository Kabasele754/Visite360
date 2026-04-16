#!/bin/bash

# Générer les certificats SSL Let's Encrypt
certbot certonly --standalone -d s4e-elevateai.com -d www.s4e-elevateai.com --agree-tos -n --email pepexykabasele@gmail.com

# Copier les certificats dans le répertoire Nginx
cp /etc/letsencrypt/live/s4e-elevateai.com/fullchain.pem /etc/nginx/ssl/cert.pem
cp /etc/letsencrypt/live/s4e-elevateai.com/privkey.pem /etc/nginx/ssl/privkey.pem

# Redémarrer Nginx pour charger les nouveaux certificats
nginx -s reload
