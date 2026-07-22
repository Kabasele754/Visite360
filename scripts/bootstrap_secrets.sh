#!/usr/bin/env sh
set -eu
mkdir -p secrets
[ -s secrets/db_password.txt ] || python -c 'import secrets; print(secrets.token_urlsafe(32))' > secrets/db_password.txt
[ -s secrets/pgadmin_password.txt ] || python -c 'import secrets; print(secrets.token_urlsafe(24))' > secrets/pgadmin_password.txt
if [ ! -s secrets/google_adc.json ]; then
  printf '%s\n' 'Copy your Google ADC service-account JSON to secrets/google_adc.json' >&2
fi
chmod 600 secrets/db_password.txt secrets/pgadmin_password.txt 2>/dev/null || true
printf '%s\n' 'Secrets initialized.'
