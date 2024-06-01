from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import os
import sys
import requests
import logging
import time
import psutil

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from apartment import Apartment

load_dotenv()

NUMBER_OF_PAGES = int(os.getenv('LIMIT'))

BASE_URL = os.getenv('BASE_URL')
SEARCH_URL = os.getenv('SEARCH_URL')
API_URL = f"{os.getenv('API_URL')}apartments/"
LOG_LEVEL = logging.INFO if os.getenv('LOG_LEVEL') == 'INFO' else logging.ERROR
cities = ['beograd', 'novi-sad']
adv_types = ['izdavanje-stanova', 'izdavanje-kuca']

log_file_path = '/app/rentbot_parser/output.log'
if os.path.exists(log_file_path):
    os.remove(log_file_path)

logging.basicConfig(filename=log_file_path, level=LOG_LEVEL,
                    format='%(asctime)s %(levelname)s:%(message)s',
                    encoding='utf-8')
logger = logging.getLogger()


def invokePost(apartment_json):
    return (
        requests.post(API_URL,
                      data=apartment_json,
                      headers={'Content-Type': 'application/json'})
    )


# Ожидание загрузки контента JS скриптами
def wait_for_images(driver, tag, timeout=60):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, tag))
        )
    except Exception as e:
        logger.error(f'Ошибка при ожидании: {str(e)}')


def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')
    options.add_argument('--log-level=3')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def monitor_resources():
    memory = psutil.virtual_memory()
    logger.info(f'Использование памяти: {memory.percent}%')
    cpu = psutil.cpu_percent(interval=1)
    logger.info(f'Использование CPU: {cpu}%')


today_start = datetime.combine(date.today(), datetime.min.time())
logger.info('Загрузка данных: ' + today_start.strftime('%d.%m.%Y %H:%M:%S'))
logger.info('Агрегатор: ' + BASE_URL)

for avd_type in adv_types:
    logger.info('Тип недвижимости: ' + avd_type.upper())
    for grad in cities:
        i = 0
        logger.info('Город: ' + grad.upper())

        while i < NUMBER_OF_PAGES:
            i += 1
            logger.info('Страница {0}'.format(i))

            driver = setup_driver()

            try:
                driver.get(SEARCH_URL.format(avd_type, grad, i))
                driver.implicitly_wait(10)

                wait_for_images(driver=driver, tag='img.resized-image')

                if 'product-list' in driver.page_source:
                    page_source = driver.page_source
                    wait_for_images(driver=driver, tag='div.product-item:not(.banner-list)')

                    soup = BeautifulSoup(page_source, 'html.parser')
                    listings = soup.select('div.product-item:not(.banner-list)')
                    for listing in listings:
                        try:
                            sub_url = ''
                            publish_date = datetime.strptime(
                                listing.find('span', class_='publish-date').
                                get_text(strip=True), '%d.%m.%Y.'
                            )

                            if publish_date >= today_start:
                                product_tag = listing.find(class_='product-title')
                                if product_tag:
                                    sub = product_tag.find('a')
                                    if sub:
                                        sub_url = BASE_URL + sub['href']

                                if sub_url == '':
                                    continue

                                image_tag = listing.find(class_='resized-image')
                                image_url = image_tag['src'] if image_tag else ''

                                driver.get(sub_url)
                                time.sleep(5)

                                if 'product-page' in driver.page_source:
                                    subpage_source = driver.page_source
                                    sub_soup = BeautifulSoup(subpage_source, 'html.parser')
                                    if sub_soup:
                                        try:
                                            if avd_type == 'izdavanje-kuca':
                                                published = sub_soup.find('strong', id='plh75').get_text(strip=True)
                                            else:
                                                published = sub_soup.find('strong', id='plh81').get_text(strip=True)

                                            if avd_type == 'izdavanje-kuca':
                                                internalId = sub_soup.find('strong', id='plh71').get_text(strip=True)
                                            else:
                                                internalId = sub_soup.find('strong', id='plh77').get_text(strip=True)

                                            content = sub_soup.find('div', class_='product-page')
                                            if content:
                                                city = content.find('span', id='plh2').get_text(strip=True)
                                                district = content.find('span', id='plh3').get_text(strip=True)
                                                offer = content.find('span', id='plh6')
                                                if offer:
                                                    price = offer.find('span', class_='offer-price-value').get_text(strip=True)
                                                    currency = offer.find('span', class_='offer-price-unit').get_text(strip=True)
                                                type = content.find('span', id='plh10').get_text(strip=True)
                                                rooms = content.find('span', id='plh12').get_text(strip=True)
                                                size = content.find('span', id='plh11').get_text(strip=True)
                                                reporter = content.find('span', id='plh13').get_text(strip=True)
                                                apartment = Apartment(city=city, district=district,
                                                                    price=price, currency=currency,
                                                                    type=type, rooms=rooms, size=size,
                                                                    reporter=reporter, published=published,
                                                                    internalId=internalId, src='halooglasi',
                                                                    image_url=image_url, url=sub_url)
                                                response = invokePost(apartment.convertToJson())
                                                if response.status_code == 201:
                                                    logger.info('Запись опубликована: ' + apartment.convertToJson())
                                                else:
                                                    logger.error(
                                                        f'Возникла ошибка: {response.content}\n{apartment.convertToJson()}'
                                                    )
                                        except Exception as e:
                                            logger.error(f'Ошибка: {str(e)}\n{sub_url}')
                                else:
                                    logger.info('Страница не найдена: ' + sub_url)
                                driver.back()

                        except Exception as e:
                            logger.error(f'Ошибка: {str(e)}')
                            continue
                else:
                    break
            except Exception as e:
                logger.error(f'Ошибка загрузки страницы {i}: {str(e)}')
                # Возможны глюки с драйвером при нехватке ресурсов
                # Повторная попытка через 5 секунд
                time.sleep(5)
                i -= 1
                continue
            finally:
                driver.quit()
                monitor_resources()

logger.info('Загрузка завершена')
