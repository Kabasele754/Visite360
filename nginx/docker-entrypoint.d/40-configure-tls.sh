#!/bin/sh
set -eu

CERT=/etc/letsencrypt/live/twinscopes.com/fullchain.pem
KEY=/etc/letsencrypt/live/twinscopes.com/privkey.pem

rm -f /etc/nginx/conf.d/10-http.conf /etc/nginx/conf.d/20-https.conf

if [ -s "$CERT" ] && [ -s "$KEY" ]; then
    echo "Twinscopes Nginx: TLS certificate detected; enabling HTTPS."
    cp /etc/nginx/templates-custom/http-redirect.conf /etc/nginx/conf.d/10-http.conf
    cp /etc/nginx/templates-custom/https.conf /etc/nginx/conf.d/20-https.conf
else
    echo "Twinscopes Nginx: no TLS certificate yet; enabling HTTP bootstrap mode."
    cp /etc/nginx/templates-custom/http-bootstrap.conf /etc/nginx/conf.d/10-http.conf
fi
