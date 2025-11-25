#!/bin/bash
# No cd command needed since WORKDIR is already set to /app/server
exec gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120