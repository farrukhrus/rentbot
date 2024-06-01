# models.py
from django.db import models
from django.utils import timezone


# Объявление
class Apartment(models.Model):
    city = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    price = models.IntegerField()
    currency = models.CharField(max_length=10)
    type = models.CharField(max_length=50)
    rooms = models.DecimalField(max_digits=10, decimal_places=1)
    size = models.IntegerField()
    reporter = models.CharField(max_length=100)
    published = models.CharField(max_length=100)
    internalId = models.CharField(max_length=100, unique=True)
    src = models.CharField(max_length=100)
    image_url = models.URLField(max_length=200)
    url = models.URLField(max_length=200)
    insertedAt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.city} - {self.district} - {self.price} {self.currency} - {self.type} - {self.rooms} - {self.size}'


# Задание на выполнение
class Task(models.Model):
    user_id = models.BigIntegerField(unique=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    interval = models.IntegerField(default=600)  # 10 минут по дефолту
    # Последняя последнего сообщения
    last_sent_date = models.DateTimeField(default=timezone.now)
    reporters = models.JSONField(default=list, null=True, blank=True)
    sizes = models.JSONField(default=list, null=True, blank=True)
    min_price = models.IntegerField(null=True, blank=True)
    max_price = models.IntegerField(null=True, blank=True)
    districts = models.JSONField(default=list, null=True, blank=True)
    property_types = models.JSONField(default=list, null=True, blank=True)
    rooms = models.JSONField(default=list, null=True, blank=True)
    isReady = models.BooleanField(default=False)

    def __str__(self):
        return f'Task(chat_id={self.user_id}, city={self.city}, interval={self.interval}, last_sent_date={self.last_sent_date}, isReady={self.isReady})'
