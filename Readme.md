docker compose exec rentbot python rentbot_django_api/manage.py migrate

docker compose exec rentbot python rentbot_django_api/manage.py makemigrations

docker compose exec rentbot python rentbot_bot/main.py
