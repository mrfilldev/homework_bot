import os
import sys
import time
import logging
from datetime import date, datetime

from dotenv import load_dotenv
import requests
import telegram

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


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
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
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params,
        )
    except requests.RequestException as request_error:
        api_message = f'Код ответе API: {request_error}'
        raise StatusError(api_message)
    if response.status_code != 200:
        api_message = (
            f'Эндпоинт {ENDPOINT} недоступен.'
            f' Код ответа API: {response.status_code}')
        logger.error(api_message)
        raise StatusError(api_message)
    return response.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('response - не словарь')
    if 'homeworks' not in response:
        raise KeyError('Нет ключа')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(f'homeworks не list {homeworks}')
    if not homeworks:
        raise KeyError(f'homeworks - пуст: {homeworks}')
    return homeworks


def parse_status(homework):
    """Парсинг данных из ответа  API."""
    if not (('homework_name' in homework) and ('status' in homework)):
        raise KeyError('не обнаружены требуемые ключи в homework')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    message = 'status invalid'
    if homework_status not in HOMEWORK_STATUSES:
        logger.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens_check = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    list_check = ''
    for key, value in tokens_check.items():
        if not value:
            list_check += str(key) + '\n'
            logger.critical(
                f'Нет переменной окружения {list_check}'
            )
    if list_check != '':
        return False
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_time = str(date.today()) + ' ' + str(datetime.now().time())
    count = 0
    send_message(bot, f'Запуск бота \nдата: {current_time}')
    while True:
        send_message(bot, f'новый цикл \nциклов: {count}')
        count += 1
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            send_message(bot, parse_status(homeworks[0]))
            logger.info('Изменений не было, ждем и проверяем еще раз.')
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(message)
        finally:
            time.sleep(TELEGRAM_RETRY_TIME)


result = check_tokens()
if result:
    if __name__ == '__main__':
        main()
