# yt-download

**Version:** 2.0 | **Last Updated:** January 2026

[![en](https://img.shields.io/badge/lang-en-red.svg)](README.md)
[![ru](https://img.shields.io/badge/lang-ru-blue.svg)](README_RU.md)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Free-green.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)]()
[![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-red.svg)](https://github.com/yt-dlp/yt-dlp)

*[Читать на русском](README_RU.md)*

---

**Automated script YouTube video downloader (yt-dlp) with intelligent error handling, retry system, and detailed logging for mass downloads (thousands of single files or playlists).**

**Автоматизированный скрипт загрузчик видео с YouTube (yt-dlp) с интеллектуальной обработкой ошибок, системой повторных попыток и детальным логированием для массовых загрузок (тысячи одиночных файлов или плейлистов).**

## ✨ Features

- 🧠 **Intelligent Error Handling** — 15+ error types classified into categories (skip, retry, pause, fatal)
- 🔄 **Automatic Retry System** — Up to 3 attempts per video with progressive delays
- 📊 **Detailed Logging** — Rotating logs with 10MB auto-rotation (keeps 5 backups)
- ⚡ **Parallel Downloads** — 5 concurrent fragments for faster speeds
- 🎯 **Resume Support** — Continue from where you left off via archive tracking
- 🍪 **Cookie Support** — Access age-restricted content with browser cookies
- 🎨 **Colored Output** — Real-time progress with color-coded status
- ⏱️ **Adaptive Delays** — 15-45 second intervals to avoid rate limits
- 📦 **MP4 Optimization** — Automatic metadata and thumbnail embedding
- 🔁 **Rate Limit Detection** — Automatic 1-hour pause on YouTube throttling

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
- [Troubleshooting](#-troubleshooting)
- [FAQ](#-faq)
- [Additional Information](#-additional-information)
- [License](#-license)
- [Useful Links](#-useful-links)

## Purpose

The script is designed for reliable downloading of large video collections (hundreds and thousands of files, including playlists) in a "set and forget" mode. Automatically handles typical issues: YouTube rate limits, network errors, unavailable videos, with the ability to resume from where it left off. It's simply a scripted wrapper around yt-dlp, written for personal convenience.

## ⚡ Quick Start

```powershell
# 1. Install dependencies
pip install -U yt-dlp colorama
winget install ffmpeg

# 2. Create links.txt with YouTube URLs
echo https://www.youtube.com/watch?v=dQw4w9WgXcQ > links.txt

# 3. Run the script
python yt-download2.py
```

That's it! The script will handle everything automatically with intelligent error recovery.

## Key Features

### Intelligent Error Handling
- Classification of **15+ error types** into categories: skip, retry, pause, fatal
- Automatic detection of **YouTube rate limit** with 1-hour pause
- Handling of HTTP 403/429/400/404/410, bot detection, geo-blocks, copyright, private videos
- Adaptive pauses depending on error type (from 30 seconds to 1 hour)

### Retry System
- Up to **3 attempts** per video with progressive delays
- Automatic skipping of irreversible errors (deleted/paid/private videos)
- Built-in hang protection (timeout **10 minutes** per video)

### Download Optimization
- Using cookies from Firefox (!) to access age-restricted videos
- **Parallel fragment downloading** (5 threads) for speed
- Adaptive delays of **15-45 seconds** between videos to avoid blocks
- Automatic embedding of metadata and thumbnails into MP4

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

# Install colorama for colored output (optional)
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
python yt-download2.py
```

### 3. Monitoring

The script will automatically process all links with error handling. Progress is displayed in the console with color highlighting:
- 🟢 Green — successful download
- 🔵 Blue — already downloaded previously
- 🟡 Yellow — warnings and retries
- 🔴 Red — errors

### 4. Interruption and Resuming

If necessary, interrupt the script with **Ctrl+C** — progress will be saved in `download_archive.txt`, and you can continue later from the same place.

## 📁 File Structure

After running, the script will create the following files:

| File | Description |
|------|----------|
| `download.log` | Main log with timestamps of all events and errors |
| `download.log.1` - `.5` | Backup log copies (created during rotation) |
| `download_archive.txt` | yt-dlp service file with IDs of successfully downloaded videos |
| `failed_links.txt` | List of URLs of failed downloads for retry |
| `*.mp4` | Downloaded video files in format `Title [ID].mp4` |

## ⚙️ Script Configuration

### Log Auto-rotation Parameters

In the `setup_logger()` function (line ~30):

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

In the `download_youtube_videos()` function (line ~280):

```python
max_attempts = 3  # Number of attempts per video (default 3)
```

### Timeout Parameters

In the download loop (line ~330):

```python
timeout_seconds = 600  # Timeout per video in seconds (default 600 = 10 minutes)
```

### yt-dlp Delay Parameters

In the `cmd` array (line ~250):

```python
'--sleep-requests', '3',      # Delay between API requests (seconds)
'--sleep-interval', '15',     # Minimum delay between videos (seconds)
'--max-sleep-interval', '45', # Maximum delay between videos (seconds)
'--socket-timeout', '30',     # Socket timeout (seconds)
```

**Delay configuration recommendations:**
- For fast downloading of small playlists (<100 videos): `10-20` seconds
- For mass downloading (>1000 videos): `15-45` seconds (current values)
- With frequent rate limits: increase to `30-90` seconds

### Download Optimization Parameters

```python
'--concurrent-fragments', '5',  # Number of parallel threads (default 5)
'--buffer-size', '16K',         # Buffer size (16K optimal for most cases)
```

### Filename Format

```python
'--output', '%(title).200s [%(id)s].%(ext)s',  # Filename template
```

**Available variables:**
- `%(title)s` — video title
- `%(id)s` — video ID
- `%(uploader)s` — channel author
- `%(upload_date)s` — upload date

Full list: [yt-dlp Output Template](https://github.com/yt-dlp/yt-dlp#output-template)

### Browser for Cookie Export

```python
'--cookies-from-browser', 'firefox',  # Browser for cookies (firefox, chrome, edge, safari)
```

Available browsers: `firefox`, `chrome`, `chromium`, `edge`, `opera`, `brave`, `safari`

## 🔍 Operating Logic

1. ✅ Checks for presence of yt-dlp and ffmpeg in the system
2. 📄 Reads the `links.txt` file with URL list (ignores commented lines with `#`)
3. 🎬 For each video, launches yt-dlp with optimized parameters
4. 👁️ Monitors output in real-time, recognizes errors
5. 🔄 On error, classifies it and decides: retry, skip, or pause
6. 📝 Logs all events with timestamps in `download.log` (with auto-rotation)
7. 💾 Saves IDs of successfully downloaded videos in `download_archive.txt`
8. 📊 Upon completion, outputs detailed statistics and list of failed downloads

### ffmpeg's Role in the Download Process

**Why ffmpeg is critically important:**

YouTube delivers high-quality video (720p and higher) as **separate streams**: a video track without audio and an audio track without video. This is due to DASH (Dynamic Adaptive Streaming) technology, which allows adaptive quality selection based on connection speed.

**What ffmpeg does:**
1. **Download** — yt-dlp downloads two separate tracks (video VP9/H.264 + audio Opus/AAC)
2. **Merging** — ffmpeg multiplexes the streams into a single file without re-encoding (fast)
3. **Conversion** — converts to MP4 format with H.264 (video) + AAC (audio) codecs
4. **Metadata** — embeds title, author, description, and thumbnail directly into the file

**Result:** MP4 with H.264/AAC is a universal format with maximum compatibility:
- 📺 **Media servers**: Plex, Jellyfin, Emby, Kodi
- 📱 **Mobile devices**: iPhone, iPad, Android
- 🖥️ **Smart TV**: Samsung, LG, Sony, Android TV
- 🎮 **Game consoles**: PlayStation, Xbox
- 🎬 **Video players**: VLC, MPC-HC, PotPlayer, Windows Media Player

**Without ffmpeg:** yt-dlp can only download low-quality video (360p-480p) where audio and video are already merged, or separate streams in WebM/VP9 formats that don't play on many devices.

## ⚠️ Handled Errors

The script automatically handles the following error types:

### Temporary (retry)
- HTTP 403 (access/cookie issues)
- HTTP 400 (outdated yt-dlp version)
- Connection timeouts
- Network errors
- Bot detection (5-minute pause)

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

### Critical (script termination)
- Disk full
- No folder access rights
- ffmpeg not found

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

### Rate Limit Errors (HTTP 429)

**Cause:** Too many requests to YouTube

**Solution:**
- Script automatically pauses for 1 hour
- Increase delays in configuration: `--sleep-interval 30` and `--max-sleep-interval 90`
- Use cookies from an authorized browser account

### "HTTP Error 403: Forbidden"

**Cause:** Access denied (often for age-restricted videos)

**Solution:**
- Ensure cookies are properly exported from Firefox
- Log into YouTube in your browser before running the script
- Check that `--cookies-from-browser firefox` is in configuration

### Script Hangs on a Video

**Cause:** Network issues or YouTube throttling

**Solution:**
- Script has built-in 10-minute timeout per video
- If it hangs repeatedly, check your internet connection
- Try reducing `--concurrent-fragments` from 5 to 3

### "No video formats available"

**Cause:** Video is deleted, private, or geo-blocked

**Solution:**
- Script automatically skips these videos
- Check `failed_links.txt` for list of failed URLs
- For geo-blocked videos, consider using a VPN

## ❓ FAQ

**Q: Can I download age-restricted videos?**  
A: Yes, use cookies from an authorized browser account. The script is configured to use Firefox cookies by default via `--cookies-from-browser firefox`.

**Q: How do I resume interrupted downloads?**  
A: Just re-run the script. It automatically skips downloaded videos via `download_archive.txt`. Previously downloaded videos are tracked by their YouTube ID.

**Q: What video quality does the script download?**  
A: Automatically selects the best available quality (typically 1080p or higher if available). The format selection prioritizes H.264/AAC for maximum compatibility.

**Q: How much disk space do I need?**  
A: Full HD (1080p) videos typically range from 500 MB to 2 GB per video. Ensure you have sufficient free space for your download list.

**Q: Can I download entire playlists?**  
A: Yes, just paste the playlist URL in `links.txt`. yt-dlp will automatically expand it to individual video URLs.

**Q: Why does the script pause for an hour?**  
A: YouTube has imposed a rate limit. The script automatically detects this and waits 1 hour before resuming to avoid account blocking.

**Q: Can I change the output format?**  
A: Yes, modify the `--output` template in the script. See [yt-dlp Output Template](https://github.com/yt-dlp/yt-dlp#output-template) for available variables.

**Q: What happens if my computer crashes during download?**  
A: All successfully downloaded videos are recorded in `download_archive.txt`. Simply restart the script and it will continue from where it left off.

**Q: Can I run multiple instances simultaneously?**  
A: Not recommended, as both instances would write to the same log and archive files, causing conflicts. Use separate directories for parallel downloads.

**Q: How do I update yt-dlp?**  
A: Run `pip install -U yt-dlp` regularly. YouTube frequently changes its API, so keeping yt-dlp updated is important for reliability.

## 📌 Additional Information

- **Account security**: Use moderate delays between videos to avoid YouTube account blocking
- **Disk space**: Ensure sufficient free space (Full HD video takes ~500 MB - 2 GB)
- **Age restrictions**: For 18+ videos, cookies from a browser with an authorized YouTube account are required
- **Updates**: Regularly update yt-dlp: `pip install -U yt-dlp`

## 📄 License

The script is distributed freely. Use at your discretion.

## 🔗 Useful Links

- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp#readme)
- [Python Downloads](https://www.python.org/downloads/)
- [ffmpeg Downloads](https://ffmpeg.org/download.html)
