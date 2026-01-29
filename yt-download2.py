import subprocess
import os
import time
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

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

def setup_logger(log_file, max_bytes=10*1024*1024, backup_count=3):
    """
    Настраивает logger с ротацией файлов
    max_bytes: максимальный размер файла (по умолчанию 10 МБ)
    backup_count: количество резервных копий (download.log.1, download.log.2, ...)
    """
    logger = logging.getLogger('yt_download')
    logger.setLevel(logging.INFO)
    
    # Удаляем существующие handlers если есть
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Rotating file handler с ограничением размера
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    # Формат лога с временной меткой
    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    
    return logger

def check_ytdlp_installed():
    """Проверяет установлен ли yt-dlp и его версию"""
    try:
        result = subprocess.run(['yt-dlp', '--version'],
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(colored(f"✓ yt-dlp версия: {version}", Fore.GREEN))
            
            # Проверяем ffmpeg
            ffmpeg_check = subprocess.run(['ffmpeg', '-version'],
                                        capture_output=True, timeout=5)
            if ffmpeg_check.returncode == 0:
                print(colored("✓ ffmpeg найден", Fore.GREEN))
            else:
                print(colored("⚠ ffmpeg не найден - объединение форматов невозможно", Fore.YELLOW))
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
    """Классифицирует ошибки на категории"""
    error_type = {
        'skip': False,      # Пропустить без повтора
        'retry': False,     # Повторить попытку
        'pause': 0,         # Секунд паузы
        'fatal': False,     # Критическая ошибка
        'message': ''
    }
    
    # Rate limit - КРИТИЧЕСКАЯ для массовой загрузки
    if 'rate-limited' in line_lower or 'rate limit' in line_lower:
        error_type.update({
            'retry': False,
            'pause': 3600,
            'message': 'YouTube rate limit! Пауза 1 час'
        })
        return error_type
    
    # Bot detection
    if 'sign in' in line_lower and 'bot' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 300,
            'message': 'Bot detection! Пауза 5 минут'
        })
        return error_type
    
    # HTTP ошибки
    if 'http error 403' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 60,
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
            'message': 'Возрастные ограничения - проверьте cookies'
        })
    elif 'geo' in line_lower and ('blocked' in line_lower or 'restricted' in line_lower):
        error_type.update({
            'skip': True,
            'message': 'Гео-блокировка'
        })
    elif 'copyright' in line_lower or 'takedown' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Удалено по copyright'
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

def download_youtube_videos(links_file='links.txt'):
    """Скачивает видео с YouTube с улучшенной обработкой ошибок"""
    if not check_ytdlp_installed():
        return
    
    script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
    links_path = os.path.join(script_dir, links_file)
    log_file = os.path.join(script_dir, 'download.log')
    archive_file = os.path.join(script_dir, 'download_archive.txt')
    
    # Настраиваем logger с ротацией (10 МБ, 5 резервных копий)
    logger = setup_logger(log_file, max_bytes=10*1024*1024, backup_count=5)
    
    if not os.path.exists(links_path):
        print(colored(f"✗ Файл {links_file} не найден!", Fore.RED))
        return
    
    try:
        active_links = read_links_file(links_path)
    except Exception as e:
        print(colored(f"✗ Ошибка чтения файла: {e}", Fore.RED))
        return
    
    if not active_links:
        print(colored("✓ Нет активных ссылок для загрузки", Fore.GREEN))
        return
    
    print(colored(f"Найдено ссылок: {len(active_links)}", Fore.CYAN))
    print(colored(f"Лог (max 10 МБ, 5 бэкапов): {log_file}", Fore.CYAN))
    print(colored(f"Архив: {archive_file}", Fore.CYAN))
    print(colored("=" * 70, Fore.BLUE))
    
    logger.info(f"{'='*70}")
    logger.info(f"Начало загрузки: {len(active_links)} видео")
    logger.info(f"{'='*70}")
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    failed_urls = []
    total_start_time = time.time()
    
    for idx, url in enumerate(active_links, 1):
        print(f"\n{colored('='*70, Fore.BLUE)}")
        print(colored(f"[{idx}/{len(active_links)}] {url}", Fore.YELLOW))
        print(colored('='*70, Fore.BLUE))
        
        logger.info(f"\n[{idx}/{len(active_links)}] URL: {url}")
        video_start_time = time.time()
        
        # УЛУЧШЕННАЯ КОМАНДА с дополнительными опциями
        cmd = [
            'yt-dlp',
            '--cookies-from-browser', 'firefox',
            '--remote-components', 'ejs:github',
            
            # Формат и конвертация
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--merge-output-format', 'mp4',
            '--remux-video', 'mp4',
            
            # Повторные попытки
            '--retries', '10',
            '--fragment-retries', '10',
            '--extractor-retries', '5',
            '--file-access-retries', '3',
            
            # Задержки (оптимизированы)
            '--sleep-requests', '3',
            '--sleep-interval', '15',
            '--max-sleep-interval', '45',
            
            # Таймауты
            '--socket-timeout', '30',
            
            # Оптимизация загрузки
            '--concurrent-fragments', '5',
            '--buffer-size', '16K',
            
            # Метаданные и naming
            '--embed-metadata',
            '--embed-thumbnail',
            '--windows-filenames',
            '--output', '%(title).200s [%(id)s].%(ext)s',
            
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
        was_already_downloaded = False
        
        while attempt < max_attempts and not success and not should_skip:
            attempt += 1
            
            if attempt > 1:
                msg = f"ПОВТОРНАЯ ПОПЫТКА {attempt}/{max_attempts}"
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
                error_details = []
                last_line_was_progress = False
                
                # Таймаут на весь процесс - 10 минут на видео
                start_time = time.time()
                timeout_seconds = 600
                
                while True:
                    # Проверяем таймаут
                    if time.time() - start_time > timeout_seconds:
                        process.kill()
                        msg = "ТАЙМАУТ! Процесс завис более 10 минут"
                        print(colored(f"\n⚠ {msg}", Fore.RED))
                        logger.warning(f"  {msg}")
                        break
                    
                    line = process.stdout.readline()
                    
                    if not line and process.poll() is not None:
                        break
                    
                    if line:
                        line = line.rstrip()
                        line_lower = line.lower()
                        
                        # Уже скачано
                        if 'has already been downloaded' in line_lower:
                            was_already_downloaded = True
                            print(colored(line, Fore.CYAN))
                            logger.info(f"  {line}")
                            continue
                        
                        # Собираем ошибки
                        if 'error' in line_lower:
                            error_keywords.append(line)
                            error_details.append(line)
                            # Логируем каждую ошибку сразу
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
                video_duration = time.time() - video_start_time
                
                # Анализ результата
                if return_code == 0:
                    if was_already_downloaded:
                        msg = "⊘ УЖЕ СКАЧАНО"
                        print(f"\n{colored(msg, Fore.CYAN)}")
                        logger.info(f"  {msg}")
                        skip_count += 1
                    else:
                        msg = f"✓ УСПЕШНО за {format_time(video_duration)}"
                        print(f"\n{colored(msg, Fore.GREEN)}")
                        logger.info(f"  {msg}")
                        success_count += 1
                    success = True
                    
                elif return_code == 2:
                    msg = "✗ ОШИБКА В ПАРАМЕТРАХ КОМАНДЫ! (exit code 2)"
                    print(f"\n{colored(msg, Fore.RED)}")
                    logger.error(f"  {msg}")
                    should_skip = True
                    fail_count += 1
                    failed_urls.append(url)
                    
                elif return_code == 101:
                    msg = "⊘ ЗАГРУЗКА ОТМЕНЕНА (exit code 101)"
                    print(f"\n{colored(msg, Fore.CYAN)}")
                    logger.info(f"  {msg}")
                    should_skip = True
                    skip_count += 1
                    
                else:  # return_code == 1 или другие
                    msg = f"✗ ОШИБКА (exit code: {return_code})"
                    print(f"\n{colored(msg, Fore.RED)}")
                    logger.error(f"  {msg}")
                    
                    # Классифицируем ошибки
                    pause_time = 0
                    should_retry = False
                    fatal_error = False
                    
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
                    
                    # Критическая ошибка - останавливаем всё
                    if fatal_error:
                        msg = "✗ КРИТИЧЕСКАЯ ОШИБКА! Остановка скрипта"
                        print(colored(f"\n{msg}", Fore.RED))
                        logger.critical(msg)
                        return
                    
                    # Пауза если требуется
                    if pause_time > 0:
                        msg = f"Пауза {pause_time} секунд..."
                        print(colored(f"  {msg}", Fore.YELLOW))
                        logger.info(f"  {msg}")
                        
                        for remaining in range(pause_time, 0, -60):
                            mins = remaining // 60
                            if mins > 0:
                                print(f"\r  Осталось: {mins} мин...  ", end='', flush=True)
                            time.sleep(min(60, remaining))
                        print()
                    
                    if attempt >= max_attempts or should_skip:
                        if should_skip:
                            msg = "Пропускаем видео (необратимая ошибка)"
                            print(colored(f"  {msg}", Fore.YELLOW))
                            logger.info(f"  {msg}")
                            skip_count += 1
                        else:
                            msg = f"✗ Не удалось после {max_attempts} попыток"
                            print(colored(f"  {msg}", Fore.RED))
                            logger.error(f"  {msg}")
                            fail_count += 1
                            failed_urls.append(url)
                
            except KeyboardInterrupt:
                msg = "⚠ ПРЕРВАНО ПОЛЬЗОВАТЕЛЕМ"
                print(f"\n\n{colored(msg, Fore.YELLOW)}")
                logger.warning(f"\n{msg} на {idx}/{len(active_links)}")
                print(colored(f"Обработано: {idx-1}/{len(active_links)}", Fore.CYAN))
                print(colored(f"✓ Успешно: {success_count}", Fore.GREEN))
                print(colored(f"⊘ Пропущено: {skip_count}", Fore.CYAN))
                print(colored(f"✗ Ошибок: {fail_count}", Fore.RED))
                sys.exit(0)
                
            except Exception as e:
                msg = f"✗ ИСКЛЮЧЕНИЕ: {e}"
                print(f"\n{colored(msg, Fore.RED)}")
                logger.exception(f"  {msg}")  # exception() автоматически добавит traceback
                
                if attempt >= max_attempts:
                    fail_count += 1
                    failed_urls.append(url)
        
        # Пауза между видео (только после успешных/неудачных, не после уже скачанных)
        if idx < len(active_links) and not was_already_downloaded:
            pause = 10 if success else 5
            print(colored(f"Пауза {pause} сек...", Fore.CYAN))
            time.sleep(pause)
    
    # Итоговая статистика
    total_duration = time.time() - total_start_time
    
    stats = [
        "="*70,
        "ЗАВЕРШЕНО!",
        "="*70,
        f"✓ Успешно скачано: {success_count}",
        f"⊘ Пропущено: {skip_count}",
        f"✗ Ошибок: {fail_count}",
        f"Всего обработано: {len(active_links)}",
        f"Общее время: {format_time(total_duration)}",
    ]
    
    if len(active_links) > 0:
        stats.append(f"Среднее время: {format_time(total_duration / len(active_links))}/видео")
    
    stats.append("="*70)
    
    # Вывод в консоль
    print(f"\n{colored('='*70, Fore.BLUE)}")
    print(colored("ЗАВЕРШЕНО!", Fore.GREEN))
    print(colored('='*70, Fore.BLUE))
    print(colored(f"✓ Успешно: {success_count}", Fore.GREEN))
    print(colored(f"⊘ Пропущено: {skip_count}", Fore.CYAN))
    print(colored(f"✗ Ошибок: {fail_count}", Fore.RED))
    print(colored(f"Всего: {len(active_links)}", Fore.CYAN))
    print(colored(f"Время: {format_time(total_duration)}", Fore.CYAN))
    if len(active_links) > 0:
        print(colored(f"Среднее: {format_time(total_duration / len(active_links))}/видео", Fore.CYAN))
    print(colored('='*70, Fore.BLUE))
    
    # Запись в лог
    logger.info(f"\n{'='*70}")
    for stat in stats[1:-1]:  # Без разделителей
        logger.info(stat)
    logger.info(f"{'='*70}\n")
    
    # Сохранение неудавшихся
    if failed_urls:
        failed_file = os.path.join(script_dir, 'failed_links.txt')
        with open(failed_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(failed_urls))
        msg = f"⚠ Неудавшиеся ({len(failed_urls)} шт.): failed_links.txt"
        print(f"\n{colored(msg, Fore.YELLOW)}")
        logger.info(f"\n{msg}")
    
    print(colored(f"\nПолный лог: {log_file}", Fore.CYAN))
    print(colored(f"  (авторотация при достижении 10 МБ, хранится 5 бэкапов)", Fore.CYAN))

if __name__ == '__main__':
    download_youtube_videos()
