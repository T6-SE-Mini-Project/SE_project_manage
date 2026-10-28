#!/bin/sh
# Container entrypoint for the Online Book Store backend.
#
# Runs on every container start, where the full environment (database
# credentials, secret key) is guaranteed to be present. Doing this here rather
# than at image build time matters: Render does not pass a service's
# environment variables into "docker build", so a build-time collectstatic or
# migrate would run without a database or a secret key.
set -e

# Collect static files for WhiteNoise. The production STORAGES backend uses a
# manifest, so this must succeed before gunicorn serves a single request.
echo "==> collectstatic"
python manage.py collectstatic --noinput

# Apply migrations. Safe for a single web instance, which is what the Render
# blueprint provisions. If you scale to multiple instances, move this into a
# Render pre-deploy command so only one process migrates at a time.
echo "==> migrate"
python manage.py migrate --noinput

# PORT is assigned by the platform (Render injects it); 8000 keeps plain
# "docker run" and docker-compose working unchanged.
echo "==> gunicorn on port ${PORT:-8000}"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
