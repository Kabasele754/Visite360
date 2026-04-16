#!/bin/bash

# Set email address (replace with yours)
EMAIL="contact@example.com"

# Set domains (replace with yours)
DOMAINS="s4e-elevatai.com www.s4e-elevatai.com"

# Ensure Certbot is installed
if ! command -v certbot &> /dev/null; then
  echo "Error: Certbot is not installed. Please install Certbot before running this script."
  exit 1
fi

# Renew certificates using webroot authentication
certbot renew --quiet --non-interactive --agree-tos --email "$EMAIL" \
  -d "$DOMAINS" --webroot -w "/var/www/certbot"

# Check if renewal was successful
if [ $? -eq 0 ]; then
  echo "Certificates renewed successfully!"
  # (Optional) Restart Nginx service to reload certificates
  # (Replace with the appropriate command for your web server)
  nginx -s reload
else
  echo "Error: Certificate renewal failed!"
  # (Optional) Send notification or log error for further investigation
fi
