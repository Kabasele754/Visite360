Create these local files before starting production Docker Compose:

- `db_password.txt`
- `pgadmin_password.txt`
- `google_adc.json`

Run `./scripts/bootstrap_secrets.sh` for the password files. Never commit real secrets.
