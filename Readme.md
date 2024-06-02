![new2](https://github.com/farrukhrus/rentbot/assets/63088485/78e7c3df-6792-4b6f-a2fe-9d6c81c1418e)

**Get docker image**
- `docker pull farrukhrus/rentbot:latest`

> Sensitive data (TOKENS, PASSWORDS) is stored in a .env file

**Running Django API**
- `docker compose exec rentbot python rentbot_django_api/manage.py migrate`
- `docker compose exec rentbot python rentbot_django_api/manage.py makemigrations`

**Running Telegram bot**
- `docker compose exec rentbot python rentbot_bot/main.py`

**Data Fetching and Messaging**

Data fetching from the real estate rental site occurs every 20 minutes.
Sending new messages occurs every 10 minutes.
