#!/bin/bash
cd /app/server
exec gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120