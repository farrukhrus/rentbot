FROM python:3.10

WORKDIR /app

COPY . /app

RUN pip install --trusted-host pypi.python.org -r rentbot_parser/requirements.txt

RUN apt-get update && apt-get install -y wget unzip cron
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb 
RUN apt install -y --fix-missing ./google-chrome-stable_current_amd64.deb
RUN rm ./google-chrome-stable_current_amd64.deb

RUN pip install --trusted-host pypi.python.org -r rentbot_django_api/requirements.txt --no-cache-dir

RUN pip install --trusted-host pypi.python.org -r rentbot_bot/requirements.txt --no-cache-dir

EXPOSE 8000

COPY cronjob /etc/cron.d/cronjob
RUN chmod 0644 /etc/cron.d/cronjob

RUN echo "" >> /etc/cron.d/cronjob
RUN crontab /etc/cron.d/cronjob

COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
