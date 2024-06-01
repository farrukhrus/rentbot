from datetime import datetime, timedelta
from rest_framework import serializers
import pytz
from .models import Apartment, Task


class ApartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Apartment
        fields = '__all__'

    def to_internal_value(self, data):
        # касты
        if 'price' in data:
            if isinstance(data['price'], str):
                data['price'] = int(data['price'].replace('.', '').replace(',', ''))

        if 'rooms' in data:
            if isinstance(data['rooms'], str):
                data['rooms'] = float(data['rooms'].replace('+', ''))

        if 'size' in data:
            if isinstance(data['size'], str):
                data['size'] = int(float(data['size'].replace(' m2', '').replace(',', '.')))

        # !!! не забыть перенести в парсер
        if 'type' in data:
            if data['type'].lower() == 'stan':
                data['type'] = 'Квартира'
            elif data['type'].lower() == 'kuća':
                data['type'] = 'Дом'

        if 'city' in data:
            if data['city'].lower() == 'beograd':
                data['city'] = 'Белград'
            elif data['city'].lower() == 'novi sad':
                data['city'] = 'Нови Сад'

        if 'reporter' in data:
            if data['reporter'].lower() == 'agencija':
                data['reporter'] = 'Агенство'
            elif data['reporter'].lower() == 'vlasnik':
                data['reporter'] = 'Владелец'

        return super().to_internal_value(data)

    def validate(self, data):
        if Apartment.objects.filter(internalId=data['internalId'],
                                    src=data['src']).exists():
            raise serializers.ValidationError(
                "Объявление с таким ID уже создано.")
        return data

    def validate_district(self, value):
        if value.startswith("Opština "):
            return value.replace("Opština ", "")
        return value

    def validate_published(self, value):
        belgrade_tz = pytz.timezone('Europe/Belgrade')
        parsed_date = datetime.strptime(value, '%d.%m.%Y. u %H:%M')

        if belgrade_tz.localize(parsed_date) < datetime.now(belgrade_tz) - timedelta(minutes=20):
            raise serializers.ValidationError(
                "Дата и время публикации не должны быть меньше (сейчас - 20 минут)")

        return belgrade_tz.localize(parsed_date).strftime('%d.%m.%Y %H:%M')


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = '__all__'
