# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [5.4.1] - 2026-06-26

### Fixed

- `download_single_url()`: moved `cfg = load_config()` to top of function (was used before assignment).
- `get_playlist_info()`: added `cfg` and `script_dir` parameters; fixed `_COOKIE_ARGS` → `cookie_args` (was NameError).
- `generate_nfo_file()`: added XML escaping via `xml.sax.saxutils.escape` for title, uploader, description, video_id.
- `generate_nfo_file()`: added `<?xml version="1.0"?>` XML declaration header.
- `generate_nfo_file()`: changed `sorttitle` from `month_day` to `title` (standard for Kodi/Jellyfin).
- `classify_error()`: removed unused `error_keywords` parameter.

### Added

- `generate_nfo_file()` is now called after successful download, gated by `cfg["downloads"]["generate_nfo"]`.
- NFO files are only generated when a matching `.nfo` does not already exist (idempotent).

## [5.4.0] - 2026-06-21

### Added

- English version: `yt_download_en.py` — full English equivalent of the Russian script.
- Configuration via `config.toml` (optional, see config.example.toml).
- Cookies file support: `cookie_mode = "file"` with `--cookies cookies.txt` (configurable).
- Setup/doctor command: `--check` flag for dependency verification.
- Orphan media cleaner: integrated as subprocess menu option.
- Test suite: `tests/test_yt_download.py` covering pure functions (classify_error, format_time, is_playlist_url, read_links_file).

### Changed

- Renamed: `yt-download5.4_RU.py` → `yt_download_ru.py` (version removed from filename).
- Renamed: `yt-download5.4_EN.py` → `yt_download_en.py`.
- Renamed: `yt-media_cleaner.1.0_win_ru.py` → `yt_media_cleaner_ru.py`.
- Archive/failed/links files now tracked via `config.toml` paths.
- README updated: English default for `yt_download_en.py`, Russian for `yt_download_ru.py`.

### Fixed

- Rolling 24h spend now uses history delta instead of /auth/key.usage_daily (calendar-day counter).

## [5.1.0] - 2026-02-04

### Added

- Initial public release of `yt-download`.
- English and Russian versions: `yt-download5.1_EN.py`, `yt-download5.1_RU.py`.
- Intelligent error handling (20+ error types, categories: skip/retry/pause/fatal).
- DNS recovery system with automatic detection and waiting.
- Playlist support with subfolder creation and progress tracking.
- NFO file generation for Plex/Kodi.
- Rotating logs (10 MB, 5 backups).
- Colored output (colorama).
- Retry system (3 attempts per video, progressive delays).
- Download archive and resume support.
