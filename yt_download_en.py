#!/usr/bin/env python3
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

# ─── DNS: monkey-patch REMOVED ─────────────────────────────────────────────────
# Reason for removal:
#   1. Monkey-patching socket.getaddrinfo only affects the Python process.
#      yt-dlp runs as a subprocess via Popen — the Python patch never
#      applies to it.
#   2. Redirecting to 8.8.8.8/8.8.4.4 via plain UDP-53 gets blocked by
#      the ISP just like the system DNS resolver.
#   3. The correct approach is to configure DoH/DoT at the system level
#      (e.g., AdGuard Home or dnscrypt-proxy in Docker), so yt-dlp
#      automatically uses the encrypted resolver.
# ─────────────────────────────────────────────────────────────────────────────

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    print("For colored output install: pip install colorama\n")

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
    """Returns colored text if colorama is available"""
    if COLORS_AVAILABLE and color_code:
        return f"{color_code}{text}{Style.RESET_ALL}"
    return text

def setup_logger(log_file, max_bytes=cfg["logging"]["max_bytes"], backup_count=cfg["logging"]["backup_count"]):
    """
    Sets up a logger with file rotation
    max_bytes: maximum file size (default 10 MB)
    backup_count: number of backup copies (download.log.1, download.log.2, ...)
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
    """Checks whether the URL is a playlist"""
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
    Retrieves playlist info: total video count and how many are already downloaded.
    Returns: (total_videos, downloaded_videos, remaining_videos)

    timeout=600 sec: for a playlist with 4000+ videos, yt-dlp makes ~87 requests
    at 1-3 sec each; 120 sec was always too short and caused TimeoutExpired.

    --cookies-from-browser firefox: private playlists (WL = Watch Later)
    require authentication; without cookies yt-dlp returned an empty list or error.
    """
    try:
        if logger:
            logger.info(f"  Checking playlist progress...")

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
                logger.warning(f"  Failed to retrieve playlist video list")
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
            logger.info(f"  Playlist: total {total_videos}, downloaded {downloaded_count}, remaining {remaining_count}")

        return (total_videos, downloaded_count, remaining_count)

    except subprocess.TimeoutExpired:
        if logger:
            logger.warning(f"  Timeout while checking playlist (>600s) — list is too large or connection is slow")
        return (0, 0, 0)
    except Exception as e:
        if logger:
            logger.error(f"  Error checking playlist: {e}")
        return (0, 0, 0)

def generate_nfo_file(info_json_path, logger=None):
    """
    Generates a .nfo file from .info.json for Kodi/Plex
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
            logger.info(f"  Created .nfo file: {os.path.basename(nfo_path)}")
        return True

    except Exception as e:
        if logger:
            logger.error(f"  Error creating .nfo: {e}")
        return False

def check_dns_resolution(host='www.youtube.com', timeout=10):
    """
    Checks host availability via the system resolver.
    Uses the system DNS (configured at the OS/DoH client level).
    Returns True if DNS works, False otherwise.
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
    Waits for DNS resolution to recover
    check_interval: check interval in seconds
    max_wait: maximum wait time in seconds
    """
    print(colored(f"\n⚠ DNS unavailable for {host}", Fore.YELLOW))
    print(colored(f"Waiting for recovery (checking every {check_interval}s)...", Fore.YELLOW))
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(check_interval)
        elapsed += check_interval
        if check_dns_resolution(host):
            print(colored(f"✓ DNS recovered after {elapsed}s", Fore.GREEN))
            return True
        mins_left = (max_wait - elapsed) // 60
        print(f"\r⏳ Elapsed {elapsed}s, ~{mins_left}m remaining... ", end='', flush=True)
    print(colored(f"\n✗ DNS not recovered within {max_wait}s", Fore.RED))
    return False

def check_ytdlp_installed():
    """Checks whether yt-dlp is installed and returns its version"""
    try:
        result = subprocess.run(['yt-dlp', '--version'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(colored(f"✓ yt-dlp version: {version}", Fore.GREEN))

            ffmpeg_check = subprocess.run(['ffmpeg', '-version'],
                                          capture_output=True, timeout=5)
            if ffmpeg_check.returncode == 0:
                print(colored("✓ ffmpeg found", Fore.GREEN))
            else:
                print(colored("⚠ ffmpeg not found - format merging unavailable", Fore.YELLOW))
            print()
            return True
    except FileNotFoundError:
        print(colored("✗ yt-dlp not found! Install with: pip install -U yt-dlp", Fore.RED))
        return False
    except Exception as e:
        print(colored(f"✗ Check error: {e}", Fore.RED))
        return False

def format_time(seconds):
    """Formats seconds into a human-readable string"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def read_links_file(links_path):
    """Reads the links file"""
    with open(links_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    links = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and stripped.startswith('http'):
            links.append(stripped)
    return links

def classify_error(line_lower, error_keywords):
    """Classifies errors by category"""
    error_type = {
        'skip': False,
        'retry': False,
        'pause': 0,
        'fatal': False,
        'dns_error': False,
        'message': ''
    }

    # DNS errors
    if 'failed to resolve' in line_lower or 'getaddrinfo failed' in line_lower:
        error_type.update({
            'dns_error': True,
            'retry': True,
            'pause': 30,
            'message': 'DNS error - check your internet connection'
        })
        return error_type

    # Rate limit (including new phrasing with data sync id / po token)
    if 'rate-limited' in line_lower or 'rate limit' in line_lower:
        error_type.update({
            'retry': False,
            'pause': 3600,
            'message': 'YouTube rate limit! Pausing for 1 hour'
        })
        return error_type

    # Bot detection
    if 'sign in' in line_lower and 'bot' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 300,
            'message': 'Bot detected! Pausing for 5 minutes'
        })
        return error_type

    # PO Token / Data Sync ID (warning, not an error — do not interrupt)
    if 'po token' in line_lower or 'data sync id' in line_lower:
        error_type.update({
            'retry': False,
            'pause': 0,
            'message': 'PO Token / Data Sync ID warning (non-critical)'
        })
        return error_type

    # HTTP errors
    if 'http error 403' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 600,
            'message': 'HTTP 403: Cookie/access issue'
        })
    elif 'http error 429' in line_lower:
        error_type.update({
            'retry': False,
            'pause': 1800,
            'message': 'HTTP 429: Too many requests'
        })
    elif 'http error 400' in line_lower:
        error_type.update({
            'retry': True,
            'message': 'HTTP 400: Possibly outdated yt-dlp version'
        })
    elif 'http error 404' in line_lower or 'http error 410' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Video has been deleted'
        })

    # Content unavailability
    if 'private video' in line_lower or 'members-only' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Private video or members-only'
        })
    elif 'video unavailable' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Video unavailable'
        })
    elif 'premieres in' in line_lower or 'will begin in' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Scheduled premiere - not yet available'
        })
    elif 'age-restricted' in line_lower or 'age restricted' in line_lower:
        error_type.update({
            'retry': True,
            'message': 'Age-restricted - check your cookies'
        })
    elif 'geo' in line_lower and ('blocked' in line_lower or 'restricted' in line_lower):
        error_type.update({
            'skip': True,
            'message': 'Geo-blocked'
        })
    elif 'copyright' in line_lower or 'takedown' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Removed due to copyright'
        })
    elif 'requires payment' in line_lower or 'rental' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Payment required'
        })

    # System errors
    if 'timeout' in line_lower or 'timed out' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 30,
            'message': 'Connection timeout'
        })
    elif 'connection' in line_lower and 'error' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 60,
            'message': 'Connection error'
        })
    elif 'no space left' in line_lower or 'disk full' in line_lower:
        error_type.update({
            'fatal': True,
            'message': 'Disk full!'
        })
    elif 'permission denied' in line_lower or 'access denied' in line_lower:
        error_type.update({
            'fatal': True,
            'message': 'No permission to access file/directory'
        })
    elif ('ffmpeg' in line_lower or 'ffprobe' in line_lower) and 'not found' in line_lower:
        error_type.update({
            'fatal': True,
            'message': 'ffmpeg not found - cannot merge formats'
        })

    return error_type

def download_single_url(url, idx, total, script_dir, downloads_dir, archive_file, logger):
    """
    Downloads video(s) for a single URL (can be a single video or a playlist)
    Returns (success_count, skip_count, fail_count, failed_url_or_none, consecutive_dns_errors, fatal)
    """
    print(f"\n{colored('='*70, Fore.BLUE)}")
    print(colored(f"[{idx}/{total}] {url}", Fore.YELLOW))
    print(colored('='*70, Fore.BLUE))
    logger.info(f"\n[{idx}/{total}] URL: {url}")

    is_playlist = is_playlist_url(url)
    if is_playlist:
        print(colored("📋 PLAYLIST detected", Fore.CYAN))
        logger.info("   Type: PLAYLIST")

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

    # yt-dlp COMMAND
    cookie_args = _build_cookie_args(cfg, script_dir, logger)
    _COOKIE_ARGS = cookie_args
    cmd = [
        'yt-dlp',
        *_COOKIE_ARGS,  # cookies: mode={cfg['cookies']['mode']}
        '--remote-components', 'ejs:github',
        # Format and conversion
        '-f', 'bestvideo+bestaudio/best',
        '--merge-output-format', 'mp4',
        '--remux-video', 'mp4',
        # Retry attempts
        '--retries', str(cfg["network"]["retries"]),
        '--fragment-retries', str(cfg["network"]["fragment_retries"]),
        '--extractor-retries', str(cfg["network"]["extractor_retries"]),
        '--file-access-retries', str(cfg["network"]["file_access_retries"]),
        # Delays
        '--sleep-requests', str(cfg["network"]["sleep_requests"]),
        '--sleep-interval', str(cfg["network"]["sleep_interval"]),
        '--max-sleep-interval', str(cfg["network"]["max_sleep_interval"]),
        # Timeouts
        '--socket-timeout', str(cfg["network"]["socket_timeout"]),
        # Download optimization
        '--concurrent-fragments', str(cfg["network"]["concurrent_fragments"]),
        '--buffer-size', cfg["network"]["buffer_size"],
        # Metadata and thumbnails
        '--embed-metadata',
        '--embed-thumbnail',
        '--write-thumbnail',
        '--convert-thumbnails', 'jpg',
        '--write-info-json',
        # File naming
        '--windows-filenames',
        '--output', output_template,
        # Error handling
        '--no-check-certificate',
        '--no-overwrites',
        '--download-archive', archive_file,
        '--ignore-errors',
        '--no-abort-on-error',
        # Progress
        '--newline',
        '--progress',
        '--console-title',
        # Random playlist order
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
            msg = f"RETRY ATTEMPT {attempt}/{max_attempts}"
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

            # Playlist timeout: 24h, single video timeout: 1h.
            # WL with 4360 videos at --sleep-interval 20 takes ~87200 sec just on pauses.
            start_time = time.time()
            timeout_seconds = cfg["network"]["timeout_playlist"] if is_playlist else cfg["network"]["timeout_video"]

            while True:
                if time.time() - start_time > timeout_seconds:
                    process.kill()
                    timeout_hours = timeout_seconds // 3600
                    msg = f"TIMEOUT! Process has been running for more than {timeout_hours} hours"
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
                            print(colored(f"📊 Playlist progress: {current}/{total_in_playlist}", Fore.MAGENTA))

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
                    msg = f"⊘ ALL ALREADY DOWNLOADED ({videos_already_in_archive} videos in archive)"
                    print(f"\n{colored(msg, Fore.CYAN)}")
                    logger.info(f"   {msg}")
                    skip_count = videos_already_in_archive
                else:
                    msg = f"✓ SUCCESS in {format_time(url_duration)}"
                    if videos_downloaded > 0:
                        msg += f" (downloaded: {videos_downloaded} videos)"
                    print(f"\n{colored(msg, Fore.GREEN)}")
                    logger.info(f"   {msg}")
                    success_count = max(1, videos_downloaded)
                    skip_count = videos_already_in_archive
                consecutive_dns_errors = 0
                success = True

            elif return_code == 2:
                msg = "✗ COMMAND PARAMETER ERROR! (exit code 2)"
                print(f"\n{colored(msg, Fore.RED)}")
                logger.error(f"   {msg}")
                should_skip = True
                fail_count = 1

            elif return_code == 101:
                msg = "⊘ DOWNLOAD CANCELLED (exit code 101)"
                print(f"\n{colored(msg, Fore.CYAN)}")
                logger.info(f"   {msg}")
                should_skip = True
                skip_count = 1

            else:
                msg = f"✗ ERROR (exit code: {return_code})"
                print(f"\n{colored(msg, Fore.RED)}")
                logger.error(f"   {msg}")

            # Error classification
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
                msg = "✗ FATAL ERROR! Stopping script"
                print(colored(f"\n{msg}", Fore.RED))
                logger.critical(msg)
                return (0, 0, 0, None, consecutive_dns_errors, True)

            if has_dns_error and consecutive_dns_errors >= max_consecutive_dns_errors:
                msg = f"⚠ Critical number of DNS errors ({consecutive_dns_errors})!"
                print(colored(f"\n{msg}", Fore.RED))
                logger.warning(msg)
                if not check_dns_resolution('www.youtube.com'):
                    logger.warning("DNS unavailable, waiting for recovery...")
                    if wait_for_dns_recovery('www.youtube.com', check_interval=cfg["network"]["dns_check_interval"], max_wait=cfg["network"]["dns_recovery_timeout"]):
                        consecutive_dns_errors = 0
                        pause_time = 30
                    else:
                        logger.error("DNS not recovered")
                        return (0, 0, 0, None, consecutive_dns_errors, True)
                else:
                    logger.info("DNS available, continuing")
                    consecutive_dns_errors = 0

            if pause_time > 0:
                msg = f"Pausing {pause_time} seconds..."
                print(colored(f"   {msg}", Fore.YELLOW))
                logger.info(f"   {msg}")
                for remaining in range(pause_time, 0, -60):
                    mins = remaining // 60
                    if mins > 0:
                        print(f"\r   Remaining: {mins} min... ", end='', flush=True)
                    time.sleep(min(60, remaining))
                print()

            if attempt >= max_attempts or should_skip:
                if should_skip:
                    msg = "Skipping URL (irreversible error)"
                    print(colored(f"   {msg}", Fore.YELLOW))
                    logger.info(f"   {msg}")
                    if skip_count == 0:
                        skip_count = 1
                else:
                    msg = f"✗ Failed after {max_attempts} attempts"
                    print(colored(f"   {msg}", Fore.RED))
                    logger.error(f"   {msg}")
                    fail_count = 1

        except KeyboardInterrupt:
            raise

        except Exception as e:
            msg = f"✗ EXCEPTION: {e}"
            print(f"\n{colored(msg, Fore.RED)}")
            logger.exception(f"   {msg}")
            if attempt >= max_attempts:
                fail_count = 1

    failed_url = url if fail_count > 0 else None
    return (success_count, skip_count, fail_count, failed_url, consecutive_dns_errors, False)

def download_youtube_videos(links_file=None):
    """Downloads YouTube videos with enhanced error handling and playlist progress tracking"""
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
        print(colored(f"✓ Created folder: {downloads_dir}", Fore.GREEN))

    logger = setup_logger(log_file, max_bytes=cfg["logging"]["max_bytes"], backup_count=cfg["logging"]["backup_count"])

    if not os.path.exists(links_path):
        print(colored(f"✗ File {links_file} not found!", Fore.RED))
        return False

    try:
        active_links = read_links_file(links_path)
    except Exception as e:
        print(colored(f"✗ Error reading file: {e}", Fore.RED))
        return False

    if not active_links:
        print(colored("✓ No active links to download", Fore.GREEN))
        return True

    print(colored(f"Links found: {len(active_links)}", Fore.CYAN))
    print(colored(f"Downloads folder: {downloads_dir}", Fore.CYAN))
    print(colored(f"Log (max 10 MB, 5 backup): {log_file}", Fore.CYAN))
    print(colored(f"Archive: {archive_file}", Fore.CYAN))
    print(colored("="*70, Fore.BLUE))

    logger.info(f"{'='*70}")
    logger.info(f"Starting download: {len(active_links)} links")
    logger.info(f"Downloads folder: {downloads_dir}")
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

            # When (0,0,0) — stats unavailable (timeout/network error),
            # don't treat the playlist as empty, continue downloading — yt-dlp handles the archive.
            if total_vids == 0 and downloaded_vids == 0 and remaining_vids == 0:
                print(colored(f"\n⚠ Could not get playlist statistics (timeout or network error)", Fore.YELLOW))
                print(colored(f"   Continuing download — yt-dlp uses the archive independently", Fore.YELLOW))
                logger.warning(f"   Playlist statistics unavailable, download continues")
            elif remaining_vids > 0:
                print(colored(f"\n📊 PLAYLIST: total {total_vids}, downloaded {downloaded_vids}, remaining {remaining_vids}", Fore.MAGENTA))
                logger.info(f"   Playlist stats: {total_vids} total, {downloaded_vids} downloaded, {remaining_vids} remaining")
            elif total_vids > 0 and remaining_vids == 0:
                print(colored(f"\n✓ PLAYLIST ALREADY FULLY DOWNLOADED ({total_vids} videos)", Fore.GREEN))
                logger.info(f"   Playlist fully downloaded: {total_vids} videos")
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

        # Post-download playlist re-check
        if is_playlist:
            total_vids, downloaded_vids, remaining_vids = get_playlist_info(url, archive_file, logger)
            if total_vids == 0:
                logger.warning(f"   Final playlist stats unavailable")
            elif remaining_vids > 0:
                print(colored(f"\n⚠ WARNING: {remaining_vids} videos remaining in playlist ({total_vids} total)", Fore.YELLOW))
                logger.warning(f"   Playlist incomplete: {remaining_vids} videos remaining")
                print(colored(f"   Consider running the script again to finish", Fore.YELLOW))
            else:
                print(colored(f"\n✓ Playlist fully downloaded ({total_vids} videos)", Fore.GREEN))
                logger.info(f"   Playlist complete: {total_vids} videos")

        if idx < len(active_links):
            pause = 10 if success > 0 else 5
            print(colored(f"Pausing {pause} sec...", Fore.CYAN))
            time.sleep(pause)

    # Final statistics
    total_duration = time.time() - total_start_time
    stats = [
        "="*70,
        "COMPLETED!",
        "="*70,
        f"✓ Successfully downloaded: {total_success}",
        f"⊘ Skipped: {total_skip}",
        f"✗ Errors: {total_fail}",
        f"Total links processed: {len(active_links)}",
        f"Total time: {format_time(total_duration)}",
    ]
    if len(active_links) > 0:
        stats.append(f"Average time: {format_time(total_duration / len(active_links))}/link")
    stats.append("="*70)

    print(f"\n{colored('='*70, Fore.BLUE)}")
    print(colored("COMPLETED!", Fore.GREEN))
    print(colored('='*70, Fore.BLUE))
    print(colored(f"✓ Success: {total_success}", Fore.GREEN))
    print(colored(f"⊘ Skipped: {total_skip}", Fore.CYAN))
    print(colored(f"✗ Errors: {total_fail}", Fore.RED))
    print(colored(f"Total: {len(active_links)} links", Fore.CYAN))
    print(colored(f"Time: {format_time(total_duration)}", Fore.CYAN))
    if len(active_links) > 0:
        print(colored(f"Average: {format_time(total_duration / len(active_links))}/link", Fore.CYAN))
    print(colored('='*70, Fore.BLUE))

    logger.info(f"\n{'='*70}")
    for stat in stats[1:-1]:
        logger.info(stat)
    logger.info(f"{'='*70}\n")

    if failed_urls:
        failed_file = os.path.join(script_dir, cfg["downloads"]["failed_links_file"])
        with open(failed_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(failed_urls))
        msg = f"⚠ Failed ({len(failed_urls)} items): failed_links.txt"
        print(f"\n{colored(msg, Fore.YELLOW)}")
        logger.info(f"\n{msg}")

    print(colored(f"\nDownloads folder: {downloads_dir}", Fore.CYAN))
    print(colored(f"Full log: {log_file}", Fore.CYAN))
    print(colored(f"   (auto-rotation at 10 MB, keeps 5 backups)", Fore.CYAN))

    # Final check for incomplete playlists
    incomplete_playlists = []
    for url in active_links:
        if is_playlist_url(url):
            total_vids, _, remaining = get_playlist_info(url, archive_file, None)
            if total_vids > 0 and remaining > 0:
                incomplete_playlists.append((url, remaining))

    if incomplete_playlists:
        print(f"\n{colored('⚠ WARNING: Incomplete playlists detected:', Fore.YELLOW)}")
        for url, remaining in incomplete_playlists:
            print(colored(f"   • {url} - {remaining} videos remaining", Fore.YELLOW))
        print(colored("   Consider running the script again to continue downloading", Fore.YELLOW))
        return False

    return True

def main_with_auto_restart():
    """Main function with automatic restart on critical errors"""
    consecutive_failures = 0
    max_consecutive_failures = 3
    restart_count = 0

    print(colored("="*70, Fore.BLUE))
    print(colored("YouTube Downloader with playlist progress tracking", Fore.CYAN))
    print(colored("Thumbnails: JPG | Metadata: .info.json + .nfo (Plex/Kodi)", Fore.CYAN))
    print(colored("="*70, Fore.BLUE))
    print()

    if not check_dns_resolution('www.youtube.com'):
        print(colored("⚠ WARNING: YouTube is unavailable!", Fore.YELLOW))
        print(colored("   Check your internet connection", Fore.YELLOW))
        print(colored("   Continuing in 10 seconds...", Fore.YELLOW))
        time.sleep(10)
    else:
        print(colored("✓ YouTube is available", Fore.GREEN))
        print()

    while True:
        try:
            restart_count += 1
            if restart_count > 1:
                print(f"\n{colored('='*70, Fore.YELLOW)}")
                print(colored(f"AUTO-RESTART #{restart_count}", Fore.YELLOW))
                print(colored("Continuing with incomplete playlists...", Fore.YELLOW))
                print(colored('='*70, Fore.YELLOW))
                print()

            result = download_youtube_videos()

            if result:
                print(colored("\n✓ Script completed successfully - all playlists fully downloaded", Fore.GREEN))
                break
            else:
                consecutive_failures += 1
                print(colored(f"\n⚠ Incomplete playlists detected (attempt #{consecutive_failures}/{max_consecutive_failures})", Fore.YELLOW))
                if consecutive_failures >= max_consecutive_failures:
                    print(colored("\n✗ Too many consecutive failures", Fore.RED))
                    print(colored("Check:", Fore.YELLOW))
                    print(colored("   1. Is your internet connection working?", Fore.YELLOW))
                    print(colored("   2. Is YouTube accessible (check in browser)?", Fore.YELLOW))
                    print(colored("   3. Is VPN/proxy active (if required)?", Fore.YELLOW))
                    print(colored("\nWaiting 5 minutes before continuing...", Fore.YELLOW))
                    time.sleep(300)
                    consecutive_failures = 0
                else:
                    print(colored("Restarting in 60 seconds to continue downloading...", Fore.CYAN))
                    time.sleep(60)

        except KeyboardInterrupt:
            print(colored("\n\n⚠ INTERRUPTED BY USER", Fore.YELLOW))
            print(colored("Shutting down...", Fore.CYAN))
            sys.exit(0)

        except Exception as e:
            consecutive_failures += 1
            print(colored(f"\n✗ UNEXPECTED EXCEPTION: {e}", Fore.RED))
            if consecutive_failures >= max_consecutive_failures:
                print(colored("\n✗ Critical error count, stopping", Fore.RED))
                sys.exit(1)
            print(colored(f"Restarting in 60 seconds... (#{consecutive_failures})", Fore.YELLOW))
            time.sleep(60)

if __name__ == '__main__':
    main_with_auto_restart()