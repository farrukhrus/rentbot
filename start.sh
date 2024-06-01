#!/bin/sh

cd /app/rentbot_django_api
gunicorn rentbot_django_api.wsgi:application --bind 0.0.0.0:8000