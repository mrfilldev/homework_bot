import os
import sys

import time
import requests
import telegram
import logging

from dotenv import load_dotenv

from exceptions import StatusError

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TELEGRAM_RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

TOKENS_CHECK = {
    'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
    'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
}


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(url=TELEGRAM_CHAT_ID, message=message)
        logger.info(
            f'Отправка сообщения {message}.'
        )
    except telegram.TelegramError:
        logger.exception(
            f'Сообщение {message} не отправлено. ОШИБКА!'
        )


def get_api_answer(current_timestamp):
    """Получене ответа от ENDPOINT."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params=params)
        if response.status_code != 200:
            api_message = (
                f'Эндпоинт {ENDPOINT} недоступен.'
                f' Код ответа API: {response.status_code}')
            logger.error(api_message)
            raise StatusError(api_message)
        return response.json()
    except requests.RequestException as request_error:
        api_message = f'Код ответе API: {request_error}'
        raise StatusError(api_message)


def check_response(response):
    """Проверка ответа API на корректность."""
    try:
        if isinstance(response, dict):
            homeworks = response['homeworks']
        else:
            raise TypeError('response - не словарь')
    except KeyError:
        raise KeyError('Нет ключа')
    if not isinstance(homeworks, list):
        raise TypeError(f'homeworks не list {homeworks}')
    if homeworks.count == 0:
        raise KeyError(f'homeworks - пуст: {homeworks}')
    return homeworks


def parse_status(homework):
    """Парсинг данных из ответа  API."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    message = 'status invalid'
    verdict = HOMEWORK_STATUSES[homework_status]
    if homework_status not in HOMEWORK_STATUSES:
        logger.error(message)
        raise KeyError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    for key, value in TOKENS_CHECK.items():
        if not value:
            logger.critical(
                f'Нет переменной окружения {key}.'
            )
            return False
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            send_message(bot, parse_status(homeworks[0]))
            logger.info('Изменений не было, ждем и проверяем еще раз.')
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(message)
        finally:
            time.sleep(TELEGRAM_RETRY_TIME)


if __name__ == '__main__':
    if check_tokens():
        main()
