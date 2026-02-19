## README.md (English)

```markdown
# yt-download

**Version:** 5.1 | **Last Updated:** 04 February 2026

[![en](https://img.shields.io/badge/lang-en-red.svg)](README.md)
[![ru](https://img.shields.io/badge/lang-ru-blue.svg)](README_RU.md)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Free-green.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)]()
[![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-red.svg)](https://github.com/yt-dlp/yt-dlp)

*[Read in Russian](README_RU.md)*

---

**Automated YouTube video downloader (yt-dlp) with intelligent error handling, DNS recovery, auto-restart, playlist progress tracking, NFO generation for Plex/Kodi, and detailed logging for mass downloads.**

## ✨ Features

- 🧠 **Intelligent Error Handling** — 20+ error types classified into categories (skip, retry, pause, fatal)
- 🌐 **DNS Recovery System** — Automatic detection and waiting for DNS restoration
- 🔄 **Auto-Restart on Critical Errors** — Script automatically restarts after failures
- 📋 **Playlist Support** — Automatic subfolder creation per playlist/channel with progress tracking
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

The script is designed for reliable downloading of large video collections (hundreds and thousands of files, including playlists) in a "set and forget" mode. It automatically handles typical issues: DNS failures, YouTube rate limits, network errors, unavailable videos, with the ability to resume from where it left off. Includes playlist progress tracking with automatic subfolder organization, NFO generation for media servers, and automatic restart on critical errors.

## ⚡ Quick Start

```powershell
# 1. Install dependencies
pip install -U yt-dlp colorama
winget install ffmpeg

# 2. Create links.txt with YouTube URLs
echo https://www.youtube.com/watch?v=dQw4w9WgXcQ > links.txt

# 3. Run the script
python yt-download5.1_EN.py
```

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

### Playlist Support
- Automatic detection of playlist and channel URLs
- Dedicated subfolder per playlist/channel: `downloads/<playlist_title>/`
- Progress tracking: shows total, downloaded, and remaining video counts
- Extended timeout of **120 minutes** for playlist processing

### Media Server Integration
- Automatic generation of **.nfo files** for Plex/Kodi from .info.json
- Metadata extraction: title, uploader, description, upload date
- Compatible format with media server requirements

### Retry System
- Up to **3 attempts** per video with progressive delays
- Automatic skipping of irreversible errors (deleted/paid/private videos)
- Built-in hang protection (timeout **60 minutes** per single video, **120 minutes** per playlist)

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
python yt-download5.1_EN.py
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
|------|-------------|
| `download.log` | Main log with timestamps of all events and errors |
| `download.log.1` - `.5` | Backup log copies (created during rotation) |
| `download_archive.txt` | yt-dlp service file with IDs of successfully downloaded videos |
| `failed_links.txt` | List of URLs of failed downloads for retry |
| `downloads/` | Main folder for all downloaded files |
| `downloads/*.mp4` | Single video files in format `Title [ID].mp4` |
| `downloads/<playlist>/` | Subfolder per playlist or channel |
| `downloads/<playlist>/*.mp4` | Playlist video files in format `Title [ID].mp4` |
| `*.info.json` | Metadata files with video information (alongside videos) |
| `*.nfo` | Media server metadata files for Plex/Kodi (alongside videos) |
| `*.jpg` | Thumbnail images in JPG format (alongside videos) |

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
timeout_seconds = 7200 if is_playlist else 3600  # 120 min for playlists, 60 min for single videos
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
'--retries', '15',              # General retry attempts
'--fragment-retries', '15',     # Fragment retry attempts
'--extractor-retries', '8',     # Extractor retry attempts
'--file-access-retries', '5',   # File access retry attempts
'--concurrent-fragments', '1',  # Number of parallel threads (1 for stability)
'--buffer-size', '16K',         # Buffer size (16K optimal for most cases)
```

### Filename Format

```python
# Playlists — saved to a dedicated subfolder:
'%(playlist_title,uploader,channel).100s/%(title).200s [%(id)s].%(ext)s'

# Single videos — saved directly to downloads/ root:
'%(title).200s [%(id)s].%(ext)s'
```

**Available variables:**
- `%(title)s` — video title (truncated to 200 characters)
- `%(id)s` — video ID
- `%(playlist_title)s` — playlist title (used for subfolder name)
- `%(uploader)s` — channel author
- `%(upload_date)s` — upload date

Full list: [yt-dlp Output Template](https://github.com/yt-dlp/yt-dlp#output-template)

### Browser for Cookie Export

```python
'--cookies-from-browser', 'firefox',  # Browser for cookies (firefox only in this config)
```

### Remote Components

```python
'--remote-components', 'ejs:github',  # Use remote extractor components from GitHub
```

## 🔍 Operating Logic

1. ✅ **Initialization**: Checks yt-dlp, ffmpeg, and DNS availability
2. 📄 **Link Processing**: Reads `links.txt` file (ignores commented lines with `#`)
3. 📋 **Playlist Check**: For playlist URLs, retrieves progress (total/downloaded/remaining videos)
4. 🌐 **DNS Monitoring**: Continuously checks DNS resolution throughout process
5. 🎬 **Video Download**: For each URL, launches yt-dlp with optimized parameters
6. 👁️ **Real-time Monitoring**: Tracks output, recognizes and classifies errors
7. 🔄 **Error Handling**: On error, decides: retry, skip, pause, or wait for DNS
8. 📁 **NFO Generation**: Creates .nfo files for media servers after successful download
9. 📝 **Logging**: Records all events with timestamps in `download.log` (with auto-rotation)
10. 💾 **Archiving**: Saves IDs of successfully downloaded videos in `download_archive.txt`
11. 🔁 **Auto-Restart**: Automatically restarts on critical errors (max 3 attempts)
12. 📊 **Statistics**: Outputs detailed stats and list of failed downloads

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
- Script has built-in timeout: 60 minutes per single video, 120 minutes per playlist
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
A: Automatically selects the best available quality using `-f bestvideo+bestaudio/best`, then remuxes to MP4. This typically gives 1080p or higher when available.

**Q: How much disk space do I need?**  
A: Full HD (1080p) videos typically range from 500 MB to 2 GB per video. Ensure you have sufficient free space for your download list plus extra for logs and metadata files.

**Q: Can I download entire playlists?**  
A: Yes, just paste the playlist URL in `links.txt`. The script automatically detects playlists, creates a dedicated subfolder, and tracks download progress.

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