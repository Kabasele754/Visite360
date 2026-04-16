#!/bin/sh

set -e

# Start nginx in background
nginx -g "daemon off;" &
NGINX_PID=$!

# Reload nginx every 12 hours so renewed certs are picked up
while true; do
  sleep 1h
  echo "Reloading nginx to pick up renewed certificates..."
  nginx -s reload
done &

# Keep container running on nginx process
wait $NGINX_PID