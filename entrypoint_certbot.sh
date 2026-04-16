#!/bin/bash

# Renouveler les certificats Let's Encrypt
certbot renew --non-interactive --agree-tos

# Redémarrer Nginx pour charger les nouveaux certificats
nginx -s reload
