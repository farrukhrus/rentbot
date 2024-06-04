import logging
import os
import sys
import re
import requests
from datetime import datetime, timedelta, timezone
import pytz
from dateutil import parser
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackContext, CallbackQueryHandler,
    ConversationHandler, JobQueue, MessageHandler, filters
)
from dotenv import load_dotenv

from dict import (cities, districts_belgrade, districts_novisad,
                  property_types, reporters, rooms, sizes)

load_dotenv()

TOKEN = os.getenv('TOKEN')
API_URL = os.getenv('API_URL')
ADV_API_URL = f'{API_URL}apartments/'
TASK_API_URL = f'{API_URL}tasks/'
LOG_LEVEL = logging.INFO if os.getenv('LOG_LEVEL') == 'INFO' else logging.ERROR

# !!! Настроить ротацию логов и именование файлов с учетом даты
log_file_path = '/app/rentbot_bot/output.log'
if os.path.exists(log_file_path):
    os.remove(log_file_path)

logging.basicConfig(filename=log_file_path, level=LOG_LEVEL,
                    format='%(asctime)s %(levelname)s:%(message)s',
                    encoding='utf-8')
logger = logging.getLogger()

# Состояния фильтров
SELECTING_FILTER, SELECTING_CITY, SELECTING_REPORTER, SELECTING_SIZE, SELECTING_MIN_PRICE, SELECTING_MAX_PRICE, SELECTING_DISTRICT, SELECTING_PROPERTY_TYPE, SELECTING_ROOMS, CONFIRMATION = range(10)
# Интервал отправки сообщений в секундах
INTERVAL = 10 * 60


def generate_keyboard(options, selected_options):
    keyboard = []
    columns = []
    # Макс. кол-во кнопок в столбце
    max_buttons_per_column = 10

    for i in range(max_buttons_per_column):
        columns.append([])

    # Плодим кнопки
    for index, (key, name) in enumerate(options.items()):
        column_index = index % max_buttons_per_column
        if key in selected_options:
            columns[column_index].append(
                InlineKeyboardButton(f'✅ {name}', callback_data=key))
        else:
            columns[column_index].append(
                InlineKeyboardButton(name, callback_data=key))

    # Собираем клавиатуру
    for i in range(max_buttons_per_column):
        if columns[i]:
            keyboard.append(columns[i])

    keyboard.append([InlineKeyboardButton('Далее ▶️', callback_data='continue')])
    return InlineKeyboardMarkup(keyboard)


def generate_filter_menu(context):
    selected_city = context.user_data.get('selected_city', [])
    selected_city = selected_city[0] if selected_city else ''
    selected_districts = ', '.join(
        context.user_data.get('selected_districts', []))
    selected_sizes = ', '.join(context.user_data.get('selected_sizes', []))
    min_price = context.user_data.get('min_price', '')
    max_price = context.user_data.get('max_price', '')
    selected_property_types = ', '.join(
        context.user_data.get('selected_property_types', []))
    selected_rooms = ', '.join(context.user_data.get('selected_rooms', []))
    selected_reporters = ', '.join(context.user_data.get('selected_reporters', []))

    keyboard = [
        [InlineKeyboardButton(
            f'✅Город: {selected_city}' if selected_city else 'Город', callback_data='filter_city')],
    ]

    if selected_city:
        keyboard.append([InlineKeyboardButton(
            f'✅Район: {selected_districts}' if selected_districts else 'Район', callback_data='filter_district')])
    else:
        keyboard.append([InlineKeyboardButton('Район (Выберите город)', callback_data='inactive')])

    keyboard.extend([
        [InlineKeyboardButton(
            f'✅Площадь: {selected_sizes}' if selected_sizes else 'Площадь', callback_data='filter_size')],
        [InlineKeyboardButton(
            f'✅Минимальная цена: {min_price}€' if min_price else 'Минимальная цена (€)', callback_data='filter_min_price')],
        [InlineKeyboardButton(
            f'✅Максимальная цена: {max_price}€' if max_price else 'Максимальная цена (€)', callback_data='filter_max_price')],
        [InlineKeyboardButton(
            f'✅Тип недвижимости: {selected_property_types}' if selected_property_types else 'Тип недвижимости', callback_data='filter_property_type')],
        [InlineKeyboardButton(
            f'✅Количество комнат: {selected_rooms}' if selected_rooms else 'Количество комнат', callback_data='filter_rooms')],
        [InlineKeyboardButton(
            f'✅Разместил: {selected_reporters}' if selected_reporters else 'Разместил', callback_data='filter_reporter')],
        [InlineKeyboardButton(
            'Начать поиск ▶️', callback_data='start_search')]
    ])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    context.user_data.clear()
    # Проверка наличия задачи в базе данных
    # !!! возможно, что стоит проверять задание в JobQueue
    task_response = requests.get(f'{TASK_API_URL}filter-by-user-id?user_id={user_id}')
    if task_response.status_code == 200:
        tasks = task_response.json()
        if tasks:
            task = tasks[0]
            context.user_data['selected_city'] = [task.get('city', '')]
            context.user_data['selected_reporters'] = task.get('reporters', [])
            context.user_data['selected_sizes'] = task.get('sizes', [])
            context.user_data['min_price'] = task.get('min_price')
            context.user_data['max_price'] = task.get('max_price')
            context.user_data['selected_districts'] = task.get('districts', [])
            context.user_data['selected_property_types'] = task.get('property_types', [])
            context.user_data['selected_rooms'] = task.get('rooms', [])
            reply_markup = generate_filter_menu(context)

            if update.message:
                await update.message.reply_text(
                    '''
Поиск объявлений уже идет.
Текущие критерии поиска:
                    ''',
                    reply_markup=reply_markup
                )
            elif update.callback_query:
                query = update.callback_query
                await query.answer()
                await query.edit_message_text(
                    '''
Поиск объявлений уже идет.
Текущие критерии поиска:
                    ''',
                    reply_markup=reply_markup
                )
            return SELECTING_FILTER

    # Если задачи не найдено или создана новая, начинаем выбор фильтров
    await begin_selection(update, context)
    return SELECTING_FILTER


async def begin_selection(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
    else:
        query = None

    chat = update.effective_chat
    name = chat.first_name

    logger.info('Получена команда /start от пользователя: {} : {}'.format(name, chat))

    context.user_data['selected_city'] = []
    context.user_data['selected_reporters'] = []
    context.user_data['selected_sizes'] = []
    context.user_data['min_price'] = None
    context.user_data['max_price'] = None
    context.user_data['selected_districts'] = []
    context.user_data['selected_property_types'] = []
    context.user_data['selected_rooms'] = []

    reply_markup = generate_filter_menu(context)
    if update.callback_query:
        await query.message.reply_text(
            '''
Привет!
Я помогу вам с поиском недвижимости для аренды в Сербии.

Выберите критерии поиска:
            ''',
            reply_markup=reply_markup
        )
    elif update.message.text == '/reset':
        await update.message.reply_text(
            '''
Выберите новые критерии поиска:
            ''',
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            '''
Я помогу вам с поиском недвижимости для аренды в Сербии.
Выберите критерии поиска:
            ''',
            reply_markup=reply_markup
        )
    return SELECTING_FILTER


async def filter_city(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    reply_markup = generate_keyboard(cities, context.user_data['selected_city'])
    await query.edit_message_text(text='Выберите город:', reply_markup=reply_markup)
    return SELECTING_CITY


async def filter_reporter(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    reply_markup = generate_keyboard(reporters, context.user_data['selected_reporters'])
    await query.edit_message_text(text='Выберите объявителя:', reply_markup=reply_markup)
    return SELECTING_REPORTER


async def filter_size(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    reply_markup = generate_keyboard(sizes, context.user_data['selected_sizes'])
    await query.edit_message_text(
        text='Выберите размеры:', reply_markup=reply_markup)
    return SELECTING_SIZE


async def filter_district(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    selected_city = context.user_data.get('selected_city', [None])[0]

    if selected_city == 'Белград':
        options = districts_belgrade
    elif selected_city == 'Нови Сад':
        options = districts_novisad
    else:
        options = {}

    reply_markup = generate_keyboard(options, context.user_data['selected_districts'])
    await query.edit_message_text(text='Выберите районы:', reply_markup=reply_markup)
    return SELECTING_DISTRICT


async def filter_property_type(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    reply_markup = generate_keyboard(
        property_types, context.user_data['selected_property_types'])
    await query.edit_message_text(
        text='Выберите типы недвижимости:', reply_markup=reply_markup)
    return SELECTING_PROPERTY_TYPE


async def filter_rooms(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    reply_markup = generate_keyboard(rooms, context.user_data['selected_rooms'])
    await query.edit_message_text(
        text='Выберите количество комнат:', reply_markup=reply_markup)
    return SELECTING_ROOMS


async def city_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    city = query.data
    if city == 'continue':
        reply_markup = generate_filter_menu(context)
        await query.edit_message_text(
            text='Критерии поиска:', reply_markup=reply_markup)
        return SELECTING_FILTER

    context.user_data['selected_city'] = [city]
    # Сбрасываем выбранные районы при изменении города
    context.user_data['selected_districts'] = []
    reply_markup = generate_keyboard(cities, context.user_data['selected_city'])
    await query.edit_message_text(
        text='Выберите город:', reply_markup=reply_markup)
    return SELECTING_CITY


async def reporter_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    reporter = query.data
    if reporter == 'continue':
        reply_markup = generate_filter_menu(context)
        await query.edit_message_text(
            text='Критерии поиска:', reply_markup=reply_markup)
        return SELECTING_FILTER

    if reporter in context.user_data['selected_reporters']:
        context.user_data['selected_reporters'].remove(reporter)
    else:
        context.user_data['selected_reporters'].append(reporter)

    reply_markup = generate_keyboard(
        reporters, context.user_data['selected_reporters'])
    await query.edit_message_text(
        text='Выберите репортеров:', reply_markup=reply_markup)
    return SELECTING_REPORTER


async def size_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    size = query.data
    if size == 'continue':
        reply_markup = generate_filter_menu(context)
        await query.edit_message_text(
            text='Критерии поиска:', reply_markup=reply_markup)
        return SELECTING_FILTER

    if size in context.user_data['selected_sizes']:
        context.user_data['selected_sizes'].remove(size)
    else:
        context.user_data['selected_sizes'].append(size)

    reply_markup = generate_keyboard(sizes, context.user_data['selected_sizes'])
    await query.edit_message_text(
        text='Выберите размеры:', reply_markup=reply_markup)
    return SELECTING_SIZE


async def filter_min_price(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text='Введите минимальную цену (в €)\nВведите 0 для сброс фильтра:')
    context.user_data['price_step'] = 'min'
    return SELECTING_MIN_PRICE


async def filter_max_price(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text='Введите максимальную цену (в €)\nВведите 0 для сброс фильтра:')
    context.user_data['price_step'] = 'max'
    return SELECTING_MAX_PRICE


async def price_choice(update: Update, context: CallbackContext):
    text = update.message.text
    price_step = context.user_data.get('price_step')

    if not text.isdigit() or int(text) < 0:
        await update.message.reply_text(
            'Цена должна быть положительным целым числом\nКритерии поиска:',
            reply_markup=generate_filter_menu(context))
        return SELECTING_FILTER

    if int(text) == 0:
        context.user_data['min_price'] = None
        context.user_data['max_price'] = None
        await update.message.reply_text(
            'Фильтр по цене сброшен.\nКритерии поиска обновлены:',
            reply_markup=generate_filter_menu(context))
        return SELECTING_FILTER

    if price_step == 'min':
        max_price = context.user_data.get('max_price')
        if max_price and int(max_price) < int(text):
            await update.message.reply_text(
                'Минимальная цена должна быть меньше максимальной\nКритерии поиска:',
                reply_markup=generate_filter_menu(context))
            return SELECTING_FILTER

        context.user_data['min_price'] = text
        await update.message.reply_text('Критерии поиска обновлены:', reply_markup=generate_filter_menu(context))
        return SELECTING_FILTER
    elif price_step == 'max':
        min_price = context.user_data.get('min_price')
        if min_price and int(text) <= int(min_price):
            await update.message.reply_text('Максимальная цена должна быть больше минимальной\nКритерии поиска:', reply_markup=generate_filter_menu(context))
            return SELECTING_FILTER

        context.user_data['max_price'] = text
        await update.message.reply_text('Критерии поиска обновлены:', reply_markup=generate_filter_menu(context))
        return SELECTING_FILTER


async def district_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    district = query.data
    if district == 'continue':
        reply_markup = generate_filter_menu(context)
        await query.edit_message_text(text='Критерии поиска:', reply_markup=reply_markup)
        return SELECTING_FILTER

    if district in context.user_data['selected_districts']:
        context.user_data['selected_districts'].remove(district)
    else:
        context.user_data['selected_districts'].append(district)

    selected_city = context.user_data.get('selected_city', [None])[0]
    if selected_city == 'Белград':
        options = districts_belgrade
    elif selected_city == 'Нови Сад':
        options = districts_novisad
    else:
        options = {}

    reply_markup = generate_keyboard(options, context.user_data['selected_districts'])
    await query.edit_message_text(text='Выберите районы:', reply_markup=reply_markup)
    return SELECTING_DISTRICT


async def property_type_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    property_type = query.data
    if property_type == 'continue':
        reply_markup = generate_filter_menu(context)
        await query.edit_message_text(text='Критерии поиска:', reply_markup=reply_markup)
        return SELECTING_FILTER

    if property_type in context.user_data['selected_property_types']:
        context.user_data['selected_property_types'].remove(property_type)
    else:
        context.user_data['selected_property_types'].append(property_type)

    reply_markup = generate_keyboard(property_types, context.user_data['selected_property_types'])
    await query.edit_message_text(text='Выберите типы недвижимости:', reply_markup=reply_markup)
    return SELECTING_PROPERTY_TYPE

async def rooms_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    room = query.data
    if room == 'continue':
        reply_markup = generate_filter_menu(context)
        await query.edit_message_text(text='Критерии поиска:', reply_markup=reply_markup)
        return SELECTING_FILTER

    if room in context.user_data['selected_rooms']:
        context.user_data['selected_rooms'].remove(room)
    else:
        context.user_data['selected_rooms'].append(room)

    reply_markup = generate_keyboard(rooms, context.user_data['selected_rooms'])
    await query.edit_message_text(text='Выберите количество комнат:', reply_markup=reply_markup)
    return SELECTING_ROOMS

async def start_search(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    selected_city = context.user_data.get('selected_city', [])
    selected_city = selected_city[0] if selected_city else ''

    if not selected_city:
        reply_markup = generate_filter_menu(context)
        await query.edit_message_text(
            '''
⚠️ Необходимо выбрать город.
            ''',
            reply_markup=reply_markup
        )
        return SELECTING_FILTER

    user_id = update.effective_user.id

    # Удаляем текущие задания пользователя из JobQueue
    current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
    for job in current_jobs:
        logger.info(f'Удаление задания для user_id {user_id}')
        job.schedule_removal()

    # Удаляем текущую задачу из базы данных
    task_response = requests.delete(f'{TASK_API_URL}delete-by-user-id?user_id={user_id}')
    if task_response.status_code == 204:
        logger.info(f'Задача для user_id {user_id} успешно удалена')
    elif task_response.status_code != 404:
        logger.error(f'Ошибка удаления задачи для user_id {user_id}: {task_response.status_code} {task_response.content}')

    # Создание новой задачи с обновленными критериями
    response = requests.post(TASK_API_URL, json={
        'user_id': user_id,
        'city': selected_city,
        'interval': INTERVAL,
        'reporters': context.user_data['selected_reporters'],
        'sizes': context.user_data['selected_sizes'],
        'min_price': context.user_data['min_price'],
        'max_price': context.user_data['max_price'],
        'districts': context.user_data['selected_districts'],
        'property_types': context.user_data['selected_property_types'],
        'rooms': context.user_data['selected_rooms'],
        'isReady': True
    })
    if response.status_code != 201:
        logger.error(f'Ошибка добавления задачи в API: {response.status_code} {response.content}')
        return ConversationHandler.END
    else:
        task = response.json()
        last_sent_date = None

    # Добавление нового задания в JobQueue
    context.application.job_queue.run_repeating(send_listings, interval=INTERVAL, data={
        'user_id': user_id,
        'selected_city': selected_city,
        'selected_reporters': context.user_data['selected_reporters'],
        'selected_sizes': context.user_data['selected_sizes'],
        'min_price': context.user_data['min_price'],
        'max_price': context.user_data['max_price'],
        'selected_districts': context.user_data['selected_districts'],
        'selected_property_types': context.user_data['selected_property_types'],
        'selected_rooms': context.user_data['selected_rooms']
    }, name=str(user_id))

    # Формирование текста с фильтрами
    filter_text = f"✅ Начинаю поиск по условиям:\n"
    filter_text += f"Город: <b>{cities[selected_city]}</b>\n"
    filter_text += f"Район: <b>{', '.join(context.user_data['selected_districts'])}</b>\n" if context.user_data['selected_districts'] else ""
    filter_text += f"Площадь: <b>{', '.join(context.user_data['selected_sizes'])}</b>\n" if context.user_data['selected_sizes'] else ""
    filter_text += f"Цена(€): <b>{context.user_data['min_price']} - {context.user_data['max_price']}</b>\n" if context.user_data['min_price'] and context.user_data['max_price'] else ""
    filter_text += f"Тип недвижимости: <b>{', '.join(context.user_data['selected_property_types'])}</b>\n" if context.user_data['selected_property_types'] else ""
    filter_text += f"Количество комнат: <b>{', '.join(context.user_data['selected_rooms'])}</b>\n" if context.user_data['selected_rooms'] else ""
    filter_text += f"Разместил: <b>{', '.join(context.user_data['selected_reporters'])}</b>\n" if context.user_data['selected_reporters'] else ""

    await query.edit_message_text(text=filter_text, parse_mode='HTML')


async def send_listings(context: CallbackContext):
    job = context.job
    user_id = job.data['user_id']
    selected_city = job.data['selected_city']
    selected_reporters = job.data['selected_reporters']
    selected_sizes = job.data['selected_sizes']
    min_price = job.data['min_price']
    max_price = job.data['max_price']
    selected_districts = job.data['selected_districts']
    selected_property_types = job.data['selected_property_types']
    selected_rooms = job.data['selected_rooms']

    try:
        # Проверяем сохранилось ли состояние пользователя в БД
        task_response = requests.get(f'{TASK_API_URL}filter-by-user-id?user_id={user_id}')
        if task_response.status_code != 200 or not task_response.json():
            logger.error(f'Задача для user_id {user_id} не найдена.')
            job.schedule_removal()
            return

        tasks = task_response.json()
        task = tasks[0]
        if not task.get('isReady'):
            logger.info(f'Задача для user_id {user_id} не готова для выполнения.')
            return

        last_sent_date = task.get('last_sent_date')
        if last_sent_date:
            last_sent_date = parser.isoparse(last_sent_date)

        params = {
            'city': selected_city,
            'last_sent_date': last_sent_date.strftime('%Y-%m-%d %H:%M:%S') if last_sent_date else '',
        }

        if selected_reporters:
            params['reporters'] = selected_reporters
        if selected_sizes:
            params['sizes'] = selected_sizes
        if min_price:
            params['min_price'] = min_price
        if max_price:
            params['max_price'] = max_price
        if selected_districts:
            params['districts'] = selected_districts
        if selected_property_types:
            params['property_types'] = selected_property_types
        if selected_rooms:
            params['rooms'] = selected_rooms

        response = requests.get(ADV_API_URL, params=params)
        if response.status_code == 200:
            listings = response.json()
            logger.info(f'Получено {len(listings)} объявлений для города {selected_city}')
            new_listings = listings
            max_inserted_at = last_sent_date

            if new_listings:
                for listing in new_listings:
                    reply_text = (
                        f"<b>{listing['city']}, {listing['district']}</b>\n"
                        f"{listing['type']}, <b>{listing['size']} m2</b>\n"
                        f"Количество комнат: <b>{listing['rooms']}</b>\n"
                        f"Разместил: <b>{listing['reporter']}</b>\n\n"
                        f"<b>{listing['price']} {listing['currency']}</b>\n\n"
                        f"<i>от {listing['published']}</i>\n"
                        f"Источник: <a href='{listing['url']}'>{listing['src']}</a>"
                    )
                    image_url = listing['image_url']

                    if image_url:
                        try:
                            await context.bot.send_photo(chat_id=job.data['user_id'], photo=image_url, caption=reply_text, parse_mode='HTML')
                        except Exception as e:
                            logger.error(f'Ошибка отправки фото: {e}')
                            await context.bot.send_message(chat_id=job.data['user_id'], text=reply_text, parse_mode='HTML')
                    else:
                        await context.bot.send_message(chat_id=job.data['user_id'], text=reply_text, parse_mode='HTML')

                    inserted_at = parser.isoparse(listing['insertedAt'])
                    if inserted_at > max_inserted_at:
                        max_inserted_at = inserted_at

                if max_inserted_at > last_sent_date:
                    new_last_sent_date = max_inserted_at + timedelta(seconds=1)
                    requests.patch(f"{TASK_API_URL}{task['id']}/", json={'last_sent_date': new_last_sent_date.isoformat()})
            else:
                logger.info(f'Нет новых объявлений для города {selected_city}')
        else:
            logger.error(f'Ошибка получения объявлений для города {selected_city}: {response.status_code} {response.content}')
    except Exception:
        logger.exception(f'Произошла ошибка при получении объявлений для города {selected_city}')


async def feedback(update: Update, context: CallbackContext):
    await update.message.reply_text(
            '''
Привет!
Буду благодарен за отзывы и предложения по работе бота.
Пиши @farrukh_rus.
            '''
        )


async def inactive_button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer('Сначала выберите город.', show_alert=True)


async def stop(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    # Очищаем контекст
    context.user_data.clear()
    logger.info(f'Удаление автоматического задания у пользователя {user_id}')

    # Удаление задания из JobQueue
    current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
    for job in current_jobs:
        logger.info(f'Удаление джоба {user_id}')
        job.schedule_removal()

    response = requests.delete(f'{TASK_API_URL}delete-by-user-id?user_id={user_id}')
    if response.status_code == 404:
        logger.info(f'Задача для user_id {user_id} не найдена.')
    elif response.status_code != 204:
        logger.error(f'Ошибка удаления задачи из API: {response.status_code} {response.content}')

    # !!! Переделать логику так, чтобы при /stop сохранялись фильтры в БД
    # Можно зацепиться за поле isReady
    await update.message.reply_text(
            '''
Поиск остановлен. Нажмите /start, чтобы возобновить поиск.
            '''
        )


async def reset(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    # Очищаем контекст
    context.user_data.clear()
    logger.info(f'Удаление автоматического задания у пользователя {user_id}')

    # Удаление задания из JobQueue
    current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
    for job in current_jobs:
        logger.info(f'Удаление джоба {user_id}')
        job.schedule_removal()

    response = requests.delete(f'{TASK_API_URL}delete-by-user-id?user_id={user_id}')
    if response.status_code == 404:
        logger.info(f'Задача для user_id {user_id} не найдена.')
    elif response.status_code != 204:
        logger.error(f'Ошибка удаления задачи из API: {response.status_code} {response.content}')

    # Возвращение к начальному состоянию
    await begin_selection(update, context)
    return SELECTING_FILTER


# Восстановить задачи из БД
def restore_tasks(job_queue):
    response = requests.get(TASK_API_URL)
    if response.status_code == 200:
        tasks = response.json()
        for task in tasks:
            if task['isReady']:
                job_queue.run_repeating(send_listings, interval=task['interval'], data={
                    'user_id': task['user_id'],
                    'selected_city': task['city'],
                    'selected_reporters': task['reporters'],
                    'selected_sizes': task['sizes'],
                    'min_price': task['min_price'],
                    'max_price': task['max_price'],
                    'selected_districts': task['districts'],
                    'selected_property_types': task['property_types'],
                    'selected_rooms': task['rooms']
                }, name=str(task['user_id']))
                belgrade_tz = pytz.timezone('Europe/Belgrade')
                new_last_sent_date = datetime.now(belgrade_tz) + timedelta(seconds=1)
                requests.patch(f"{TASK_API_URL}{task['id']}/", json={'last_sent_date': new_last_sent_date.isoformat()})
    else:
        logger.error(f'Ошибка получения задач из API: {response.status_code} {response.content}')
        sys.exit(1)


def main():
    job_queue = JobQueue()
    application = Application.builder().token(TOKEN).job_queue(job_queue).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start),
                      CommandHandler('reset', reset),
                      CommandHandler('feedback', feedback),
                      CommandHandler('stop', stop)],
        states={
            SELECTING_FILTER: [
                CallbackQueryHandler(
                    filter_city, pattern='^filter_city$'),
                CallbackQueryHandler(
                    filter_reporter, pattern='^filter_reporter$'),
                CallbackQueryHandler(
                    filter_size, pattern='^filter_size$'),
                CallbackQueryHandler(
                    filter_min_price, pattern='^filter_min_price$'),
                CallbackQueryHandler(
                    filter_max_price, pattern='^filter_max_price$'),
                CallbackQueryHandler(
                    filter_district, pattern='^filter_district$'),
                CallbackQueryHandler(
                    filter_property_type, pattern='^filter_property_type$'),
                CallbackQueryHandler(
                    filter_rooms, pattern='^filter_rooms$'),
                CallbackQueryHandler(
                    start_search, pattern='^start_search$'),
                CallbackQueryHandler(
                    inactive_button, pattern='^inactive$')
            ],
            SELECTING_CITY: [
                CallbackQueryHandler(
                    city_choice, pattern='^({}|continue)$'.format('|'.join(map(re.escape, cities.keys())))),
            ],
            SELECTING_REPORTER: [
                CallbackQueryHandler(
                    reporter_choice, pattern='^({}|continue)$'.format('|'.join(map(re.escape, reporters.keys())))),
            ],
            SELECTING_SIZE: [
                CallbackQueryHandler(
                    size_choice, pattern='^({}|continue)$'.format('|'.join(map(re.escape, sizes.keys())))),
            ],
            SELECTING_MIN_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, price_choice),
            ],
            SELECTING_MAX_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, price_choice),
            ],
            SELECTING_DISTRICT: [
                CallbackQueryHandler(
                    district_choice, pattern='^({}|continue)$'.format('|'.join(map(re.escape, {**districts_belgrade, **districts_novisad}.keys())))),
            ],
            SELECTING_PROPERTY_TYPE: [
                CallbackQueryHandler(
                    property_type_choice, pattern='^({}|continue)$'.format('|'.join(map(re.escape, property_types.keys())))),
            ],
            SELECTING_ROOMS: [
                CallbackQueryHandler(
                    rooms_choice, pattern='^({}|continue)$'.format('|'.join(map(re.escape, rooms.keys())))),
            ],
        },
        fallbacks=[CommandHandler('start', start),
                   CommandHandler('reset', reset),
                   CommandHandler('feedback', feedback),
                   CommandHandler('stop', stop)]
    )

    application.add_handler(conv_handler)

    job_queue.set_application(application)
    job_queue.start()

    restore_tasks(job_queue)

    application.run_polling()


if __name__ == '__main__':
    main()
