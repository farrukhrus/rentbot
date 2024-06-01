import json


class Apartment:
    def __init__(self, city, district, price, currency,
                 type, rooms, size, reporter,
                 published, internalId, src,
                 image_url, url) -> None:
        self.src = src
        self.city = city
        self.district = district
        self.price = price
        self.currency = currency
        self.type = type
        self.rooms = rooms
        self.size = size
        self.reporter = reporter
        self.published = published
        self.internalId = internalId
        self.image_url = image_url
        self.url = url

    def __str__(self) -> str:
        return f'src: {self.src}, internalId: {self.internalId}, city: {self.city}'

    def convertToJson(self) -> str:
        return json.dumps({
            "src": self.src,
            "city": self.city,
            "district": self.district,
            "price": self.price,
            "currency": self.currency,
            "type": self.type,
            "rooms": self.rooms,
            "size": self.size,
            "reporter": self.reporter,
            "published": self.published,
            "internalId": self.internalId,
            "image_url": self.image_url,
            "url": self.url
        })
