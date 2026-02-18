import subprocess
import os
import time
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import socket
import json
import re

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    print("Для цветного вывода: pip install colorama\n")

def colored(text, color_code=''):
    """Возвращает цветной текст если colorama доступна"""
    if COLORS_AVAILABLE and color_code:
        return f"{color_code}{text}{Style.RESET_ALL}"
    return text

def setup_logger(log_file, max_bytes=10*1024*1024, backup_count=5):
    """
    Настраивает логгер с ротацией файлов
    max_bytes: максимальный размер файла (по умолчанию 10 МБ)
    backup_count: количество backup копий (download.log.1, download.log.2, ...)
    """
    logger = logging.getLogger('yt_download')
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )

    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger

def is_playlist_url(url):
    """Проверяет является ли URL плейлистом"""
    playlist_patterns = [
        r'[?&]list=',
        r'/playlist\?',
        r'youtube\.com/c/',
        r'youtube\.com/@',
        r'youtube\.com/channel/',
        r'youtube\.com/user/'
    ]
    return any(re.search(pattern, url) for pattern in playlist_patterns)

def get_playlist_info(url, archive_file, logger=None):
    """
    Получает информацию о плейлисте: общее количество видео и сколько уже скачано
    Возвращает: (total_videos, downloaded_videos, remaining_videos)
    """
    try:
        if logger:
            logger.info(f"  Проверка прогресса плейлиста...")

        cmd = [
            'yt-dlp',
            '--flat-playlist',
            '--print', 'id',
            '--no-warnings',
            url
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            if logger:
                logger.warning(f"  Не удалось получить список видео плейлиста")
            return (0, 0, 0)

        all_video_ids = set(result.stdout.strip().split('\n'))
        all_video_ids.discard('')
        total_videos = len(all_video_ids)

        downloaded_ids = set()
        if os.path.exists(archive_file):
            with open(archive_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        parts = line.split()
                        if len(parts) >= 2:
                            downloaded_ids.add(parts[1])

        downloaded_from_playlist = all_video_ids.intersection(downloaded_ids)
        downloaded_count = len(downloaded_from_playlist)
        remaining_count = total_videos - downloaded_count

        if logger:
            logger.info(f"  Плейлист: всего {total_videos}, скачано {downloaded_count}, осталось {remaining_count}")

        return (total_videos, downloaded_count, remaining_count)

    except subprocess.TimeoutExpired:
        if logger:
            logger.warning(f"  Таймаут при проверке плейлиста")
        return (0, 0, 0)
    except Exception as e:
        if logger:
            logger.error(f"  Ошибка проверки плейлиста: {e}")
        return (0, 0, 0)

def generate_nfo_file(info_json_path, logger=None):
    """
    Генерирует .nfo файл из .info.json для Kodi/Plex
    """
    try:
        with open(info_json_path, 'r', encoding='utf-8') as f:
            info = json.load(f)

        nfo_path = info_json_path.replace('.info.json', '.nfo')

        title = info.get('title', 'Unknown')
        video_id = info.get('id', '')
        uploader = info.get('uploader', info.get('channel', 'Unknown'))
        description = info.get('description', '')
        upload_date = info.get('upload_date', '')

        year = upload_date[:4] if len(upload_date) >= 4 else ''
        month_day = upload_date[4:] if len(upload_date) >= 8 else ''
        formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]} 00:00:00Z" if len(upload_date) == 8 else ''

        nfo_content = f"""<movie>
<title>{title}</title>
<studio>{uploader}</studio>
<uniqueid type="youtube">{video_id}</uniqueid>
<plot>{description}</plot>
<premiered>{formatted_date}</premiered>
<year>{year}</year>
<sorttitle>{month_day}</sorttitle>
<source>YouTube</source>
</movie>"""

        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)

        if logger:
            logger.info(f"  Создан .nfo файл: {os.path.basename(nfo_path)}")
        return True

    except Exception as e:
        if logger:
            logger.error(f"  Ошибка создания .nfo: {e}")
        return False

def check_dns_resolution(host='www.youtube.com', timeout=10):
    """
    Проверяет возможность разрешения DNS для указанного хоста
    Возвращает True если DNS работает, False в противном случае
    """
    try:
        socket.setdefaulttimeout(timeout)
        result = socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        return len(result) > 0
    except (socket.gaierror, socket.timeout, OSError) as e:
        return False

def wait_for_dns_recovery(host='www.youtube.com', check_interval=60, max_wait=3600):
    """
    Ожидает восстановления DNS разрешения
    check_interval: интервал проверки в секундах
    max_wait: максимальное время ожидания в секундах
    """
    print(colored(f"\n⚠ DNS недоступен для {host}", Fore.YELLOW))
    print(colored(f"Ожидание восстановления (проверка каждые {check_interval}с)...", Fore.YELLOW))
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(check_interval)
        elapsed += check_interval
        if check_dns_resolution(host):
            print(colored(f"✓ DNS восстановлен после {elapsed}с", Fore.GREEN))
            return True
        mins_left = (max_wait - elapsed) // 60
        print(f"\r⏳ Прошло {elapsed}с, осталось ~{mins_left}м... ", end='', flush=True)
    print(colored(f"\n✗ DNS не восстановлен за {max_wait}с", Fore.RED))
    return False

def check_ytdlp_installed():
    """Проверяет установлен ли yt-dlp и его версию"""
    try:
        result = subprocess.run(['yt-dlp', '--version'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(colored(f"✓ yt-dlp версия: {version}", Fore.GREEN))

            ffmpeg_check = subprocess.run(['ffmpeg', '-version'],
                                          capture_output=True, timeout=5)
            if ffmpeg_check.returncode == 0:
                print(colored("✓ ffmpeg найден", Fore.GREEN))
            else:
                print(colored("⚠ ffmpeg не найден - слияние форматов недоступно", Fore.YELLOW))
            print()
            return True
    except FileNotFoundError:
        print(colored("✗ yt-dlp не найден! Установите: pip install -U yt-dlp", Fore.RED))
        return False
    except Exception as e:
        print(colored(f"✗ Ошибка проверки: {e}", Fore.RED))
        return False

def format_time(seconds):
    """Форматирует секунды в читаемый формат"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}ч {minutes}м {secs}с"
    elif minutes > 0:
        return f"{minutes}м {secs}с"
    else:
        return f"{secs}с"

def read_links_file(links_path):
    """Читает файл со ссылками"""
    with open(links_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    links = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and stripped.startswith('http'):
            links.append(stripped)
    return links

def classify_error(line_lower, error_keywords):
    """Классифицирует ошибки по категориям"""
    error_type = {
        'skip': False,
        'retry': False,
        'pause': 0,
        'fatal': False,
        'dns_error': False,
        'message': ''
    }

    # DNS ошибки
    if 'failed to resolve' in line_lower or 'getaddrinfo failed' in line_lower:
        error_type.update({
            'dns_error': True,
            'retry': True,
            'pause': 30,
            'message': 'DNS ошибка - проверьте интернет-соединение'
        })
        return error_type

    # Rate limit
    if 'rate-limited' in line_lower or 'rate limit' in line_lower:
        error_type.update({
            'retry': False,
            'pause': 3600,
            'message': 'Ограничение YouTube! Пауза 1 час'
        })
        return error_type

    # Обнаружение бота
    if 'sign in' in line_lower and 'bot' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 300,
            'message': 'Обнаружен бот! Пауза 5 минут'
        })
        return error_type

    # HTTP ошибки
    if 'http error 403' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 600,
            'message': 'HTTP 403: Проблема с cookies/доступом'
        })
    elif 'http error 429' in line_lower:
        error_type.update({
            'retry': False,
            'pause': 1800,
            'message': 'HTTP 429: Слишком много запросов'
        })
    elif 'http error 400' in line_lower:
        error_type.update({
            'retry': True,
            'message': 'HTTP 400: Возможно устаревшая версия yt-dlp'
        })
    elif 'http error 404' in line_lower or 'http error 410' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Видео удалено'
        })

    # Недоступность контента
    if 'private video' in line_lower or 'members-only' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Приватное видео или только для подписчиков'
        })
    elif 'video unavailable' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Видео недоступно'
        })
    elif 'premieres in' in line_lower or 'will begin in' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Запланированная премьера - еще не доступно'
        })
    elif 'age-restricted' in line_lower or 'age restricted' in line_lower:
        error_type.update({
            'retry': True,
            'message': 'Ограничение по возрасту - проверьте cookies'
        })
    elif 'geo' in line_lower and ('blocked' in line_lower or 'restricted' in line_lower):
        error_type.update({
            'skip': True,
            'message': 'Гео-блокировка'
        })
    elif 'copyright' in line_lower or 'takedown' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Удалено по авторским правам'
        })
    elif 'requires payment' in line_lower or 'rental' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Требуется оплата'
        })

    # Системные ошибки
    if 'timeout' in line_lower or 'timed out' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 30,
            'message': 'Таймаут соединения'
        })
    elif 'connection' in line_lower and 'error' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 60,
            'message': 'Ошибка соединения'
        })
    elif 'no space left' in line_lower or 'disk full' in line_lower:
        error_type.update({
            'fatal': True,
            'message': 'Диск заполнен!'
        })
    elif 'permission denied' in line_lower or 'access denied' in line_lower:
        error_type.update({
            'fatal': True,
            'message': 'Нет прав доступа к файлу/директории'
        })
    elif ('ffmpeg' in line_lower or 'ffprobe' in line_lower) and 'not found' in line_lower:
        error_type.update({
            'fatal': True,
            'message': 'ffmpeg не найден - невозможно объединить форматы'
        })

    return error_type

def download_single_url(url, idx, total, script_dir, downloads_dir, archive_file, logger):
    """
    Скачивает видео по одному URL (может быть одно видео или плейлист)
    Возвращает (success_count, skip_count, fail_count, failed_url_or_none, consecutive_dns_errors, fatal)
    """
    print(f"\n{colored('='*70, Fore.BLUE)}")
    print(colored(f"[{idx}/{total}] {url}", Fore.YELLOW))
    print(colored('='*70, Fore.BLUE))
    logger.info(f"\n[{idx}/{total}] URL: {url}")

    # Проверяем, является ли URL плейлистом
    is_playlist = is_playlist_url(url)
    if is_playlist:
        print(colored("📋 Обнаружен ПЛЕЙЛИСТ", Fore.CYAN))
        logger.info("  Тип: ПЛЕЙЛИСТ")

    url_start_time = time.time()

    # ── ИЗМЕНЕНИЕ 1: Определяем шаблон пути в зависимости от типа URL ──────
    if is_playlist:
        output_template = os.path.join(
            downloads_dir,
            '%(playlist_title,uploader,channel).100s',  # папка = название плейлиста/канала
            '%(title).200s [%(id)s].%(ext)s'
        )
    else:
        output_template = os.path.join(
            downloads_dir,
            '%(title).200s [%(id)s].%(ext)s'           # одиночное видео — в корень downloads/
        )
    # ────────────────────────────────────────────────────────────────────────

    # КОМАНДА yt-dlp с оптимизацией для нестабильного соединения
    cmd = [
        'yt-dlp',
        '--cookies-from-browser', 'firefox',
        '--remote-components', 'ejs:github',
        # Формат и конвертация
        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        '--merge-output-format', 'mp4',
        '--remux-video', 'mp4',
        # Попытки повтора
        '--retries', '15',
        '--fragment-retries', '15',
        '--extractor-retries', '8',
        '--file-access-retries', '5',
        # Задержки
        '--sleep-requests', '5',
        '--sleep-interval', '20',
        '--max-sleep-interval', '60',
        # Таймауты
        '--socket-timeout', '60',
        # Оптимизация загрузки
        '--concurrent-fragments', '1',
        '--buffer-size', '16K',
        # Метаданные и обложки
        '--embed-metadata',
        '--embed-thumbnail',
        '--write-thumbnail',
        '--convert-thumbnails', 'jpg',
        '--write-info-json',
        # Именование файлов
        '--windows-filenames',
        '--output', output_template,        # ── ИЗМЕНЕНИЕ 2: динамический шаблон
        # Обработка ошибок
        '--no-check-certificate',
        '--no-overwrites',
        '--download-archive', archive_file,
        '--ignore-errors',
        '--no-abort-on-error',
        # Прогресс
        '--newline',
        '--progress',
        '--console-title',
        url
    ]

    max_attempts = 3
    attempt = 0
    success = False
    should_skip = False
    consecutive_dns_errors = 0
    max_consecutive_dns_errors = 20
    success_count = 0
    skip_count = 0
    fail_count = 0

    while attempt < max_attempts and not success and not should_skip:
        attempt += 1
        if attempt > 1:
            msg = f"ПОПЫТКА ПОВТОРА {attempt}/{max_attempts}"
            print(f"\n{colored(f'⚠ {msg}', Fore.YELLOW)}")
            logger.info(f"  {msg}")
            time.sleep(5)

        try:
            process = subprocess.Popen(
                cmd,
                cwd=script_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            error_keywords = []
            last_line_was_progress = False
            dns_errors_in_attempt = 0
            videos_downloaded = 0
            videos_already_in_archive = 0

            # Таймаут для всего процесса - 120 минут для плейлиста, 60 для одного видео
            start_time = time.time()
            timeout_seconds = 7200 if is_playlist else 3600

            while True:
                # Проверка таймаута
                if time.time() - start_time > timeout_seconds:
                    process.kill()
                    timeout_mins = timeout_seconds // 60
                    msg = f"ТАЙМАУТ! Процесс завис более чем на {timeout_mins} минут"
                    print(colored(f"\n⚠ {msg}", Fore.RED))
                    logger.warning(f"  {msg}")
                    break

                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    line = line.rstrip()
                    line_lower = line.lower()

                    # Подсчет скачанных видео
                    if '[download] downloading item' in line_lower:
                        match = re.search(r'downloading item (\d+) of (\d+)', line_lower)
                        if match:
                            current = int(match.group(1))
                            total_in_playlist = int(match.group(2))
                            print(colored(f"📊 Прогресс плейлиста: {current}/{total_in_playlist}", Fore.MAGENTA))

                    # Уже скачано
                    if 'has already been downloaded' in line_lower or 'has already been recorded in the archive' in line_lower:
                        videos_already_in_archive += 1
                        print(colored(line, Fore.CYAN))
                        logger.info(f"  {line}")
                        continue

                    # Успешная загрузка файла
                    if '[download] 100%' in line or 'has already been downloaded' in line_lower:
                        if 'has already been downloaded' not in line_lower:
                            videos_downloaded += 1

                    # Сбор ошибок
                    if 'error' in line_lower or 'warning' in line_lower:
                        error_keywords.append(line)

                        # Специальная обработка DNS ошибок
                        if 'failed to resolve' in line_lower or 'getaddrinfo failed' in line_lower:
                            dns_errors_in_attempt += 1
                            consecutive_dns_errors += 1
                            logger.error(f"  DNS ERROR #{consecutive_dns_errors}: {line}")
                        else:
                            logger.error(f"  ERROR: {line}")

                    # Прогресс загрузки
                    if '[download]' in line and '%' in line:
                        sys.stdout.write('\r' + ' ' * 100 + '\r')
                        sys.stdout.write(colored(line, Fore.GREEN))
                        sys.stdout.flush()
                        last_line_was_progress = True
                    else:
                        if last_line_was_progress:
                            print()
                        last_line_was_progress = False

                        # Цветной вывод
                        if line.startswith('[download]'):
                            print(colored(line, Fore.CYAN))
                        elif 'Merging' in line or 'merger' in line_lower:
                            print(colored(line, Fore.MAGENTA))
                        elif line.startswith('['):
                            print(colored(line, Fore.BLUE))
                        else:
                            print(line)

            if last_line_was_progress:
                print()

            return_code = process.wait()
            url_duration = time.time() - url_start_time

            # Анализ результата
            if return_code == 0:
                if videos_already_in_archive > 0 and videos_downloaded == 0:
                    msg = f"⊘ ВСЕ УЖЕ СКАЧАНО ({videos_already_in_archive} видео в архиве)"
                    print(f"\n{colored(msg, Fore.CYAN)}")
                    logger.info(f"  {msg}")
                    skip_count = videos_already_in_archive
                else:
                    msg = f"✓ УСПЕХ за {format_time(url_duration)}"
                    if videos_downloaded > 0:
                        msg += f" (скачано: {videos_downloaded} видео)"
                    print(f"\n{colored(msg, Fore.GREEN)}")
                    logger.info(f"  {msg}")
                    success_count = max(1, videos_downloaded)
                    skip_count = videos_already_in_archive
                    consecutive_dns_errors = 0
                success = True

            elif return_code == 2:
                msg = "✗ ОШИБКА ПАРАМЕТРОВ КОМАНДЫ! (exit code 2)"
                print(f"\n{colored(msg, Fore.RED)}")
                logger.error(f"  {msg}")
                should_skip = True
                fail_count = 1

            elif return_code == 101:
                msg = "⊘ ЗАГРУЗКА ОТМЕНЕНА (exit code 101)"
                print(f"\n{colored(msg, Fore.CYAN)}")
                logger.info(f"  {msg}")
                should_skip = True
                skip_count = 1

            else:
                msg = f"✗ ОШИБКА (exit code: {return_code})"
                print(f"\n{colored(msg, Fore.RED)}")
                logger.error(f"  {msg}")

                # Классификация ошибок
                pause_time = 0
                should_retry = False
                fatal_error = False
                has_dns_error = False

                for error in error_keywords:
                    error_class = classify_error(error.lower(), error_keywords)
                    if error_class['message']:
                        print(colored(f"  ⚠ {error_class['message']}", Fore.YELLOW))
                        logger.warning(f"  {error_class['message']}")
                    if error_class['skip']:
                        should_skip = True
                    if error_class['retry']:
                        should_retry = True
                    if error_class['pause'] > pause_time:
                        pause_time = error_class['pause']
                    if error_class['fatal']:
                        fatal_error = True
                    if error_class['dns_error']:
                        has_dns_error = True

                # Фатальная ошибка - остановка всего
                if fatal_error:
                    msg = "✗ ФАТАЛЬНАЯ ОШИБКА! Остановка скрипта"
                    print(colored(f"\n{msg}", Fore.RED))
                    logger.critical(msg)
                    return (0, 0, 0, None, consecutive_dns_errors, True)  # fatal=True

                # Проверка критического количества DNS ошибок
                if has_dns_error and consecutive_dns_errors >= max_consecutive_dns_errors:
                    msg = f"⚠ Критическое количество DNS ошибок ({consecutive_dns_errors})!"
                    print(colored(f"\n{msg}", Fore.RED))
                    logger.warning(msg)
                    if not check_dns_resolution('www.youtube.com'):
                        logger.warning("DNS недоступен, ожидание восстановления...")
                        if wait_for_dns_recovery('www.youtube.com', check_interval=60, max_wait=600):
                            consecutive_dns_errors = 0
                            pause_time = 30
                        else:
                            logger.error("DNS не восстановлен")
                            return (0, 0, 0, None, consecutive_dns_errors, True)  # fatal=True
                    else:
                        logger.info("DNS доступен, продолжаем")
                        consecutive_dns_errors = 0

                # Пауза если требуется
                if pause_time > 0:
                    msg = f"Пауза {pause_time} секунд..."
                    print(colored(f"  {msg}", Fore.YELLOW))
                    logger.info(f"  {msg}")
                    for remaining in range(pause_time, 0, -60):
                        mins = remaining // 60
                        if mins > 0:
                            print(f"\r  Осталось: {mins} мин... ", end='', flush=True)
                        time.sleep(min(60, remaining))
                    print()

            if attempt >= max_attempts or should_skip:
                if should_skip:
                    msg = "Пропуск URL (необратимая ошибка)"
                    print(colored(f"  {msg}", Fore.YELLOW))
                    logger.info(f"  {msg}")
                    if skip_count == 0:
                        skip_count = 1
                else:
                    msg = f"✗ Провал после {max_attempts} попыток"
                    print(colored(f"  {msg}", Fore.RED))
                    logger.error(f"  {msg}")
                    fail_count = 1

        except KeyboardInterrupt:
            raise  # Пробрасываем наверх

        except Exception as e:
            msg = f"✗ ИСКЛЮЧЕНИЕ: {e}"
            print(f"\n{colored(msg, Fore.RED)}")
            logger.exception(f"  {msg}")
            if attempt >= max_attempts:
                fail_count = 1

    failed_url = url if fail_count > 0 else None
    return (success_count, skip_count, fail_count, failed_url, consecutive_dns_errors, False)  # fatal=False

def download_youtube_videos(links_file='links.txt'):
    """Скачивает YouTube видео с улучшенной обработкой ошибок и проверкой прогресса плейлистов"""
    if not check_ytdlp_installed():
        return False

    script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
    downloads_dir = os.path.join(script_dir, 'downloads')
    links_path = os.path.join(script_dir, links_file)
    log_file = os.path.join(script_dir, 'download.log')
    archive_file = os.path.join(script_dir, 'download_archive.txt')

    # Создаем папку downloads если её нет
    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)
        print(colored(f"✓ Создана папка: {downloads_dir}", Fore.GREEN))

    # Настройка логгера с ротацией (10 МБ, 5 backup копий)
    logger = setup_logger(log_file, max_bytes=10*1024*1024, backup_count=5)

    if not os.path.exists(links_path):
        print(colored(f"✗ Файл {links_file} не найден!", Fore.RED))
        return False

    try:
        active_links = read_links_file(links_path)
    except Exception as e:
        print(colored(f"✗ Ошибка чтения файла: {e}", Fore.RED))
        return False

    if not active_links:
        print(colored("✓ Нет активных ссылок для загрузки", Fore.GREEN))
        return True

    print(colored(f"Найдено ссылок: {len(active_links)}", Fore.CYAN))
    print(colored(f"Папка загрузок: {downloads_dir}", Fore.CYAN))
    print(colored(f"Лог (макс 10 МБ, 5 backup): {log_file}", Fore.CYAN))
    print(colored(f"Архив: {archive_file}", Fore.CYAN))
    print(colored("="*70, Fore.BLUE))

    logger.info(f"{'='*70}")
    logger.info(f"Начало загрузки: {len(active_links)} ссылок")
    logger.info(f"Папка загрузок: {downloads_dir}")
    logger.info(f"{'='*70}")

    total_success = 0
    total_skip = 0
    total_fail = 0
    failed_urls = []
    total_start_time = time.time()
    consecutive_dns_errors = 0

    # Основной цикл по ссылкам
    for idx, url in enumerate(active_links, 1):
        # Для плейлистов проверяем прогресс
        is_playlist = is_playlist_url(url)
        if is_playlist:
            total_vids, downloaded_vids, remaining_vids = get_playlist_info(url, archive_file, logger)
            if remaining_vids > 0:
                print(colored(f"\n📊 ПЛЕЙЛИСТ: всего {total_vids}, скачано {downloaded_vids}, осталось {remaining_vids}", Fore.MAGENTA))
                logger.info(f"  Статистика плейлиста: {total_vids} всего, {downloaded_vids} скачано, {remaining_vids} осталось")
            elif total_vids > 0 and remaining_vids == 0:
                print(colored(f"\n✓ ПЛЕЙЛИСТ УЖЕ ПОЛНОСТЬЮ СКАЧАН ({total_vids} видео)", Fore.GREEN))
                logger.info(f"  Плейлист полностью скачан: {total_vids} видео")
                total_skip += total_vids
                continue

        # Скачиваем URL
        success, skip, fail, failed_url, dns_errors, fatal = download_single_url(
            url, idx, len(active_links), script_dir, downloads_dir, archive_file, logger
        )

        total_success += success
        total_skip += skip
        total_fail += fail
        consecutive_dns_errors = dns_errors

        if failed_url:
            failed_urls.append(failed_url)

        if fatal:
            return False

        # Для плейлистов после скачивания проверяем прогресс снова
        if is_playlist:
            total_vids, downloaded_vids, remaining_vids = get_playlist_info(url, archive_file, logger)
            if remaining_vids > 0:
                print(colored(f"\n⚠ ВНИМАНИЕ: В плейлисте осталось {remaining_vids} не скачанных видео из {total_vids}", Fore.YELLOW))
                logger.warning(f"  Плейлист не завершен: осталось {remaining_vids} видео")
                print(colored(f"  Рекомендуется запустить скрипт снова для завершения загрузки", Fore.YELLOW))
            else:
                print(colored(f"\n✓ Плейлист полностью загружен ({total_vids} видео)", Fore.GREEN))
                logger.info(f"  Плейлист завершен: {total_vids} видео")

        # Пауза между URL
        if idx < len(active_links):
            pause = 10 if success > 0 else 5
            print(colored(f"Пауза {pause} сек...", Fore.CYAN))
            time.sleep(pause)

    # Финальная статистика
    total_duration = time.time() - total_start_time
    stats = [
        "="*70,
        "ЗАВЕРШЕНО!",
        "="*70,
        f"✓ Успешно скачано: {total_success}",
        f"⊘ Пропущено: {total_skip}",
        f"✗ Ошибок: {total_fail}",
        f"Всего обработано: {len(active_links)} ссылок",
        f"Общее время: {format_time(total_duration)}",
    ]
    if len(active_links) > 0:
        stats.append(f"Среднее время: {format_time(total_duration / len(active_links))}/ссылка")
    stats.append("="*70)

    # Вывод в консоль
    print(f"\n{colored('='*70, Fore.BLUE)}")
    print(colored("ЗАВЕРШЕНО!", Fore.GREEN))
    print(colored('='*70, Fore.BLUE))
    print(colored(f"✓ Успешно: {total_success}", Fore.GREEN))
    print(colored(f"⊘ Пропущено: {total_skip}", Fore.CYAN))
    print(colored(f"✗ Ошибок: {total_fail}", Fore.RED))
    print(colored(f"Всего: {len(active_links)} ссылок", Fore.CYAN))
    print(colored(f"Время: {format_time(total_duration)}", Fore.CYAN))
    if len(active_links) > 0:
        print(colored(f"Среднее: {format_time(total_duration / len(active_links))}/ссылка", Fore.CYAN))
    print(colored('='*70, Fore.BLUE))

    # Запись в лог
    logger.info(f"\n{'='*70}")
    for stat in stats[1:-1]:
        logger.info(stat)
    logger.info(f"{'='*70}\n")

    # Сохранение провальных
    if failed_urls:
        failed_file = os.path.join(script_dir, 'failed_links.txt')
        with open(failed_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(failed_urls))
        msg = f"⚠ Провалено ({len(failed_urls)} шт.): failed_links.txt"
        print(f"\n{colored(msg, Fore.YELLOW)}")
        logger.info(f"\n{msg}")

    print(colored(f"\nПапка загрузок: {downloads_dir}", Fore.CYAN))
    print(colored(f"Полный лог: {log_file}", Fore.CYAN))
    print(colored(f"  (авто-ротация при 10 МБ, хранится 5 backup)", Fore.CYAN))

    # Проверяем есть ли плейлисты с не скачанными видео
    incomplete_playlists = []
    for url in active_links:
        if is_playlist_url(url):
            _, _, remaining = get_playlist_info(url, archive_file, None)
            if remaining > 0:
                incomplete_playlists.append((url, remaining))

    if incomplete_playlists:
        print(f"\n{colored('⚠ ВНИМАНИЕ: Обнаружены незавершенные плейлисты:', Fore.YELLOW)}")
        for url, remaining in incomplete_playlists:
            print(colored(f"  • {url} - осталось {remaining} видео", Fore.YELLOW))
        print(colored("  Рекомендуется запустить скрипт снова для продолжения загрузки", Fore.YELLOW))
        return False  # Возвращаем False чтобы автоматически перезапустить

    return True

def main_with_auto_restart():
    """Главная функция с автоматическим перезапуском при критических ошибках"""
    consecutive_failures = 0
    max_consecutive_failures = 3
    restart_count = 0

    print(colored("="*70, Fore.BLUE))
    print(colored("YouTube Downloader с проверкой прогресса плейлистов", Fore.CYAN))
    print(colored("Обложки: JPG | Метаданные: .info.json + .nfo (Plex/Kodi)", Fore.CYAN))
    print(colored("="*70, Fore.BLUE))
    print()

    # Проверка DNS при старте
    if not check_dns_resolution('www.youtube.com'):
        print(colored("⚠ ВНИМАНИЕ: YouTube недоступен!", Fore.YELLOW))
        print(colored("  Проверьте интернет-соединение", Fore.YELLOW))
        print(colored("  Продолжение через 10 секунд...", Fore.YELLOW))
        time.sleep(10)
    else:
        print(colored("✓ YouTube доступен", Fore.GREEN))
    print()

    while True:
        try:
            restart_count += 1
            if restart_count > 1:
                print(f"\n{colored('='*70, Fore.YELLOW)}")
                print(colored(f"АВТОМАТИЧЕСКИЙ ПЕРЕЗАПУСК #{restart_count}", Fore.YELLOW))
                print(colored("Продолжаем загрузку незавершенных плейлистов...", Fore.YELLOW))
                print(colored('='*70, Fore.YELLOW))
                print()

            result = download_youtube_videos()

            if result:
                print(colored("\n✓ Скрипт завершен успешно - все плейлисты полностью загружены", Fore.GREEN))
                break
            else:
                consecutive_failures += 1
                print(colored(f"\n⚠ Обнаружены незавершенные плейлисты (попытка #{consecutive_failures}/{max_consecutive_failures})", Fore.YELLOW))
                if consecutive_failures >= max_consecutive_failures:
                    print(colored("\n✗ Слишком много последовательных ошибок", Fore.RED))
                    print(colored("Проверьте:", Fore.YELLOW))
                    print(colored("  1. Работает ли интернет-соединение", Fore.YELLOW))
                    print(colored("  2. Доступен ли YouTube (проверьте в браузере)", Fore.YELLOW))
                    print(colored("  3. Активен ли VPN/прокси (если требуется)", Fore.YELLOW))
                    print(colored("\nОжидание 5 минут перед продолжением...", Fore.YELLOW))
                    time.sleep(300)
                    consecutive_failures = 0
                else:
                    print(colored("Перезапуск через 60 секунд для продолжения загрузки...", Fore.CYAN))
                    time.sleep(60)

        except KeyboardInterrupt:
            print(colored("\n\n⚠ ПРЕРВАНО ПОЛЬЗОВАТЕЛЕМ", Fore.YELLOW))
            print(colored("Завершение работы...", Fore.CYAN))
            sys.exit(0)

        except Exception as e:
            consecutive_failures += 1
            print(colored(f"\n✗ НЕОЖИДАННОЕ ИСКЛЮЧЕНИЕ: {e}", Fore.RED))
            if consecutive_failures >= max_consecutive_failures:
                print(colored("\n✗ Критическое количество ошибок, остановка", Fore.RED))
                sys.exit(1)
            print(colored(f"Перезапуск через 60 секунд... (#{consecutive_failures})", Fore.YELLOW))
            time.sleep(60)

if __name__ == '__main__':
    main_with_auto_restart()