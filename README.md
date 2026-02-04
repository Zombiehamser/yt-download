# yt-download

**Version:** 3.0 | **Last Updated:** 04 February 2026

[![en](https://img.shields.io/badge/lang-en-red.svg)](README.md)
[![ru](https://img.shields.io/badge/lang-ru-blue.svg)](README_RU.md)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Free-green.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)]()
[![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-red.svg)](https://github.com/yt-dlp/yt-dlp)

*[Read in Russian](README_RU.md)*

---

**Automated YouTube video downloader (yt-dlp) with intelligent error handling, DNS recovery, auto-restart, NFO generation for Plex/Kodi, and detailed logging for mass downloads.**

## ✨ Features

- 🧠 **Intelligent Error Handling** — 20+ error types classified into categories (skip, retry, pause, fatal)
- 🌐 **DNS Recovery System** — Automatic detection and waiting for DNS restoration
- 🔄 **Auto-Restart on Critical Errors** — Script automatically restarts after failures
- 📁 **NFO Generation** — Creates .nfo files for Plex/Kodi with metadata from .info.json
- 📊 **Detailed Logging** — Rotating logs with 10MB auto-rotation (keeps 5 backups)
- 🎯 **Resume Support** — Continue from where you left off via archive tracking
- 🍪 **Cookie Support** — Access age-restricted content with Firefox cookies
- 🎨 **Colored Output** — Real-time progress with color-coded status
- ⏱️ **Adaptive Delays** — 5-60 second intervals to avoid rate limits
- 📦 **MP4 Optimization** — Automatic metadata and thumbnail embedding
- 🔁 **Rate Limit Detection** — Automatic pauses from 30 seconds to 1 hour
- 🛡️ **Stable Connection** — Optimized for unstable networks (1 concurrent fragment)

## 📋 Table of Contents

- [Purpose](#purpose)
- [Quick Start](#-quick-start)
- [Key Features](#key-features)
- [System Requirements](#system-requirements)
- [Installing Dependencies](#installing-dependencies)
- [Usage](#-usage)
- [File Structure](#-file-structure)
- [Script Configuration](#️-script-configuration)
- [Operating Logic](#-operating-logic)
- [Handled Errors](#️-handled-errors)
- [NFO File Generation](#-nfo-file-generation)
- [Troubleshooting](#-troubleshooting)
- [FAQ](#-faq)
- [Additional Information](#-additional-information)
- [License](#-license)
- [Useful Links](#-useful-links)

## Purpose

The script is designed for reliable downloading of large video collections (hundreds and thousands of files, including playlists) in a "set and forget" mode. It automatically handles typical issues: DNS failures, YouTube rate limits, network errors, unavailable videos, with the ability to resume from where it left off. Includes NFO generation for media servers and automatic restart on critical errors.

## ⚡ Quick Start

```powershell
# 1. Install dependencies
pip install -U yt-dlp colorama
winget install ffmpeg

# 2. Create links.txt with YouTube URLs
echo https://www.youtube.com/watch?v=dQw4w9WgXcQ > links.txt

# 3. Run the script
python yt-download3_RU.py

That's it! The script will handle everything automatically with intelligent error recovery and DNS monitoring.

## Key Features

### Intelligent Error Handling
- Classification of **20+ error types** into categories: skip, retry, pause, fatal
- Automatic detection of **DNS failures** with recovery waiting
- Handling of HTTP 403/429/400/404/410, bot detection, geo-blocks, copyright, private videos
- Adaptive pauses depending on error type (from 30 seconds to 1 hour)

### DNS Recovery System
- Automatic detection of DNS resolution failures
- Smart waiting for DNS restoration (up to 10 minutes)
- Tracking consecutive DNS errors to prevent infinite loops
- Early DNS availability check before script start

### Auto-Restart Mechanism
- Automatic restart on critical errors (up to 3 consecutive failures)
- Graceful handling of network interruptions
- Resume from interruption point

### Media Server Integration
- Automatic generation of **.nfo files** for Plex/Kodi from .info.json
- Metadata extraction: title, uploader, description, upload date
- Compatible format with media server requirements

### Retry System
- Up to **3 attempts** per video with progressive delays
- Automatic skipping of irreversible errors (deleted/paid/private videos)
- Built-in hang protection (timeout **60 minutes** per video)

### Download Optimization
- Using cookies from Firefox to access age-restricted videos
- **Stable single-fragment downloading** (1 thread) for unstable connections
- Adaptive delays of **5-60 seconds** between videos to avoid blocks
- Automatic embedding of metadata and thumbnails into MP4
- Separate thumbnail saving as JPG files

### Logging and Monitoring
- Single log file `download.log` with timestamps of all events
- **Automatic log rotation** at 10 MB (keeps 5 backup copies)
- Colored console output with download progress bar (via colorama)
- Detailed statistics: successful/skipped/errors, total and average time

### Archiving and Resuming
- Uses yt-dlp's built-in mechanism to track downloaded videos by ID
- Automatic **skipping of already downloaded** files on restart
- Saving list of failed downloads to `failed_links.txt` for retry

## System Requirements

### Required Components

- **Windows**: 10/11 or Windows Server 2016+
- **Python**: 3.8 or higher → [Download Python](https://www.python.org/downloads/)
- **PowerShell**: 5.1 or higher (built into Windows)
- **yt-dlp**: latest version → [GitHub yt-dlp](https://github.com/yt-dlp/yt-dlp)
- **ffmpeg**: for merging video/audio formats → [Download ffmpeg](https://ffmpeg.org/download.html)

### Installing Dependencies

#### Installing yt-dlp and Python Libraries

```powershell
# Install yt-dlp
pip install -U yt-dlp

# Install colorama for colored output (optional but recommended)
pip install colorama
```

#### Installing ffmpeg

There are several ways to install ffmpeg in PowerShell on Windows.

##### Method 1: Via Winget (recommended)

Winget is built into Windows 10/11, so this is the easiest method:

```powershell
winget install ffmpeg
```

##### Method 2: Via Chocolatey

If you have Chocolatey installed, run in PowerShell with administrator rights:

```powershell
choco install ffmpeg
```

##### Method 3: Via Scoop

Scoop installs programs in a user directory without cluttering system folders:

```powershell
scoop install ffmpeg
```

##### Method 4: Manual Installation

If you prefer more control over the installation process:

1. Open PowerShell with administrator rights

2. Download and install ffmpeg:

```powershell
# Download ffmpeg
Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile "ffmpeg.zip"

# Extract to C:\
Expand-Archive -Path "ffmpeg.zip" -DestinationPath "C:\"

# Rename folder
$ffmpegFolder = Get-ChildItem -Path "C:\" -Filter "ffmpeg-*" -Directory
Rename-Item -Path $ffmpegFolder.FullName -NewName "ffmpeg"
```

3. Add ffmpeg to PATH:

```powershell
$envPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
[Environment]::SetEnvironmentVariable("PATH", $envPath + ";C:\ffmpeg\bin", "Machine")
```

4. Verify installation by opening a new terminal:

```powershell
ffmpeg -version
```

After installation, the following commands will be available: `ffmpeg`, `ffplay`, `ffprobe`.

## 🚀 Usage

### 1. Preparation

Create a file `links.txt` in the script folder, add one YouTube URL per line:

```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/watch?v=9bZkp7q19f0
https://www.youtube.com/watch?v=h4Bq69HfR0Y&list=RDh4Bq69HfR0Y&start_radio=1&pp=ygUMa2VybWl0IGRhbmNloAcB0gcJCXwKAYcqIYzv
```

### 2. Launch

```powershell
python yt-download3_RU.py
```

### 3. Monitoring

The script will automatically process all links with error handling. Progress is displayed in the console with color highlighting:
- 🟢 Green — successful download
- 🔵 Blue — already downloaded previously
- 🟡 Yellow — warnings and retries
- 🔴 Red — errors
- 🟣 Purple — merging process
- 🌐 Cyan — DNS recovery process

### 4. Interruption and Resuming

If necessary, interrupt the script with **Ctrl+C** — progress will be saved in `download_archive.txt`, and you can continue later from the same place. The script also has auto-restart capability for critical errors.

## 📁 File Structure

After running, the script will create the following files:

| File | Description |
|------|----------|
| `download.log` | Main log with timestamps of all events and errors |
| `download.log.1` - `.5` | Backup log copies (created during rotation) |
| `download_archive.txt` | yt-dlp service file with IDs of successfully downloaded videos |
| `failed_links.txt` | List of URLs of failed downloads for retry |
| `*.mp4` | Downloaded video files in format `Title [ID].mp4` |
| `*.info.json` | Metadata files with video information |
| `*.nfo` | Media server metadata files for Plex/Kodi |
| `*.jpg` | Thumbnail images in JPG format |

## ⚙️ Script Configuration

### Log Auto-rotation Parameters

In the `setup_logger()` function:

```python
logger = setup_logger(
    log_file, 
    max_bytes=10*1024*1024,  # Maximum log size in bytes (default 10 MB)
    backup_count=5           # Number of backup copies (default 5)
)
```

**Configuring log size and count:**
- `max_bytes` — file size at which rotation occurs (e.g., `20*1024*1024` for 20 MB)
- `backup_count` — number of old logs to keep (e.g., `3` for 3 copies)

### Retry Parameters

In the `download_youtube_videos()` function:

```python
max_attempts = 3  # Number of attempts per video (default 3)
```

### Timeout Parameters

In the download loop:

```python
timeout_seconds = 3600  # Timeout per video in seconds (default 3600 = 60 minutes)
```

### yt-dlp Delay Parameters

In the `cmd` array:

```python
'--sleep-requests', '5',      # Delay between API requests (seconds)
'--sleep-interval', '20',     # Minimum delay between videos (seconds)
'--max-sleep-interval', '60', # Maximum delay between videos (seconds)
'--socket-timeout', '60',     # Socket timeout (seconds)
```

**Delay configuration recommendations:**
- For unstable connections: `20-60` seconds (current values)
- With frequent rate limits: increase to `30-120` seconds

### Download Optimization Parameters

```python
'--concurrent-fragments', '1',  # Number of parallel threads (1 for stability)
'--buffer-size', '16K',         # Buffer size (16K optimal for most cases)
'--fragment-retries', '15',     # Fragment retry attempts
'--retries', '15',              # General retry attempts
```

### Filename Format

```python
'--output', '%(title).200s [%(id)s].%(ext)s',  # Filename template
```

**Available variables:**
- `%(title)s` — video title (truncated to 200 characters)
- `%(id)s` — video ID
- `%(uploader)s` — channel author
- `%(upload_date)s` — upload date

Full list: [yt-dlp Output Template](https://github.com/yt-dlp/yt-dlp#output-template)

### Browser for Cookie Export

```python
'--cookies-from-browser', 'firefox',  # Browser for cookies (firefox only in this config)
```

## 🔍 Operating Logic

1. ✅ **Initialization**: Checks yt-dlp, ffmpeg, and DNS availability
2. 📄 **Link Processing**: Reads `links.txt` file (ignores commented lines with `#`)
3. 🌐 **DNS Monitoring**: Continuously checks DNS resolution throughout process
4. 🎬 **Video Download**: For each video, launches yt-dlp with optimized parameters
5. 👁️ **Real-time Monitoring**: Tracks output, recognizes and classifies errors
6. 🔄 **Error Handling**: On error, decides: retry, skip, pause, or wait for DNS
7. 📁 **NFO Generation**: Creates .nfo files for media servers after successful download
8. 📝 **Logging**: Records all events with timestamps in `download.log` (with auto-rotation)
9. 💾 **Archiving**: Saves IDs of successfully downloaded videos in `download_archive.txt`
10. 🔁 **Auto-Restart**: Automatically restarts on critical errors (max 3 attempts)
11. 📊 **Statistics**: Outputs detailed stats and list of failed downloads

### DNS Recovery Process

1. **Detection**: Script monitors for "failed to resolve" or "getaddrinfo failed" errors
2. **Counting**: Tracks consecutive DNS errors (max 20 before critical action)
3. **Recovery Attempt**: Pauses and waits for DNS restoration (up to 10 minutes)
4. **Resumption**: Continues downloading once DNS is restored
5. **Fallback**: If DNS not restored, script can be restarted manually

### NFO File Generation

After each successful download, the script:
1. Locates the `.info.json` file created by yt-dlp
2. Extracts metadata: title, video ID, uploader, description, upload date
3. Creates a `.nfo` file with structured information for Plex/Kodi
4. Saves it alongside the video file with the same base name

## 📁 NFO File Generation

The script automatically generates `.nfo` files compatible with Plex, Kodi, and other media servers. These files contain structured metadata that helps media organizers properly catalog your videos.

### What's in the .nfo file:
- **Video Title**
- **Uploader/Channel name**
- **YouTube Video ID**
- **Video Description**
- **Upload Date** (formatted as YYYY-MM-DD HH:MM:SSZ)
- **Year** and **Month/Day** (separated for media server parsing)
- **Source identifier** ("YouTube")

### File Location:
- Created in the same directory as the downloaded video
- Same base filename as the video (e.g., `Video Title [ABC123].nfo`)
- Automatically generated from the `.info.json` file created by yt-dlp

### Benefits:
- **Plex/Kodi Compatibility**: Media servers automatically read and display metadata
- **Organized Library**: Proper sorting by date, channel, and title
- **Searchable Content**: Descriptions and metadata become searchable in your media library
- **Automatic Thumbnails**: Media servers can use the embedded or separate thumbnail

## ⚠️ Handled Errors

The script automatically handles the following error types:

### Temporary (retry with delay)
- DNS resolution failures (30-second pause, wait for recovery)
- HTTP 403 (access/cookie issues) - 10-minute pause
- HTTP 400 (outdated yt-dlp version)
- Connection timeouts (30-second pause)
- Network errors (60-second pause)
- Bot detection (5-minute pause)
- Age-restricted content (retry with cookies)

### Rate Limiting (long pauses)
- YouTube rate limit (1-hour pause)
- HTTP 429 (30-minute pause)

### Irreversible (skip without retry)
- HTTP 404/410 (video deleted)
- Private videos / Members-only
- Geo-blocking
- Copyright takedown
- Payment required
- Scheduled premieres
- Video unavailable

### Critical (script termination/restart)
- Disk full
- No folder access permissions
- ffmpeg not found
- Command parameter errors (exit code 2)

## 🔧 Troubleshooting

### "yt-dlp not found" Error

**Cause:** yt-dlp is not installed or not in PATH

**Solution:**
```powershell
# Verify installation
where yt-dlp

# Reinstall if needed
pip install -U yt-dlp
```

### "ffmpeg not found" Error

**Cause:** ffmpeg is not installed or not in PATH

**Solution:**
```powershell
# Install via winget
winget install ffmpeg

# Restart PowerShell to reload PATH
# Verify installation
ffmpeg -version
```

### DNS Resolution Errors

**Cause:** Internet connection issues or DNS server problems

**Solution:**
- Script automatically pauses and waits for DNS recovery (up to 10 minutes)
- Check your internet connection
- Try flushing DNS: `ipconfig /flushdns`
- Consider changing DNS servers to Google (8.8.8.8) or Cloudflare (1.1.1.1)

### Rate Limit Errors (HTTP 429)

**Cause:** Too many requests to YouTube

**Solution:**
- Script automatically pauses for 30 minutes
- Increase delays in configuration: modify `--sleep-interval` and `--max-sleep-interval`
- Use cookies from an authorized browser account

### "HTTP Error 403: Forbidden"

**Cause:** Access denied (often for age-restricted videos)

**Solution:**
- Ensure cookies are properly exported from Firefox
- Log into YouTube in Firefox before running the script
- Check that `--cookies-from-browser firefox` is working

### Script Hangs on a Video

**Cause:** Network issues or YouTube throttling

**Solution:**
- Script has built-in 60-minute timeout per video
- If it hangs repeatedly, check your internet connection stability
- The single concurrent fragment (--concurrent-fragments 1) is already optimized for unstable connections

### "No video formats available"

**Cause:** Video is deleted, private, or geo-blocked

**Solution:**
- Script automatically skips these videos
- Check `failed_links.txt` for list of failed URLs
- For geo-blocked videos, consider using a VPN

### NFO Files Not Generated

**Cause:** .info.json files missing or corrupted

**Solution:**
- Ensure `--write-info-json` is in the yt-dlp command (it is by default)
- Check that video downloads complete successfully
- Verify disk space is available

## ❓ FAQ

**Q: Can I download age-restricted videos?**  
A: Yes, the script uses cookies from Firefox via `--cookies-from-browser firefox`. Make sure you're logged into YouTube in Firefox before running the script.

**Q: How do I resume interrupted downloads?**  
A: Just re-run the script. It automatically skips downloaded videos via `download_archive.txt`. The script also has auto-restart capability for crashes.

**Q: What video quality does the script download?**  
A: Automatically selects the best available MP4 format: `bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best`. This typically gives 1080p or higher when available.

**Q: How much disk space do I need?**  
A: Full HD (1080p) videos typically range from 500 MB to 2 GB per video. Ensure you have sufficient free space for your download list plus extra for logs and metadata files.

**Q: Can I download entire playlists?**  
A: Yes, just paste the playlist URL in `links.txt`. yt-dlp will automatically expand it to individual video URLs.

**Q: Why does the script pause for an hour sometimes?**  
A: When YouTube rate limiting is detected, the script automatically pauses for 1 hour to avoid account blocking.

**Q: Can I change the browser for cookies?**  
A: Yes, modify the `--cookies-from-browser` parameter in the cmd array. Supported: firefox, chrome, chromium, edge, opera, brave, safari.

**Q: What are .nfo files and do I need them?**  
A: .nfo files are metadata files for media servers like Plex and Kodi. They're automatically generated and help organize your video library. You can delete them if not using a media server.

**Q: How does DNS recovery work?**  
A: When DNS errors are detected, the script pauses, checks DNS availability every 60 seconds, and resumes automatically when DNS is restored (up to 10 minutes wait).

**Q: Can I run multiple instances simultaneously?**  
A: Not recommended, as both instances would write to the same log and archive files, causing conflicts. Use separate directories for parallel downloads.

**Q: How do I update yt-dlp?**  
A: Run `pip install -U yt-dlp` regularly. YouTube frequently changes its API, so keeping yt-dlp updated is important for reliability.

## 📌 Additional Information

- **Account security**: Use moderate delays between videos to avoid YouTube account blocking
- **Disk space**: Ensure sufficient free space (Full HD video takes ~500 MB - 2 GB)
- **Age restrictions**: For 18+ videos, cookies from a browser with an authorized YouTube account are required
- **Updates**: Regularly update yt-dlp: `pip install -U yt-dlp`
- **DNS issues**: The script is resilient to temporary DNS failures but may need manual intervention for prolonged outages
- **Logs**: Check `download.log` for detailed error information if downloads fail
- **Thumbnails**: Separate JPG thumbnails are saved alongside videos for media server use

## 📄 License

The script is distributed freely. Use at your discretion.

## 🔗 Useful Links

- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp#readme)
- [Python Downloads](https://www.python.org/downloads/)
- [ffmpeg Downloads](https://ffmpeg.org/download.html)
- [Colorama (colored output)](https://pypi.org/project/colorama/)
```

## README_RU.md

```markdown
# yt-download

**Версия:** 3.0 | **Последнее обновление:** Февраль 2026

[![en](https://img.shields.io/badge/lang-en-red.svg)](README.md)
[![ru](https://img.shields.io/badge/lang-ru-blue.svg)](README_RU.md)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Free-green.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)]()
[![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-red.svg)](https://github.com/yt-dlp/yt-dlp)

*[Читать на английском](README.md)*

---

**Автоматизированный скрипт загрузчик видео с YouTube (yt-dlp) с интеллектуальной обработкой ошибок, восстановлением DNS, автоматическим перезапуском, генерацией NFO для Plex/Kodi и детальным логированием для массовых загрузок.**

## ✨ Возможности

- 🧠 **Интеллектуальная обработка ошибок** — 20+ типов ошибок, классифицированных по категориям (пропуск, повтор, пауза, критические)
- 🌐 **Система восстановления DNS** — Автоматическое обнаружение и ожидание восстановления DNS
- 🔄 **Автоматический перезапуск при критических ошибках** — Скрипт автоматически перезапускается после сбоев
- 📁 **Генерация NFO файлов** — Создает .nfo файлы для Plex/Kodi с метаданными из .info.json
- 📊 **Детальное логирование** — Ротация логов при достижении 10 МБ (хранится 5 резервных копий)
- 🎯 **Поддержка возобновления** — Продолжение с места остановки через архив загрузок
- 🍪 **Поддержка cookies** — Доступ к контенту с возрастными ограничениями через cookies Firefox
- 🎨 **Цветной вывод** — Прогресс в реальном времени с цветовой индикацией статуса
- ⏱️ **Адаптивные задержки** — Интервалы 5-60 секунд для избежания блокировок
- 📦 **Оптимизация MP4** — Автоматическое встраивание метаданных и миниатюр
- 🔁 **Определение rate limit** — Автоматические паузы от 30 секунд до 1 часа
- 🛡️ **Стабильное соединение** — Оптимизировано для нестабильных сетей (1 параллельный фрагмент)

## 📋 Содержание

- [Назначение](#назначение)
- [Быстрый старт](#-быстрый-старт)
- [Основные возможности](#основные-возможности)
- [Системные требования](#системные-требования)
- [Установка зависимостей](#установка-зависимостей)
- [Использование](#-использование)
- [Структура файлов](#-структура-файлов)
- [Настройка скрипта](#️-настройка-скрипта)
- [Логика работы](#-логика-работы)
- [Обрабатываемые ошибки](#️-обрабатываемые-ошибки)
- [Генерация NFO файлов](#-генерация-nfo-файлов)
- [Решение проблем](#-решение-проблем)
- [FAQ](#-faq)
- [Дополнительная информация](#-дополнительная-информация)
- [Лицензия](#-лицензия)
- [Полезные ссылки](#-полезные-ссылки)

## Назначение

Скрипт предназначен для надежной загрузки больших коллекций видео (сотни и тысячи файлов, включая плейлисты) в режиме «запустил и забыл». Автоматически обрабатывает типичные проблемы: сбои DNS, rate limit YouTube, сетевые ошибки, недоступные видео, с возможностью возобновления с места остановки. Включает генерацию NFO для медиасерверов и автоматический перезапуск при критических ошибках.

## ⚡ Быстрый старт

```powershell
# 1. Установка зависимостей
pip install -U yt-dlp colorama
winget install ffmpeg

# 2. Создайте links.txt со ссылками на YouTube
echo https://www.youtube.com/watch?v=dQw4w9WgXcQ > links.txt

# 3. Запустите скрипт
python yt-download3_RU.py
```

Вот и всё! Скрипт автоматически обработает всё с интеллектуальным восстановлением после ошибок и мониторингом DNS.

## Основные возможности

### Интеллектуальная обработка ошибок
- Классификация **20+ типов ошибок** на категории: skip (пропустить), retry (повторить), pause (пауза), fatal (критические)
- Автоматическое определение **сбоев DNS** с ожиданием восстановления
- Обработка HTTP 403/429/400/404/410, bot detection, geo-блокировки, copyright, приватных видео
- Адаптивные паузы в зависимости от типа ошибки (от 30 секунд до 1 часа)

### Система восстановления DNS
- Автоматическое обнаружение ошибок разрешения DNS
- Умное ожидание восстановления DNS (до 10 минут)
- Отслеживание последовательных ошибок DNS для предотвращения бесконечных циклов
- Проверка доступности DNS перед запуском скрипта

### Механизм автоматического перезапуска
- Автоматический перезапуск при критических ошибках (до 3 последовательных сбоев)
- Корректная обработка сетевых прерываний
- Возобновление с точки прерывания

### Интеграция с медиасерверами
- Автоматическая генерация **.nfo файлов** для Plex/Kodi из .info.json
- Извлечение метаданных: название, загрузчик, описание, дата загрузки
- Совместимый формат с требованиями медиасерверов

### Система повторных попыток
- До **3 попыток** на каждое видео с прогрессивными задержками
- Автоматический пропуск необратимых ошибок (удаленные/платные/приватные видео)
- Встроенная защита от зависания (таймаут **60 минут** на видео)

### Оптимизация загрузки
- Использование cookies из Firefox для доступа к видео с возрастными ограничениями
- **Стабильная однопоточная загрузка** (1 поток) для нестабильных соединений
- Адаптивные задержки **5-60 секунд** между видео для избежания блокировок
- Автоматическое встраивание метаданных и миниатюр в MP4
- Отдельное сохранение миниатюр как JPG файлов

### Логирование и мониторинг
- Единый лог-файл `download.log` с временными метками всех событий
- **Автоматическая ротация логов** при достижении 10 МБ (хранится 5 резервных копий)
- Цветной консольный вывод с прогресс-баром загрузки (через colorama)
- Детальная статистика: успешно/пропущено/ошибки, общее и среднее время

### Архивирование и возобновление
- Использует встроенный механизм yt-dlp для отслеживания скачанных видео по ID
- Автоматический **пропуск уже загруженных** файлов при перезапуске
- Сохранение списка неудавшихся загрузок в `failed_links.txt` для повторной попытки

## Системные требования

### Обязательные компоненты

- **Windows**: 10/11 или Windows Server 2016+
- **Python**: 3.8 или выше → [Скачать Python](https://www.python.org/downloads/)
- **PowerShell**: 5.1 или выше (встроен в Windows)
- **yt-dlp**: последняя версия → [GitHub yt-dlp](https://github.com/yt-dlp/yt-dlp)
- **ffmpeg**: для объединения видео/аудио форматов → [Скачать ffmpeg](https://ffmpeg.org/download.html)

### Установка зависимостей

#### Установка yt-dlp и Python-библиотек

```powershell
# Установка yt-dlp
pip install -U yt-dlp

# Установка colorama для цветного вывода (опционально, но рекомендуется)
pip install colorama
```

#### Установка ffmpeg

Существует несколько способов установки ffmpeg в PowerShell на Windows.

##### Способ 1: Через Winget (рекомендуется)

Winget встроен в Windows 10/11, поэтому это самый простой способ:

```powershell
winget install ffmpeg
```

##### Способ 2: Через Chocolatey

Если у вас установлен Chocolatey, выполните в PowerShell с правами администратора:

```powershell
choco install ffmpeg
```

##### Способ 3: Через Scoop

Scoop устанавливает программы в пользовательскую директорию без засорения системных папок:

```powershell
scoop install ffmpeg
```

##### Способ 4: Ручная установка

Если предпочитаете больший контроль над процессом установки:

1. Откройте PowerShell с правами администратора

2. Скачайте и установите ffmpeg:

```powershell
# Скачивание ffmpeg
Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile "ffmpeg.zip"

# Распаковка в C:\
Expand-Archive -Path "ffmpeg.zip" -DestinationPath "C:\"

# Переименование папки
$ffmpegFolder = Get-ChildItem -Path "C:\" -Filter "ffmpeg-*" -Directory
Rename-Item -Path $ffmpegFolder.FullName -NewName "ffmpeg"
```

3. Добавьте ffmpeg в PATH:

```powershell
$envPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
[Environment]::SetEnvironmentVariable("PATH", $envPath + ";C:\ffmpeg\bin", "Machine")
```

4. Проверьте установку, открыв новый терминал:

```powershell
ffmpeg -version
```

После установки станут доступны команды: `ffmpeg`, `ffplay`, `ffprobe`.

## 🚀 Использование

### 1. Подготовка

Создайте файл `links.txt` в папке со скриптом, добавьте по одному YouTube URL на строку:

```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/watch?v=9bZkp7q19f0
https://www.youtube.com/watch?v=h4Bq69HfR0Y&list=RDh4Bq69HfR0Y&start_radio=1&pp=ygUMa2VybWl0IGRhbmNloAcB0gcJCXwKAYcqIYzv
```

### 2. Запуск

```powershell
python yt-download3_RU.py
```

### 3. Мониторинг

Скрипт автоматически обработает все ссылки с обработкой ошибок. Прогресс отображается в консоли с цветной подсветкой:
- 🟢 Зеленый — успешная загрузка
- 🔵 Голубой — уже скачано ранее
- 🟡 Желтый — предупреждения и повторные попытки
- 🔴 Красный — ошибки
- 🟣 Фиолетовый — процесс объединения
- 🌐 Бирюзовый — процесс восстановления DNS

### 4. Прерывание и возобновление

При необходимости прервите скрипт комбинацией **Ctrl+C** — прогресс сохранится в `download_archive.txt`, и можно продолжить позже с того же места. Скрипт также имеет функцию автоматического перезапуска при критических ошибках.

## 📁 Структура файлов

После запуска скрипт создаст следующие файлы:

| Файл | Описание |
|------|----------|
| `download.log` | Основной лог с временными метками всех событий и ошибок |
| `download.log.1` - `.5` | Резервные копии логов (создаются при ротации) |
| `download_archive.txt` | Служебный файл yt-dlp с ID успешно скачанных видео |
| `failed_links.txt` | Список URL неудавшихся загрузок для повторной попытки |
| `*.mp4` | Скачанные видеофайлы в формате `Название [ID].mp4` |
| `*.info.json` | Файлы метаданных с информацией о видео |
| `*.nfo` | Файлы метаданных для медиасерверов Plex/Kodi |
| `*.jpg` | Изображения миниатюр в формате JPG |

## ⚙️ Настройка скрипта

### Параметры авторотации логов

В функции `setup_logger()`:

```python
logger = setup_logger(
    log_file, 
    max_bytes=10*1024*1024,  # Максимальный размер лога в байтах (по умолчанию 10 МБ)
    backup_count=5           # Количество резервных копий (по умолчанию 5)
)
```

**Настройка размера и количества логов:**
- `max_bytes` — размер файла, при котором происходит ротация (например, `20*1024*1024` для 20 МБ)
- `backup_count` — количество сохраняемых старых логов (например, `3` для 3 копий)

### Параметры повторных попыток

В функции `download_youtube_videos()`:

```python
max_attempts = 3  # Количество попыток на видео (по умолчанию 3)
```

### Параметры таймаутов

В цикле загрузки:

```python
timeout_seconds = 3600  # Таймаут на одно видео в секундах (по умолчанию 3600 = 60 минут)
```

### Параметры задержек yt-dlp

В массиве `cmd`:

```python
'--sleep-requests', '5',      # Задержка между API-запросами (секунды)
'--sleep-interval', '20',     # Минимальная задержка между видео (секунды)
'--max-sleep-interval', '60', # Максимальная задержка между видео (секунды)
'--socket-timeout', '60',     # Таймаут сокета (секунды)
```

**Рекомендации по настройке задержек:**
- Для нестабильных соединений: `20-60` секунд (текущие значения)
- При частых rate limit: увеличьте до `30-120` секунд

### Параметры оптимизации загрузки

```python
'--concurrent-fragments', '1',  # Количество параллельных потоков (1 для стабильности)
'--buffer-size', '16K',         # Размер буфера (16K оптимален для большинства случаев)
'--fragment-retries', '15',     # Попытки повтора для фрагментов
'--retries', '15',              # Общие попытки повтора
```

### Формат имен файлов

```python
'--output', '%(title).200s [%(id)s].%(ext)s',  # Шаблон имени файла
```

**Доступные переменные:**
- `%(title)s` — название видео (обрезается до 200 символов)
- `%(id)s` — ID видео
- `%(uploader)s` — автор канала
- `%(upload_date)s` — дата загрузки

Полный список: [yt-dlp Output Template](https://github.com/yt-dlp/yt-dlp#output-template)

### Браузер для экспорта cookies

```python
'--cookies-from-browser', 'firefox',  # Браузер для cookies (только firefox в этой конфигурации)
```

## 🔍 Логика работы

1. ✅ **Инициализация**: Проверяет yt-dlp, ffmpeg и доступность DNS
2. 📄 **Обработка ссылок**: Читает файл `links.txt` (игнорирует закомментированные строки с `#`)
3. 🌐 **Мониторинг DNS**: Постоянно проверяет разрешение DNS в течение процесса
4. 🎬 **Загрузка видео**: Для каждого видео запускает yt-dlp с оптимизированными параметрами
5. 👁️ **Мониторинг в реальном времени**: Отслеживает вывод, распознает и классифицирует ошибки
6. 🔄 **Обработка ошибок**: При ошибке принимает решение: повторить, пропустить, сделать паузу или ждать DNS
7. 📁 **Генерация NFO**: Создает .nfo файлы для медиасерверов после успешной загрузки
8. 📝 **Логирование**: Записывает все события с временными метками в `download.log` (с авторотацией)
9. 💾 **Архивирование**: Сохраняет ID успешно скачанных видео в `download_archive.txt`
10. 🔁 **Автоперезапуск**: Автоматически перезапускается при критических ошибках (макс. 3 попытки)
11. 📊 **Статистика**: Выводит детальную статистику и список неудавшихся загрузок

### Процесс восстановления DNS

1. **Обнаружение**: Скрипт отслеживает ошибки "failed to resolve" или "getaddrinfo failed"
2. **Подсчет**: Отслеживает последовательные ошибки DNS (макс. 20 перед критическим действием)
3. **Попытка восстановления**: Делает паузу и ждет восстановления DNS (до 10 минут)
4. **Возобновление**: Продолжает загрузку после восстановления DNS
5. **Резервный вариант**: Если DNS не восстановлен, скрипт можно перезапустить вручную

### Генерация NFO файлов

После каждой успешной загрузки скрипт:
1. Находит файл `.info.json`, созданный yt-dlp
2. Извлекает метаданные: название, ID видео, загрузчик, описание, дата загрузки
3. Создает файл `.nfo` со структурированной информацией для Plex/Kodi
4. Сохраняет его рядом с видеофайлом с тем же базовым именем

## 📁 Генерация NFO файлов

Скрипт автоматически генерирует `.nfo` файлы, совместимые с Plex, Kodi и другими медиасерверами. Эти файлы содержат структурированные метаданные, которые помогают медиаорганизаторам правильно каталогизировать ваши видео.

### Что содержится в .nfo файле:
- **Название видео**
- **Имя загрузчика/канала**
- **YouTube ID видео**
- **Описание видео**
- **Дата загрузки** (в формате ГГГГ-ММ-ДД ЧЧ:ММ:ССZ)
- **Год** и **Месяц/День** (разделены для парсинга медиасервером)
- **Идентификатор источника** ("YouTube")

### Расположение файлов:
- Создаются в той же директории, что и скачанное видео
- То же базовое имя файла, что и у видео (например, `Название видео [ABC123].nfo`)
- Автоматически генерируются из файла `.info.json`, созданного yt-dlp

### Преимущества:
- **Совместимость с Plex/Kodi**: Медиасерверы автоматически читают и отображают метаданные
- **Организованная библиотека**: Правильная сортировка по дате, каналу и названию
- **Поисковый контент**: Описания и метаданные становятся доступными для поиска в медиабиблиотеке
- **Автоматические миниатюры**: Медиасерверы могут использовать встроенные или отдельные миниатюры

## ⚠️ Обрабатываемые ошибки

Скрипт автоматически обрабатывает следующие типы ошибок:

### Временные (повтор с задержкой)
- Ошибки разрешения DNS (пауза 30 секунд, ожидание восстановления)
- HTTP 403 (проблемы с доступом/cookies) - пауза 10 минут
- HTTP 400 (устаревшая версия yt-dlp)
- Таймауты соединения (пауза 30 секунд)
- Сетевые ошибки (пауза 60 секунд)
- Bot detection (пауза 5 минут)
- Контент с возрастными ограничениями (повтор с cookies)

### Rate Limiting (длительные паузы)
- YouTube rate limit (пауза 1 час)
- HTTP 429 (пауза 30 минут)

### Необратимые (пропуск без повтора)
- HTTP 404/410 (видео удалено)
- Приватные видео / Members-only
- Гео-блокировка
- Copyright takedown
- Требуется оплата
- Запланированные премьеры
- Видео недоступно

### Критические (остановка/перезапуск скрипта)
- Диск заполнен
- Нет прав доступа к папке
- ffmpeg не найден
- Ошибки параметров команды (код выхода 2)

## 🔧 Решение проблем

### Ошибка "yt-dlp not found"

**Причина:** yt-dlp не установлен или отсутствует в PATH

**Решение:**
```powershell
# Проверьте установку
where yt-dlp

# Переустановите при необходимости
pip install -U yt-dlp
```

### Ошибка "ffmpeg not found"

**Причина:** ffmpeg не установлен или отсутствует в PATH

**Решение:**
```powershell
# Установите через winget
winget install ffmpeg

# Перезапустите PowerShell для обновления PATH
# Проверьте установку
ffmpeg -version
```

### Ошибки разрешения DNS

**Причина:** Проблемы с интернет-соединением или DNS серверами

**Решение:**
- Скрипт автоматически делает паузу и ждет восстановления DNS (до 10 минут)
- Проверьте интернет-соединение
- Попробуйте очистить DNS: `ipconfig /flushdns`
- Рассмотрите смену DNS серверов на Google (8.8.8.8) или Cloudflare (1.1.1.1)

### Ошибки Rate Limit (HTTP 429)

**Причина:** Слишком много запросов к YouTube

**Решение:**
- Скрипт автоматически делает паузу на 30 минут
- Увеличьте задержки в конфигурации: измените `--sleep-interval` и `--max-sleep-interval`
- Используйте cookies из авторизованного аккаунта браузера

### "HTTP Error 403: Forbidden"

**Причина:** Доступ запрещен (часто для видео с возрастными ограничениями)

**Решение:**
- Убедитесь, что cookies правильно экспортированы из Firefox
- Войдите в YouTube в Firefox перед запуском скрипта
- Проверьте работу `--cookies-from-browser firefox`

### Скрипт зависает на видео

**Причина:** Проблемы с сетью или ограничение YouTube

**Решение:**
- У скрипта встроенный таймаут 60 минут на видео
- Если зависает повторно, проверьте стабильность интернет-соединения
- Один параллельный фрагмент (--concurrent-fragments 1) уже оптимизирован для нестабильных соединений

### "No video formats available"

**Причина:** Видео удалено, приватное или заблокировано в вашем регионе

**Решение:**
- Скрипт автоматически пропускает такие видео
- Проверьте `failed_links.txt` для списка неудавшихся URL
- Для гео-блокированных видео рассмотрите использование VPN

### NFO файлы не создаются

**Причина:** Отсутствуют или повреждены .info.json файлы

**Решение:**
- Убедитесь, что `--write-info-json` есть в команде yt-dlp (есть по умолчанию)
- Проверьте, что загрузки видео завершаются успешно
- Убедитесь, что есть свободное место на диске

## ❓ FAQ

**В: Могу ли я скачивать видео с возрастными ограничениями?**  
О: Да, скрипт использует cookies из Firefox через `--cookies-from-browser firefox`. Убедитесь, что вы вошли в YouTube в Firefox перед запуском скрипта.

**В: Как возобновить прерванные загрузки?**  
О: Просто перезапустите скрипт. Он автоматически пропустит уже скачанные видео через `download_archive.txt`. Скрипт также имеет функцию автоматического перезапуска при сбоях.

**В: Какое качество видео скачивает скрипт?**  
О: Автоматически выбирается лучший доступный формат MP4: `bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best`. Обычно это дает 1080p или выше, если доступно.

**В: Сколько места на диске мне нужно?**  
О: Видео Full HD (1080p) обычно занимают от 500 МБ до 2 ГБ на видео. Убедитесь, что у вас достаточно свободного места для списка загрузок плюс дополнительно для логов и файлов метаданных.

**В: Могу ли я скачивать целые плейлисты?**  
О: Да, просто вставьте URL плейлиста в `links.txt`. yt-dlp автоматически развернет его в отдельные URL видео.

**В: Почему скрипт делает паузу на час иногда?**  
О: Когда обнаруживается ограничение YouTube (rate limit), скрипт автоматически делает паузу на 1 час, чтобы избежать блокировки аккаунта.

**В: Могу ли я изменить браузер для cookies?**  
О: Да, измените параметр `--cookies-from-browser` в массиве cmd. Поддерживаются: firefox, chrome, chromium, edge, opera, brave, safari.

**В: Что такое .nfo файлы и нужны ли они мне?**  
О: .nfo файлы — это файлы метаданных для медиасерверов типа Plex и Kodi. Они автоматически генерируются и помогают организовать вашу видеобиблиотеку. Вы можете удалить их, если не используете медиасервер.

**В: Как работает восстановление DNS?**  
О: При обнаружении ошибок DNS скрипт делает паузу, проверяет доступность DNS каждые 60 секунд и автоматически возобновляет работу после восстановления DNS (ожидание до 10 минут).

**В: Могу ли я запустить несколько экземпляров одновременно?**  
О: Не рекомендуется, так как оба экземпляра будут писать в одни и те же лог-файлы и архивные файлы, вызывая конфликты. Используйте отдельные директории для параллельных загрузок.

**В: Как обновить yt-dlp?**  
О: Регулярно выполняйте `pip install -U yt-dlp`. YouTube часто меняет свой API, поэтому поддержание yt-dlp в актуальном состоянии важно для надежности.

## 📌 Дополнительная информация

- **Безопасность аккаунта**: Используйте умеренные задержки между видео, чтобы избежать блокировки аккаунта YouTube
- **Место на диске**: Убедитесь в наличии достаточного свободного места (видео в Full HD занимает ~500 МБ - 2 ГБ)
- **Возрастные ограничения**: Для видео 18+ требуются cookies из браузера с авторизованным аккаунтом YouTube
- **Обновления**: Регулярно обновляйте yt-dlp: `pip install -U yt-dlp`
- **Проблемы с DNS**: Скрипт устойчив к временным сбоям DNS, но может потребовать ручного вмешательства при длительных простоях
- **Логи**: Проверяйте `download.log` для детальной информации об ошибках, если загрузки не удаются
- **Миниатюры**: Отдельные JPG миниатюры сохраняются рядом с видео для использования медиасерверами

## 📄 Лицензия

Скрипт распространяется свободно. Используйте на свое усмотрение.

## 🔗 Полезные ссылки

- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp#readme)
- [Python Downloads](https://www.python.org/downloads/)
- [ffmpeg Downloads](https://ffmpeg.org/download.html)
- [Colorama (цветной вывод)](https://pypi.org/project/colorama/)
```

Оба файла теперь полностью соответствуют функционалу скрипта `yt-download3_RU.py`, включая все новые функции: генерацию NFO файлов, восстановление DNS, автоматический перезапуск, и другие улучшения. Тексты идентичны по структуре и содержанию, только на разных языках.
