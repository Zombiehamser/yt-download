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
# ── Config loading ─────────────────────────────────────────────
_CONFIG: dict | None = None

def load_config(config_path: str | None = None) -> dict:
    """Load config from config.toml. Returns merged dict (config overrides defaults).

    Priority: config.toml values -> hardcoded defaults.
    Returns defaults when config.toml is missing or invalid TOML.
    """
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    defaults = {
        "downloads": {
            "output_dir": "downloads",
            "links_file": "links.txt",
            "archive_file": "download_archive.txt",
            "failed_links_file": "failed_links.txt",
            "log_file": "download.log",
            "max_attempts": 3,
            "generate_nfo": True,
            "save_thumbnails": True,
        },
        "cookies": {
            "mode": "browser",
            "browser": "firefox",
            "cookies_file": "cookies.txt",
        },
        "network": {
            "dns_check": True,
            "dns_recovery_wait": True,
            "dns_recovery_timeout": 600,
            "dns_check_interval": 60,
            "max_consecutive_dns_errors": 20,
            "socket_timeout": 60,
            "timeout_video": 3600,
            "timeout_playlist": 86400,
            "retries": 15,
            "fragment_retries": 15,
            "extractor_retries": 8,
            "file_access_retries": 5,
            "sleep_requests": 5,
            "sleep_interval": 20,
            "max_sleep_interval": 60,
            "concurrent_fragments": 1,
            "buffer_size": "16K",
        },
        "logging": {
            "max_bytes": 10 * 1024 * 1024,
            "backup_count": 5,
            "log_level": "INFO",
        },
        "ui": {
            "color": True,
        },
    }

    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config.toml"
        )

    if not os.path.isfile(config_path):
        _CONFIG = defaults
        return defaults

    try:
        import tomllib  # type: ignore[import-untyped]
        loader = tomllib
    except ImportError:
        try:
            import tomli as loader  # type: ignore[no-redef]
        except ImportError:
            _CONFIG = defaults
            return defaults

    try:
        with open(config_path, "rb") as f:
            user_cfg = loader.load(f)
    except Exception:
        print(f"[config] Warning: invalid TOML in {config_path}, using defaults", file=sys.stderr)
        _CONFIG = defaults
        return defaults

    # Non-destructive merge: user config overrides defaults
    merged = {}
    for section, values in defaults.items():
        if section in user_cfg and isinstance(user_cfg[section], dict):
            merged[section] = {
                **values,
                **{k: v for k, v in user_cfg[section].items() if v is not None},
            }
        else:
            merged[section] = dict(values)

    _CONFIG = merged
    return merged

# ─── DNS: monkey-patch УДАЛЁН ─────────────────────────────────────────────────
# Причина удаления:
#   1. Monkey-patch на socket.getaddrinfo влияет ТОЛЬКО на Python-процесс.
#      yt-dlp запускается через subprocess.Popen — это отдельный процесс,
#      на который Python-патч вообще не распространяется.
#   2. Перенаправление на 8.8.8.8/8.8.4.4 через обычный UDP-53 блокируется
#      провайдером точно так же, как системный DNS-резолвер.
#   3. Правильное решение — настроить DoH/DoT на системном уровне
#      (например, AdGuard Home или dnscrypt-proxy в Docker), тогда
#      yt-dlp автоматически будет использовать защищённый резолвер.
# ─────────────────────────────────────────────────────────────────────────────

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    print("Для цветного вывода: pip install colorama\n")

def colored(text, color_code=''):
def _build_cookie_args(cfg: dict, script_dir: str, logger=None):
    """Build yt-dlp cookie CLI args based on config.

    Returns list of strings to extend into the yt-dlp command.
    """
    mode = cfg["cookies"]["mode"]
    browser = cfg["cookies"]["browser"]
    cookie_file = cfg["cookies"]["cookies_file"]

    if mode == "browser":
        return ["--cookies-from-browser", browser]

    if mode == "file":
        cookies_path = os.path.join(script_dir, cookie_file)
        if os.path.isfile(cookies_path):
            return ["--cookies", str(cookies_path)]
        print(colored(f"  \u26a0 Cookies file not found: {cookie_file}", Fore.YELLOW))
        print(colored(f"    Fallback to browser mode ({browser})", Fore.YELLOW))
        if logger:
            logger.warning(f"Cookies file not found: {cookie_file}, fallback to browser mode ({browser})")
        return ["--cookies-from-browser", browser]

    # mode == "off"
    return []
    """Возвращает цветной текст если colorama доступна"""
    if COLORS_AVAILABLE and color_code:
        return f"{color_code}{text}{Style.RESET_ALL}"
    return text

def setup_logger(log_file, max_bytes=cfg["logging"]["max_bytes"], backup_count=cfg["logging"]["backup_count"]):
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
    Получает информацию о плейлисте: общее количество видео и сколько уже скачано.
    Возвращает: (total_videos, downloaded_videos, remaining_videos)

    timeout=600 сек: для плейлиста из 4000+ видео yt-dlp делает ~87 запросов по 1-3 сек,
    120 с заведомо мало и функция всегда падала с TimeoutExpired.

    --cookies-from-browser firefox: приватные плейлисты (WL = Watch Later)
    без авторизации недоступны, без cookies yt-dlp возвращал пустой список или ошибку.
    """
    try:
        if logger:
            logger.info(f"   Проверка прогресса плейлиста...")

        cookie_args_info = _build_cookie_args(cfg, script_dir, logger)
        _COOKIE_ARGS_INFO = cookie_args_info
        cmd = [
            'yt-dlp',
            '--flat-playlist',
            '--print', 'id',
            *_COOKIE_ARGS,  # cookies: mode={cfg['cookies']['mode']}
            '--no-warnings',
            url
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            if logger:
                logger.warning(f"   Не удалось получить список видео плейлиста")
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
            logger.info(f"   Плейлист: всего {total_videos}, скачано {downloaded_count}, осталось {remaining_count}")

        return (total_videos, downloaded_count, remaining_count)

    except subprocess.TimeoutExpired:
        if logger:
            logger.warning(f"   Таймаут при проверке плейлиста (>600с) — список слишком большой или соединение медленное")
        return (0, 0, 0)
    except Exception as e:
        if logger:
            logger.error(f"   Ошибка проверки плейлиста: {e}")
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
            logger.info(f"   Создан .nfo файл: {os.path.basename(nfo_path)}")
        return True

    except Exception as e:
        if logger:
            logger.error(f"   Ошибка создания .nfo: {e}")
        return False

def check_dns_resolution(host='www.youtube.com', timeout=10):
    """
    Проверяет доступность хоста через системный резолвер.
    Использует системный DNS (настроенный на уровне ОС/DoH-клиента).
    Возвращает True если DNS работает, False в противном случае.
    """
    try:
        socket.setdefaulttimeout(timeout)
        result = socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        return len(result) > 0
    except (socket.gaierror, socket.timeout, OSError):
        return False
    except Exception:
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

    # Rate limit (включая новую формулировку с data sync id / po token)
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

    # PO Token / Data Sync ID (предупреждение, не ошибка — не прерываем)
    if 'po token' in line_lower or 'data sync id' in line_lower:
        error_type.update({
            'retry': False,
            'pause': 0,
            'message': 'Предупреждение PO Token/Data Sync ID (некритично)'
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

    is_playlist = is_playlist_url(url)
    if is_playlist:
        print(colored("📋 Обнаружен ПЛЕЙЛИСТ", Fore.CYAN))
        logger.info("   Тип: ПЛЕЙЛИСТ")

    url_start_time = time.time()

    if is_playlist:
        output_template = os.path.join(
            downloads_dir,
            '%(playlist_title,uploader,channel).100s',
            '%(title).200s [%(id)s].%(ext)s'
        )
    else:
        output_template = os.path.join(
            downloads_dir,
            '%(title).200s [%(id)s].%(ext)s'
        )

    # КОМАНДА yt-dlp
    cookie_args = _build_cookie_args(cfg, script_dir, logger)
    _COOKIE_ARGS = cookie_args
    cmd = [
        'yt-dlp',
        *_COOKIE_ARGS,  # cookies: mode={cfg['cookies']['mode']}
        '--remote-components', 'ejs:github',
        # Формат и конвертация
        '-f', 'bestvideo+bestaudio/best',
        '--merge-output-format', 'mp4',
        '--remux-video', 'mp4',
        # Попытки повтора
        '--retries', str(cfg["network"]["retries"]),
        '--fragment-retries', str(cfg["network"]["fragment_retries"]),
        '--extractor-retries', str(cfg["network"]["extractor_retries"]),
        '--file-access-retries', str(cfg["network"]["file_access_retries"]),
        # Задержки
        '--sleep-requests', str(cfg["network"]["sleep_requests"]),
        '--sleep-interval', str(cfg["network"]["sleep_interval"]),
        '--max-sleep-interval', str(cfg["network"]["max_sleep_interval"]),
        # Таймауты
        '--socket-timeout', str(cfg["network"]["socket_timeout"]),
        # Оптимизация загрузки
        '--concurrent-fragments', str(cfg["network"]["concurrent_fragments"]),
        '--buffer-size', cfg["network"]["buffer_size"],
        # Метаданные и обложки
        '--embed-metadata',
        '--embed-thumbnail',
        '--write-thumbnail',
        '--convert-thumbnails', 'jpg',
        '--write-info-json',
        # Именование файлов
        '--windows-filenames',
        '--output', output_template,
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
        # Случайный порядок видео в плейлисте
        '--playlist-random',
        url
    ]

    cfg = load_config()
    max_attempts = cfg["downloads"]["max_attempts"]
    attempt = 0
    success = False
    should_skip = False
    consecutive_dns_errors = 0
    max_consecutive_dns_errors = cfg["network"]["max_consecutive_dns_errors"]
    success_count = 0
    skip_count = 0
    fail_count = 0

    while attempt < max_attempts and not success and not should_skip:
        attempt += 1
        if attempt > 1:
            msg = f"ПОПЫТКА ПОВТОРА {attempt}/{max_attempts}"
            print(f"\n{colored(f'⚠ {msg}', Fore.YELLOW)}")
            logger.info(f"   {msg}")
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

            # Таймаут для плейлиста 24 ч, для одного видео 1 ч.
            # WL из 4360 видео при --sleep-interval 20 занимает ~87200 сек только на паузах.
            start_time = time.time()
            timeout_seconds = cfg["network"]["timeout_playlist"] if is_playlist else cfg["network"]["timeout_video"]

            while True:
                if time.time() - start_time > timeout_seconds:
                    process.kill()
                    timeout_hours = timeout_seconds // 3600
                    msg = f"ТАЙМАУТ! Процесс работал более {timeout_hours} часов"
                    print(colored(f"\n⚠ {msg}", Fore.RED))
                    logger.warning(f"   {msg}")
                    break

                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    line = line.rstrip()
                    line_lower = line.lower()

                    if '[download] downloading item' in line_lower:
                        match = re.search(r'downloading item (\d+) of (\d+)', line_lower)
                        if match:
                            current = int(match.group(1))
                            total_in_playlist = int(match.group(2))
                            print(colored(f"📊 Прогресс плейлиста: {current}/{total_in_playlist}", Fore.MAGENTA))

                    if 'has already been downloaded' in line_lower or 'has already been recorded in the archive' in line_lower:
                        videos_already_in_archive += 1
                        print(colored(line, Fore.CYAN))
                        logger.info(f"   {line}")
                        continue

                    if '[download] 100%' in line or 'has already been downloaded' in line_lower:
                        if 'has already been downloaded' not in line_lower:
                            videos_downloaded += 1

                    if 'error' in line_lower or 'warning' in line_lower:
                        error_keywords.append(line)

                        if 'failed to resolve' in line_lower or 'getaddrinfo failed' in line_lower:
                            dns_errors_in_attempt += 1
                            consecutive_dns_errors += 1
                            logger.error(f"   DNS ERROR #{consecutive_dns_errors}: {line}")
                        else:
                            logger.error(f"   ERROR: {line}")

                    if '[download]' in line and '%' in line:
                        sys.stdout.write('\r' + ' ' * 100 + '\r')
                        sys.stdout.write(colored(line, Fore.GREEN))
                        sys.stdout.flush()
                        last_line_was_progress = True
                    else:
                        if last_line_was_progress:
                            print()
                        last_line_was_progress = False

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

            if return_code == 0:
                if videos_already_in_archive > 0 and videos_downloaded == 0:
                    msg = f"⊘ ВСЕ УЖЕ СКАЧАНО ({videos_already_in_archive} видео в архиве)"
                    print(f"\n{colored(msg, Fore.CYAN)}")
                    logger.info(f"   {msg}")
                    skip_count = videos_already_in_archive
                else:
                    msg = f"✓ УСПЕХ за {format_time(url_duration)}"
                    if videos_downloaded > 0:
                        msg += f" (скачано: {videos_downloaded} видео)"
                    print(f"\n{colored(msg, Fore.GREEN)}")
                    logger.info(f"   {msg}")
                    success_count = max(1, videos_downloaded)
                    skip_count = videos_already_in_archive
                consecutive_dns_errors = 0
                success = True

            elif return_code == 2:
                msg = "✗ ОШИБКА ПАРАМЕТРОВ КОМАНДЫ! (exit code 2)"
                print(f"\n{colored(msg, Fore.RED)}")
                logger.error(f"   {msg}")
                should_skip = True
                fail_count = 1

            elif return_code == 101:
                msg = "⊘ ЗАГРУЗКА ОТМЕНЕНА (exit code 101)"
                print(f"\n{colored(msg, Fore.CYAN)}")
                logger.info(f"   {msg}")
                should_skip = True
                skip_count = 1

            else:
                msg = f"✗ ОШИБКА (exit code: {return_code})"
                print(f"\n{colored(msg, Fore.RED)}")
                logger.error(f"   {msg}")

            # Классификация ошибок
            pause_time = 0
            should_retry = False
            fatal_error = False
            has_dns_error = False

            for error in error_keywords:
                error_class = classify_error(error.lower(), error_keywords)
                if error_class['message']:
                    print(colored(f"   ⚠ {error_class['message']}", Fore.YELLOW))
                    logger.warning(f"   {error_class['message']}")
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

            if fatal_error:
                msg = "✗ ФАТАЛЬНАЯ ОШИБКА! Остановка скрипта"
                print(colored(f"\n{msg}", Fore.RED))
                logger.critical(msg)
                return (0, 0, 0, None, consecutive_dns_errors, True)

            if has_dns_error and consecutive_dns_errors >= max_consecutive_dns_errors:
                msg = f"⚠ Критическое количество DNS ошибок ({consecutive_dns_errors})!"
                print(colored(f"\n{msg}", Fore.RED))
                logger.warning(msg)
                if not check_dns_resolution('www.youtube.com'):
                    logger.warning("DNS недоступен, ожидание восстановления...")
                    if wait_for_dns_recovery('www.youtube.com', check_interval=cfg["network"]["dns_check_interval"], max_wait=cfg["network"]["dns_recovery_timeout"]):
                        consecutive_dns_errors = 0
                        pause_time = 30
                    else:
                        logger.error("DNS не восстановлен")
                        return (0, 0, 0, None, consecutive_dns_errors, True)
                else:
                    logger.info("DNS доступен, продолжаем")
                    consecutive_dns_errors = 0

            if pause_time > 0:
                msg = f"Пауза {pause_time} секунд..."
                print(colored(f"   {msg}", Fore.YELLOW))
                logger.info(f"   {msg}")
                for remaining in range(pause_time, 0, -60):
                    mins = remaining // 60
                    if mins > 0:
                        print(f"\r   Осталось: {mins} мин... ", end='', flush=True)
                    time.sleep(min(60, remaining))
                print()

            if attempt >= max_attempts or should_skip:
                if should_skip:
                    msg = "Пропуск URL (необратимая ошибка)"
                    print(colored(f"   {msg}", Fore.YELLOW))
                    logger.info(f"   {msg}")
                    if skip_count == 0:
                        skip_count = 1
                else:
                    msg = f"✗ Провал после {max_attempts} попыток"
                    print(colored(f"   {msg}", Fore.RED))
                    logger.error(f"   {msg}")
                    fail_count = 1

        except KeyboardInterrupt:
            raise

        except Exception as e:
            msg = f"✗ ИСКЛЮЧЕНИЕ: {e}"
            print(f"\n{colored(msg, Fore.RED)}")
            logger.exception(f"   {msg}")
            if attempt >= max_attempts:
                fail_count = 1

    failed_url = url if fail_count > 0 else None
    return (success_count, skip_count, fail_count, failed_url, consecutive_dns_errors, False)

def download_youtube_videos(links_file=None):
    """Скачивает YouTube видео с улучшенной обработкой ошибок и проверкой прогресса плейлистов"""
    if not check_ytdlp_installed():
    cfg = load_config()
        return False

    script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
    downloads_dir = os.path.join(script_dir, cfg["downloads"]["output_dir"])
    links_path = os.path.join(script_dir, links_file or cfg["downloads"]["links_file"])
    log_file = os.path.join(script_dir, cfg["downloads"]["log_file"])
    archive_file = os.path.join(script_dir, cfg["downloads"]["archive_file"])

    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)
        print(colored(f"✓ Создана папка: {downloads_dir}", Fore.GREEN))

    logger = setup_logger(log_file, max_bytes=cfg["logging"]["max_bytes"], backup_count=cfg["logging"]["backup_count"])

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

    for idx, url in enumerate(active_links, 1):
        is_playlist = is_playlist_url(url)

        if is_playlist:
            total_vids, downloaded_vids, remaining_vids = get_playlist_info(url, archive_file, logger)

            # При (0,0,0) — не удалось получить статистику (таймаут/ошибка сети),
            # не считаем плейлист пустым, продолжаем загрузку — yt-dlp сам разберётся по архиву.
            if total_vids == 0 and downloaded_vids == 0 and remaining_vids == 0:
                print(colored(f"\n⚠ Не удалось получить статистику плейлиста (таймаут или ошибка сети)", Fore.YELLOW))
                print(colored(f"   Продолжаем загрузку — yt-dlp использует архив самостоятельно", Fore.YELLOW))
                logger.warning(f"   Статистика плейлиста недоступна, загрузка продолжается")
            elif remaining_vids > 0:
                print(colored(f"\n📊 ПЛЕЙЛИСТ: всего {total_vids}, скачано {downloaded_vids}, осталось {remaining_vids}", Fore.MAGENTA))
                logger.info(f"   Статистика плейлиста: {total_vids} всего, {downloaded_vids} скачано, {remaining_vids} осталось")
            elif total_vids > 0 and remaining_vids == 0:
                print(colored(f"\n✓ ПЛЕЙЛИСТ УЖЕ ПОЛНОСТЬЮ СКАЧАН ({total_vids} видео)", Fore.GREEN))
                logger.info(f"   Плейлист полностью скачан: {total_vids} видео")
                total_skip += total_vids
                continue

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

        # После загрузки плейлиста — повторная проверка прогресса
        if is_playlist:
            total_vids, downloaded_vids, remaining_vids = get_playlist_info(url, archive_file, logger)
            if total_vids == 0:
                logger.warning(f"   Финальная статистика плейлиста недоступна")
            elif remaining_vids > 0:
                print(colored(f"\n⚠ ВНИМАНИЕ: В плейлисте осталось {remaining_vids} не скачанных видео из {total_vids}", Fore.YELLOW))
                logger.warning(f"   Плейлист не завершен: осталось {remaining_vids} видео")
                print(colored(f"   Рекомендуется запустить скрипт снова для завершения загрузки", Fore.YELLOW))
            else:
                print(colored(f"\n✓ Плейлист полностью загружен ({total_vids} видео)", Fore.GREEN))
                logger.info(f"   Плейлист завершен: {total_vids} видео")

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

    logger.info(f"\n{'='*70}")
    for stat in stats[1:-1]:
        logger.info(stat)
    logger.info(f"{'='*70}\n")

    if failed_urls:
        failed_file = os.path.join(script_dir, cfg["downloads"]["failed_links_file"])
        with open(failed_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(failed_urls))
        msg = f"⚠ Провалено ({len(failed_urls)} шт.): failed_links.txt"
        print(f"\n{colored(msg, Fore.YELLOW)}")
        logger.info(f"\n{msg}")

    print(colored(f"\nПапка загрузок: {downloads_dir}", Fore.CYAN))
    print(colored(f"Полный лог: {log_file}", Fore.CYAN))
    print(colored(f"   (авто-ротация при 10 МБ, хранится 5 backup)", Fore.CYAN))

    # Финальная проверка незавершённых плейлистов
    incomplete_playlists = []
    for url in active_links:
        if is_playlist_url(url):
            total_vids, _, remaining = get_playlist_info(url, archive_file, None)
            if total_vids > 0 and remaining > 0:
                incomplete_playlists.append((url, remaining))

    if incomplete_playlists:
        print(f"\n{colored('⚠ ВНИМАНИЕ: Обнаружены незавершенные плейлисты:', Fore.YELLOW)}")
        for url, remaining in incomplete_playlists:
            print(colored(f"   • {url} - осталось {remaining} видео", Fore.YELLOW))
        print(colored("   Рекомендуется запустить скрипт снова для продолжения загрузки", Fore.YELLOW))
        return False

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

    if not check_dns_resolution('www.youtube.com'):
        print(colored("⚠ ВНИМАНИЕ: YouTube недоступен!", Fore.YELLOW))
        print(colored("   Проверьте интернет-соединение", Fore.YELLOW))
        print(colored("   Продолжение через 10 секунд...", Fore.YELLOW))
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
                    print(colored("   1. Работает ли интернет-соединение", Fore.YELLOW))
                    print(colored("   2. Доступен ли YouTube (проверьте в браузере)", Fore.YELLOW))
                    print(colored("   3. Активен ли VPN/прокси (если требуется)", Fore.YELLOW))
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

def setup_check():
    """Check all dependencies and offer to install missing ones."""
    cfg = load_config()
    print(colored("=" * 70, Fore.BLUE))
    print(colored("  ПРОВЕРКА ЗАВИСИМОСТЕЙ", Fore.CYAN))
    print(colored("=" * 70, Fore.BLUE))
    print()

    all_ok = True

    # 1. Python version
    print(colored("  [1/5] Версия Python...", Fore.CYAN), end=" ", flush=True)
    if sys.version_info >= (3, 8):
        print(colored(f"\u2705 {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", Fore.GREEN))
    else:
        print(colored(f"\u274c {sys.version_info.major}.{sys.version_info.minor} (требуется 3.8+)", Fore.RED))
        all_ok = False

    # 2. yt-dlp
    print(colored("  [2/5] yt-dlp...", Fore.CYAN), end=" ", flush=True)
    ytdlp_ok = False
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(colored(f"\u2705 {result.stdout.strip()}", Fore.GREEN))
            ytdlp_ok = True
        else:
            print(colored(f"\u274c not found", Fore.RED))
    except FileNotFoundError:
        print(colored(f"\u274c not found", Fore.RED))
    if not ytdlp_ok:
        all_ok = False
        ans = input("    \u2795 Install yt-dlp? (y/n): ").strip().lower()
        if ans == 'y':
            _install_package('yt-dlp')

    # 3. ffmpeg
    print(colored("  [3/5] ffmpeg...", Fore.CYAN), end=" ", flush=True)
    ffmpeg_ok = False
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.decode().split('\n')[0] if isinstance(result.stdout, bytes) else result.stdout.split('\n')[0]
            print(colored(f"\u2705 ffmpeg found", Fore.GREEN))
            ffmpeg_ok = True
        else:
            print(colored(f"\u274c not found", Fore.RED))
    except FileNotFoundError:
        print(colored(f"\u274c not found", Fore.RED))
    if not ffmpeg_ok:
        all_ok = False
        print(colored("    \u2139 Install ffmpeg: winget install ffmpeg", Fore.YELLOW))

    # 4. colorama
    print(colored("  [4/5] colorama...", Fore.CYAN), end=" ", flush=True)
    try:
        import importlib.util
        spec = importlib.util.find_spec("colorama")
        if spec is not None:
            print(colored(f"\u2705 installed", Fore.GREEN))
        else:
            print(colored(f"\u274c not installed", Fore.RED))
            all_ok = False
            ans = input("    \u2795 Install colorama? (y/n): ").strip().lower()
            if ans == 'y':
                _install_package('colorama')
    except ImportError:
        print(colored(f"\u274c not installed", Fore.RED))
        all_ok = False

    # 5. Cookies (if mode=file)
    print(colored("  [5/5] Cookies file...", Fore.CYAN), end=" ", flush=True)
    cookie_mode = cfg["cookies"]["mode"]
    if cookie_mode == "file":
        cookie_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), cfg["cookies"]["cookies_file"]
        )
        if os.path.isfile(cookie_path):
            print(colored(f"\u2705 {cfg['cookies']['cookies_file']} exists", Fore.GREEN))
        else:
            print(colored(f"\u274c {cfg['cookies']['cookies_file']} not found (mode=file)", Fore.RED))
            print(colored(f"    \u2139 Export cookies from browser or set mode=browser in config", Fore.YELLOW))
            all_ok = False
    else:
        print(colored("\u2705 not required (mode={})".format(cookie_mode), Fore.GREEN))

    print()
    if all_ok:
        print(colored("\u2705 All dependencies satisfied!", Fore.GREEN))
    else:
        print(colored("\u26a0 Some dependencies are missing (see above)", Fore.YELLOW))
    print(colored("=" * 70, Fore.BLUE))


def _install_package(package_name):
    """Try to install a package via uv, fallback to pip."""
    try:
        subprocess.run(['uv', 'pip', 'install', package_name], check=True, timeout=60)
        print(colored(f"    \u2705 {package_name} installed via uv", Fore.GREEN))
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', package_name], check=True, timeout=60)
            print(colored(f"    \u2705 {package_name} installed via pip", Fore.GREEN))
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(colored(f"    \u274c Failed to install {package_name}: {e}", Fore.RED))


def run_cleanup():
    """Запустить очистку мусора (NFO/превью без видео) через subprocess."""
    cfg = load_config()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cleaner_path = os.path.join(script_dir, "yt_media_cleaner_ru.py")

    if not os.path.isfile(cleaner_path):
        print(colored(f"  \u26a0 Cleaner не найден: yt_media_cleaner_ru.py", Fore.YELLOW))
        print(colored(f"    Скачайте скрипт из репозитория или поместите рядом с yt_download_ru.py", Fore.YELLOW))
        return

    media_root = cfg.get("cleanup", {}).get("media_root", "downloads")
    print()
    print(colored("=" * 70, Fore.BLUE))
    print(colored("  ОЧИСТКА МУСОРА (NFO/превью без видео)", Fore.CYAN))
    print(colored("=" * 70, Fore.BLUE))
    print(colored(f"  Скрипт: {cleaner_path}", Fore.CYAN))
    print(colored(f"  Директория: {media_root}", Fore.CYAN))
    print(colored(f"  Удаление: .nfo, .jpg, .jpeg, .webp, .png без парного .mp4", Fore.CYAN))
    print()
    print(colored("  Будет запущен интерактивный cleaner.", Fore.YELLOW))
    print(colored("  В cleaner выберите режим 2 (очистка orphan) или 3 (оба режима).", Fore.YELLOW))
    ans = input(colored("  Продолжить? (y/n): ", Fore.YELLOW)).strip().lower()
    if ans != "y":
        print(colored("  Очистка отменена.", Fore.YELLOW))
        return

    print(colored("\n  Запуск cleaner...\n", Fore.CYAN))
    try:
        subprocess.run([sys.executable, cleaner_path], timeout=300)
    except subprocess.TimeoutExpired:
        print(colored("  \u26a0 Cleaner превысил таймаут (300 с)", Fore.YELLOW))
    except Exception as e:
        print(colored(f"  \u274c Ошибка запуска cleaner: {e}", Fore.RED))

    print(colored("\n  Cleaner завершён.", Fore.GREEN))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Downloader")
    parser.add_argument('--check', '-c', action='store_true', help='Check dependencies and exit')
    parser.add_argument('--cleanup', '-C', action='store_true', help='Run orphan metadata cleaner and exit')
    args = parser.parse_args()
    if args.check:
        setup_check()
        sys.exit(0)
    if args.cleanup:
        run_cleanup()
        sys.exit(0)
    main_with_auto_restart()
