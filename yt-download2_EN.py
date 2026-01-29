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
    print("For colored output: pip install colorama\n")

def colored(text, color_code=''):
    """Returns colored text if colorama is available"""
    if COLORS_AVAILABLE and color_code:
        return f"{color_code}{text}{Style.RESET_ALL}"
    return text

def setup_logger(log_file, max_bytes=10*1024*1024, backup_count=3):
    """
    Configures logger with file rotation
    max_bytes: maximum file size (default 10 MB)
    backup_count: number of backup copies (download.log.1, download.log.2, ...)
    """
    logger = logging.getLogger('yt_download')
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers if any
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
    """Formats seconds to readable format"""
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
    """Reads links file"""
    with open(links_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    links = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and stripped.startswith('http'):
            links.append(stripped)
    
    return links

def classify_error(line_lower, error_keywords):
    """Classifies errors into categories"""
    error_type = {
        'skip': False,     # Skip without retry
        'retry': False,    # Retry attempt
        'pause': 0,        # Seconds to pause
        'fatal': False,    # Fatal error
        'message': ''
    }
    
    # Rate limit - CRITICAL for bulk downloads
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
            'message': 'Bot detection! Pause 5 minutes'
        })
        return error_type
    
    # HTTP errors
    if 'http error 403' in line_lower:
        error_type.update({
            'retry': True,
            'pause': 600,
            'message': 'HTTP 403: Problem with cookies/access'
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
            'message': 'Age-restricted - check cookies'
        })
    elif 'geo' in line_lower and ('blocked' in line_lower or 'restricted' in line_lower):
        error_type.update({
            'skip': True,
            'message': 'Geo-blocked'
        })
    elif 'copyright' in line_lower or 'takedown' in line_lower:
        error_type.update({
            'skip': True,
            'message': 'Removed by copyright'
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
            'message': 'No access permissions to file/directory'
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
        return
    
    script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
    links_path = os.path.join(script_dir, links_file)
    log_file = os.path.join(script_dir, 'download.log')
    archive_file = os.path.join(script_dir, 'download_archive.txt')
    
    # Setup logger with rotation (10 MB, 5 backup copies)
    logger = setup_logger(log_file, max_bytes=10*1024*1024, backup_count=5)
    
    if not os.path.exists(links_path):
        print(colored(f"✗ File {links_file} not found!", Fore.RED))
        return
    
    try:
        active_links = read_links_file(links_path)
    except Exception as e:
        print(colored(f"✗ File read error: {e}", Fore.RED))
        return
    
    if not active_links:
        print(colored("✓ No active links to download", Fore.GREEN))
        return
    
    print(colored(f"Links found: {len(active_links)}", Fore.CYAN))
    print(colored(f"Log (max 10 MB, 5 backups): {log_file}", Fore.CYAN))
    print(colored(f"Archive: {archive_file}", Fore.CYAN))
    print(colored("=" * 70, Fore.BLUE))
    
    logger.info(f"{'='*70}")
    logger.info(f"Starting download: {len(active_links)} videos")
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
        
        # ENHANCED COMMAND with additional options
        cmd = [
            'yt-dlp',
            '--cookies-from-browser', 'firefox',
            '--remote-components', 'ejs:github',
            
            # Format and conversion
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--merge-output-format', 'mp4',
            '--remux-video', 'mp4',
            
            # Retry attempts
            '--retries', '10',
            '--fragment-retries', '10',
            '--extractor-retries', '5',
            '--file-access-retries', '3',
            
            # Delays (optimized)
            '--sleep-requests', '3',
            '--sleep-interval', '15',
            '--max-sleep-interval', '45',
            
            # Timeouts
            '--socket-timeout', '30',
            
            # Download optimization
            '--concurrent-fragments', '1',
            '--buffer-size', '16K',
            
            # Metadata and naming
            '--embed-metadata',
            '--embed-thumbnail',
            '--windows-filenames',
            '--output', '%(title).200s [%(id)s].%(ext)s',
            
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
                
                # Timeout for entire process - 60 minutes per video
                start_time = time.time()
                timeout_seconds = 3600
                
                while True:
                    # Check timeout
                    if time.time() - start_time > timeout_seconds:
                        process.kill()
                        msg = "TIMEOUT! Process hung for more than 60 minutes"
                        print(colored(f"\n⚠ {msg}", Fore.RED))
                        logger.warning(f"  {msg}")
                        break
                    
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    
                    if line:
                        line = line.rstrip()
                        line_lower = line.lower()
                        
                        # Already downloaded
                        if 'has already been downloaded' in line_lower:
                            was_already_downloaded = True
                            print(colored(line, Fore.CYAN))
                            logger.info(f"  {line}")
                            continue
                        
                        # Collect errors
                        if 'error' in line_lower:
                            error_keywords.append(line)
                            error_details.append(line)
                            # Log each error immediately
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
                
                # Result analysis
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
                        success = True
                        
                elif return_code == 2:
                    msg = "✗ COMMAND PARAMETERS ERROR! (exit code 2)"
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
                    
                else:  # return_code == 1 or others
                    msg = f"✗ ERROR (exit code: {return_code})"
                    print(f"\n{colored(msg, Fore.RED)}")
                    logger.error(f"  {msg}")
                    
                    # Classify errors
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
                    
                    # Fatal error - stop everything
                    if fatal_error:
                        msg = "✗ FATAL ERROR! Stopping script"
                        print(colored(f"\n{msg}", Fore.RED))
                        logger.critical(msg)
                        return
                    
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
                logger.warning(f"\n{msg} at {idx}/{len(active_links)}")
                print(colored(f"Processed: {idx-1}/{len(active_links)}", Fore.CYAN))
                print(colored(f"✓ Success: {success_count}", Fore.GREEN))
                print(colored(f"⊘ Skipped: {skip_count}", Fore.CYAN))
                print(colored(f"✗ Errors: {fail_count}", Fore.RED))
                sys.exit(0)
                
            except Exception as e:
                msg = f"✗ EXCEPTION: {e}"
                print(f"\n{colored(msg, Fore.RED)}")
                logger.exception(f"  {msg}")  # exception() will automatically add traceback
                if attempt >= max_attempts:
                    fail_count += 1
                    failed_urls.append(url)
        
        # Pause between videos (only after success/fail, not after already downloaded)
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
        f"✗ Errors: {fail_count}",
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
    print(colored(f"✗ Errors: {fail_count}", Fore.RED))
    print(colored(f"Total: {len(active_links)}", Fore.CYAN))
    print(colored(f"Time: {format_time(total_duration)}", Fore.CYAN))
    if len(active_links) > 0:
        print(colored(f"Average: {format_time(total_duration / len(active_links))}/video", Fore.CYAN))
    print(colored('='*70, Fore.BLUE))
    
    # Write to log
    logger.info(f"\n{'='*70}")
    for stat in stats[1:-1]:  # Without separators
        logger.info(stat)
    logger.info(f"{'='*70}\n")
    
    # Save failed
    if failed_urls:
        failed_file = os.path.join(script_dir, 'failed_links.txt')
        with open(failed_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(failed_urls))
        
        msg = f"⚠ Failed ({len(failed_urls)} pcs.): failed_links.txt"
        print(f"\n{colored(msg, Fore.YELLOW)}")
        logger.info(f"\n{msg}")
    
    print(colored(f"\nFull log: {log_file}", Fore.CYAN))
    print(colored(f"  (auto-rotation at 10 MB, 5 backups stored)", Fore.CYAN))

if __name__ == '__main__':
    download_youtube_videos()