#!/bin/sh
set -eu

python manage.py collectstatic --noinput
exec uvicorn core.asgi:application --host 0.0.0.0 --port "${PORT:-10000}"
