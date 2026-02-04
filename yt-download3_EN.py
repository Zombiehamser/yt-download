import subprocess
import os
import time
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import socket
import json

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    print("For color output: pip install colorama\n")

def colored(text, color_code=''):
    """Returns colored text if colorama is available"""
    if COLORS_AVAILABLE and color_code:
        return f"{color_code}{text}{Style.RESET_ALL}"
    return text

def setup_logger(log_file, max_bytes=10*1024*1024, backup_count=5):
    """
    Configures logger with file rotation
    max_bytes: maximum file size (default 10 MB)
    backup_count: number of backup copies (download.log.1, download.log.2, ...)
    """
    logger = logging.getLogger('yt_download')
    logger.setLevel(logging.INFO)

    # Remove existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # Rotating file handler with size limit
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )

    # Log format with timestamp
    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

def generate_nfo_file(info_json_path, logger=None):
    """
    Generates .nfo file from .info.json for Kodi/Plex
    """
    try:
        with open(info_json_path, 'r', encoding='utf-8') as f:
            info = json.load(f)

        # Path to .nfo file (replace .info.json with .nfo)
        nfo_path = info_json_path.replace('.info.json', '.nfo')

        # Extract data
        title = info.get('title', 'Unknown')
        video_id = info.get('id', '')
        uploader = info.get('uploader', info.get('channel', 'Unknown'))
        description = info.get('description', '')
        upload_date = info.get('upload_date', '')

        # Format date
        year = upload_date[:4] if len(upload_date) >= 4 else ''
        month_day = upload_date[4:] if len(upload_date) >= 8 else ''
        formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]} 00:00:00Z" if len(upload_date) == 8 else ''

        # Create .nfo content
        nfo_content = f"""{title}
{uploader}
{video_id}
{description}
{formatted_date}
{year}
{month_day}
YouTube"""

        # Save .nfo file
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
    Checks DNS resolution capability for specified host
    Returns True if DNS works, False otherwise
    """
    try:
        socket.setdefaulttimeout(timeout)
        result = socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        return len(result) > 0
    except (socket.gaierror, socket.timeout, OSError) as e:
        return False

def wait_for_dns_recovery(host='www.youtube.com', check_interval=60, max_wait=3600):
    """
    Waits for DNS resolution recovery
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
            print(colored(f"✓ DNS restored after {elapsed}s", Fore.GREEN))
            return True

        mins_left = (max_wait - elapsed) // 60
        print(f"\r⏳ Elapsed {elapsed}s, remaining ~{mins_left}m... ", end='', flush=True)

    print(colored(f"\n✗ DNS not restored in {max_wait}s", Fore.RED))
    return False

def check_ytdlp_installed():
    """Checks if yt-dlp is installed and its version"""
    try:
        result = subprocess.run(['yt-dlp', '--version'],
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(colored(f"✓ yt-dlp version: {version}", Fore.GREEN))

            # Check ffmpeg
            ffmpeg_check = subprocess.run(['ffmpeg', '-version'],
                                        capture_output=True, timeout=5)
            if ffmpeg_check.returncode == 0:
                print(colored("✓ ffmpeg found", Fore.GREEN))
            else:
                print(colored("⚠ ffmpeg not found - format merging unavailable", Fore.YELLOW))

            print()
            return True
    except FileNotFoundError:
        print(colored("✗ yt-dlp not found! Install: pip install -U yt-dlp", Fore.RED))
        return False
    except Exception as e:
        print(colored(f"✗ Check error: {e}", Fore.RED))
        return False

def format_time(seconds):
    """Formats seconds into readable format"""
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
    """Reads file with links"""
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
            'message': 'DNS error - check internet connection'
        })
        return error_type

    # Rate limit
    if 'rate-limited' in line_lower or 'rate limit' in line_lower:
        error_type.update({
            'retry': False,
            'pause': 3600,
            'message': 'YouTube rate limit! Pause 1 hour'
        })
        return error_type

    # Bot detection
    if 'sign in' in line_lower and 'bot' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 300,
            'message': 'Bot detected! Pause 5 minutes'
        })
        return error_type

    # HTTP errors
    if 'http error 403' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 600,
            'message': 'HTTP 403: Cookies/access issue'
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
            'message': 'Video removed'
        })

    # Content availability
    if 'private video' in line_lower or 'members-only' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Private video or members-only content'
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
            'message': 'Age restriction - check cookies'
        })
    elif 'geo' in line_lower and ('blocked' in line_lower or 'restricted' in line_lower):
        error_type.update({
            'skip': True,
            'message': 'Geo-blocked content'
        })
    elif 'copyright' in line_lower or 'takedown' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Removed due to copyright'
        })
    elif 'requires payment' in line_lower or 'rental' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Requires payment'
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
            'message': 'No file/directory access permission'
        })
    elif ('ffmpeg' in line_lower or 'ffprobe' in line_lower) and 'not found' in line_lower:
        error_type.update({
            'fatal': True,
            'message': 'ffmpeg not found - cannot merge formats'
        })

    return error_type

def download_youtube_videos(links_file='links.txt'):
    """Downloads YouTube videos with enhanced error handling"""
    if not check_ytdlp_installed():
        return False

    script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
    downloads_dir = os.path.join(script_dir, 'downloads')
    links_path = os.path.join(script_dir, links_file)
    log_file = os.path.join(script_dir, 'download.log')
    archive_file = os.path.join(script_dir, 'download_archive.txt')

    # Create downloads folder if it doesn't exist
    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)
        print(colored(f"✓ Created folder: {downloads_dir}", Fore.GREEN))

    # Setup logger with rotation (10 MB, 5 backup copies)
    logger = setup_logger(log_file, max_bytes=10*1024*1024, backup_count=5)

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

    print(colored(f"Found links: {len(active_links)}", Fore.CYAN))
    print(colored(f"Downloads folder: {downloads_dir}", Fore.CYAN))
    print(colored(f"Log (max 10 MB, 5 backups): {log_file}", Fore.CYAN))
    print(colored(f"Archive: {archive_file}", Fore.CYAN))
    print(colored("="*70, Fore.BLUE))

    logger.info(f"{'='*70}")
    logger.info(f"Download started: {len(active_links)} videos")
    logger.info(f"Downloads folder: {downloads_dir}")
    logger.info(f"{'='*70}")

    success_count = 0
    fail_count = 0
    skip_count = 0
    failed_urls = []
    total_start_time = time.time()

    # DNS error counter
    consecutive_dns_errors = 0
    max_consecutive_dns_errors = 20

    for idx, url in enumerate(active_links, 1):
        print(f"\n{colored('='*70, Fore.BLUE)}")
        print(colored(f"[{idx}/{len(active_links)}] {url}", Fore.YELLOW))
        print(colored('='*70, Fore.BLUE))
        logger.info(f"\n[{idx}/{len(active_links)}] URL: {url}")

        video_start_time = time.time()

        # yt-dlp command optimized for unstable connections
        cmd = [
            'yt-dlp',
            '--cookies-from-browser', 'firefox',
            '--remote-components', 'ejs:github',

            # Format and conversion
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--merge-output-format', 'mp4',
            '--remux-video', 'mp4',

            # Retry attempts
            '--retries', '15',
            '--fragment-retries', '15',
            '--extractor-retries', '8',
            '--file-access-retries', '5',

            # Delays
            '--sleep-requests', '5',
            '--sleep-interval', '20',
            '--max-sleep-interval', '60',

            # Timeouts
            '--socket-timeout', '60',

            # Download optimization
            '--concurrent-fragments', '1',
            '--buffer-size', '16K',

            # Metadata and thumbnails
            '--embed-metadata',
            '--embed-thumbnail',
            '--write-thumbnail',  # IMPORTANT: save thumbnail as separate file
            '--convert-thumbnails', 'jpg',  # Convert to JPG
            '--write-info-json',  # Create .info.json

            # File naming
            '--windows-filenames',
            '--output', os.path.join(downloads_dir, '%(title).200s [%(id)s].%(ext)s'),

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

            url
        ]

        max_attempts = 3
        attempt = 0
        success = False
        should_skip = False
        was_already_downloaded = False
        video_id = None

        while attempt < max_attempts and not success and not should_skip:
            attempt += 1

            if attempt > 1:
                msg = f"RETRY ATTEMPT {attempt}/{max_attempts}"
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
                dns_errors_in_video = 0

                # Process timeout - 60 minutes per video
                start_time = time.time()
                timeout_seconds = 3600

                while True:
                    # Check timeout
                    if time.time() - start_time > timeout_seconds:
                        process.kill()
                        msg = "TIMEOUT! Process stuck for more than 60 minutes"
                        print(colored(f"\n⚠ {msg}", Fore.RED))
                        logger.warning(f"  {msg}")
                        break

                    line = process.stdout.readline()

                    if not line and process.poll() is not None:
                        break

                    if line:
                        line = line.rstrip()
                        line_lower = line.lower()

                        # Extract video ID for subsequent .nfo generation
                        if not video_id and '[download]' in line and 'Destination' in line:
                            import re
                            match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', line)
                            if match:
                                video_id = match.group(1)

                        # Already downloaded
                        if 'has already been downloaded' in line_lower or 'has already been recorded in the archive' in line_lower:
                            was_already_downloaded = True
                            print(colored(line, Fore.CYAN))
                            logger.info(f"  {line}")
                            continue

                        # Collect errors
                        if 'error' in line_lower or 'warning' in line_lower:
                            error_keywords.append(line)
                            error_details.append(line)

                            # Special DNS error handling
                            if 'failed to resolve' in line_lower or 'getaddrinfo failed' in line_lower:
                                dns_errors_in_video += 1
                                consecutive_dns_errors += 1
                                logger.error(f"  DNS ERROR #{consecutive_dns_errors}: {line}")
                            else:
                                logger.error(f"  ERROR: {line}")

                        # Download progress
                        if '[download]' in line and '%' in line:
                            sys.stdout.write('\r' + ' ' * 100 + '\r')
                            sys.stdout.write(colored(line, Fore.GREEN))
                            sys.stdout.flush()
                            last_line_was_progress = True
                        else:
                            if last_line_was_progress:
                                print()
                                last_line_was_progress = False

                            # Colored output
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

                # Analyze result
                if return_code == 0:
                    if was_already_downloaded:
                        msg = "⊘ ALREADY DOWNLOADED"
                        print(f"\n{colored(msg, Fore.CYAN)}")
                        logger.info(f"  {msg}")
                        skip_count += 1
                    else:
                        msg = f"✓ SUCCESS in {format_time(video_duration)}"
                        print(f"\n{colored(msg, Fore.GREEN)}")
                        logger.info(f"  {msg}")
                        success_count += 1
                        consecutive_dns_errors = 0

                        # Generate .nfo file from .info.json
                        if video_id:
                            info_json_pattern = os.path.join(downloads_dir, f"*[{video_id}].info.json")
                            import glob
                            info_json_files = glob.glob(info_json_pattern)
                            if info_json_files:
                                print(colored("  Generating .nfo file for Plex/Kodi...", Fore.CYAN))
                                generate_nfo_file(info_json_files[0], logger)

                    success = True

                elif return_code == 2:
                    msg = "✗ COMMAND PARAMETER ERROR! (exit code 2)"
                    print(f"\n{colored(msg, Fore.RED)}")
                    logger.error(f"  {msg}")
                    should_skip = True
                    fail_count += 1
                    failed_urls.append(url)

                elif return_code == 101:
                    msg = "⊘ DOWNLOAD CANCELLED (exit code 101)"
                    print(f"\n{colored(msg, Fore.CYAN)}")
                    logger.info(f"  {msg}")
                    should_skip = True
                    skip_count += 1

                else:
                    msg = f"✗ ERROR (exit code: {return_code})"
                    print(f"\n{colored(msg, Fore.RED)}")
                    logger.error(f"  {msg}")

                    # Error classification
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

                    # Fatal error - stop everything
                    if fatal_error:
                        msg = "✗ FATAL ERROR! Stopping script"
                        print(colored(f"\n{msg}", Fore.RED))
                        logger.critical(msg)
                        return False

                    # Check critical DNS error count
                    if has_dns_error and consecutive_dns_errors >= max_consecutive_dns_errors:
                        msg = f"⚠ Critical DNS error count ({consecutive_dns_errors})!"
                        print(colored(f"\n{msg}", Fore.RED))
                        logger.warning(msg)

                        if not check_dns_resolution('www.youtube.com'):
                            logger.warning("DNS unavailable, waiting for recovery...")
                            if wait_for_dns_recovery('www.youtube.com', check_interval=60, max_wait=600):
                                consecutive_dns_errors = 0
                                pause_time = 30
                            else:
                                logger.error("DNS not restored, returning False for restart")
                                return False
                        else:
                            logger.info("DNS available, continuing")
                            consecutive_dns_errors = 0

                    # Pause if required
                    if pause_time > 0:
                        msg = f"Pause {pause_time} seconds..."
                        print(colored(f"  {msg}", Fore.YELLOW))
                        logger.info(f"  {msg}")

                        for remaining in range(pause_time, 0, -60):
                            mins = remaining // 60
                            if mins > 0:
                                print(f"\r  Remaining: {mins} min... ", end='', flush=True)
                            time.sleep(min(60, remaining))
                        print()

                if attempt >= max_attempts or should_skip:
                    if should_skip:
                        msg = "Skipping video (irreversible error)"
                        print(colored(f"  {msg}", Fore.YELLOW))
                        logger.info(f"  {msg}")
                        skip_count += 1
                    else:
                        msg = f"✗ Failed after {max_attempts} attempts"
                        print(colored(f"  {msg}", Fore.RED))
                        logger.error(f"  {msg}")
                        fail_count += 1
                        failed_urls.append(url)

            except KeyboardInterrupt:
                msg = "⚠ INTERRUPTED BY USER"
                print(f"\n\n{colored(msg, Fore.YELLOW)}")
                logger.warning(f"\n{msg} on {idx}/{len(active_links)}")
                print(colored(f"Processed: {idx-1}/{len(active_links)}", Fore.CYAN))
                print(colored(f"✓ Success: {success_count}", Fore.GREEN))
                print(colored(f"⊘ Skipped: {skip_count}", Fore.CYAN))
                print(colored(f"✗ Failed: {fail_count}", Fore.RED))
                sys.exit(0)

            except Exception as e:
                msg = f"✗ EXCEPTION: {e}"
                print(f"\n{colored(msg, Fore.RED)}")
                logger.exception(f"  {msg}")

                if attempt >= max_attempts:
                    fail_count += 1
                    failed_urls.append(url)

        # Pause between videos (only after success/failure, not for already downloaded)
        if idx < len(active_links) and not was_already_downloaded:
            pause = 10 if success else 5
            print(colored(f"Pause {pause} sec...", Fore.CYAN))
            time.sleep(pause)

    # Final statistics
    total_duration = time.time() - total_start_time

    stats = [
        "="*70,
        "COMPLETED!",
        "="*70,
        f"✓ Successfully downloaded: {success_count}",
        f"⊘ Skipped: {skip_count}",
        f"✗ Failed: {fail_count}",
        f"Total processed: {len(active_links)}",
        f"Total time: {format_time(total_duration)}",
    ]

    if len(active_links) > 0:
        stats.append(f"Average time: {format_time(total_duration / len(active_links))}/video")

    stats.append("="*70)

    # Console output
    print(f"\n{colored('='*70, Fore.BLUE)}")
    print(colored("COMPLETED!", Fore.GREEN))
    print(colored('='*70, Fore.BLUE))
    print(colored(f"✓ Success: {success_count}", Fore.GREEN))
    print(colored(f"⊘ Skipped: {skip_count}", Fore.CYAN))
    print(colored(f"✗ Failed: {fail_count}", Fore.RED))
    print(colored(f"Total: {len(active_links)}", Fore.CYAN))
    print(colored(f"Time: {format_time(total_duration)}", Fore.CYAN))

    if len(active_links) > 0:
        print(colored(f"Average: {format_time(total_duration / len(active_links))}/video", Fore.CYAN))

    print(colored('='*70, Fore.BLUE))

    # Write to log
    logger.info(f"\n{'='*70}")
    for stat in stats[1:-1]:
        logger.info(stat)
    logger.info(f"{'='*70}\n")

    # Save failed URLs
    if failed_urls:
        failed_file = os.path.join(script_dir, 'failed_links.txt')
        with open(failed_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(failed_urls))

        msg = f"⚠ Failed ({len(failed_urls)} items): failed_links.txt"
        print(f"\n{colored(msg, Fore.YELLOW)}")
        logger.info(f"\n{msg}")

    print(colored(f"\nDownloads folder: {downloads_dir}", Fore.CYAN))
    print(colored(f"Full log: {log_file}", Fore.CYAN))
    print(colored(f"  (auto-rotation at 10 MB, 5 backups kept)", Fore.CYAN))

    return True

def main_with_auto_restart():
    """Main function with automatic restart on critical errors"""
    consecutive_failures = 0
    max_consecutive_failures = 3
    restart_count = 0

    print(colored("="*70, Fore.BLUE))
    print(colored("YouTube Downloader with automatic restart", Fore.CYAN))
    print(colored("Thumbnails: JPG | Metadata: .info.json + .nfo (Plex/Kodi)", Fore.CYAN))
    print(colored("="*70, Fore.BLUE))
    print()

    # Check DNS at startup
    if not check_dns_resolution('www.youtube.com'):
        print(colored("⚠ WARNING: YouTube unavailable!", Fore.YELLOW))
        print(colored("  Check internet connection", Fore.YELLOW))
        print(colored("  Continuing in 10 seconds...", Fore.YELLOW))
        time.sleep(10)
    else:
        print(colored("✓ YouTube available", Fore.GREEN))

    print()

    while True:
        try:
            restart_count += 1

            if restart_count > 1:
                print(f"\n{colored('='*70, Fore.YELLOW)}")
                print(colored(f"AUTOMATIC RESTART #{restart_count}", Fore.YELLOW))
                print(colored('='*70, Fore.YELLOW))
                print()

            result = download_youtube_videos()

            if result:
                print(colored("\n✓ Script completed successfully", Fore.GREEN))
                break
            else:
                consecutive_failures += 1
                print(colored(f"\n⚠ Critical error #{consecutive_failures}/{max_consecutive_failures}", Fore.YELLOW))

                if consecutive_failures >= max_consecutive_failures:
                    print(colored("\n✗ Too many consecutive errors", Fore.RED))
                    print(colored("Check:", Fore.YELLOW))
                    print(colored("  1. Internet connection", Fore.YELLOW))
                    print(colored("  2. YouTube availability (check in browser)", Fore.YELLOW))
                    print(colored("  3. VPN/proxy activity (if required)", Fore.YELLOW))
                    print(colored("\nWaiting 5 minutes before continuing...", Fore.YELLOW))
                    time.sleep(300)
                    consecutive_failures = 0
                else:
                    print(colored("Restarting in 60 seconds...", Fore.CYAN))
                    time.sleep(60)

        except KeyboardInterrupt:
            print(colored("\n\n⚠ INTERRUPTED BY USER", Fore.YELLOW))
            print(colored("Shutting down...", Fore.CYAN))
            sys.exit(0)

        except Exception as e:
            consecutive_failures += 1
            print(colored(f"\n✗ UNEXPECTED EXCEPTION: {e}", Fore.RED))

            if consecutive_failures >= max_consecutive_failures:
                print(colored("\n✗ Critical error count reached, stopping", Fore.RED))
                sys.exit(1)

            print(colored(f"Restarting in 60 seconds... (#{consecutive_failures})", Fore.YELLOW))
            time.sleep(60)

if __name__ == '__main__':
    main_with_auto_restart()