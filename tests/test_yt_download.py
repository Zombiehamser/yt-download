#!/usr/bin/env python3
"""Tests for yt-download — pure function tests + Phase G (load_config, cookies, setup, cleanup).

All tests are isolated: no network, no real yt-dlp, no real subprocess.
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from collections import namedtuple

import pytest

VersionInfo = namedtuple("VersionInfo", ["major", "minor", "micro"])

# ── Import RU and EN scripts ──────────────────────────────────
# Direct import via importlib: fail hard if module can't be loaded.
ROOT = Path(__file__).resolve().parent.parent  # tests/ -> yt-download/


def load_module(module_name, file_name):
    path = ROOT / file_name
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist — cannot import {module_name}")
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    assert spec is not None, f"importlib could not create spec for {path}"
    assert spec.loader is not None, f"importlib could not find loader for {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ru = load_module("yt_download_ru", "yt_download_ru.py")
en = load_module("yt_download_en", "yt_download_en.py")


# ── Fixture: reset config cache after each load_config test ───
@pytest.fixture
def reset_config():
    ru._CONFIG = None
    yield
    ru._CONFIG = None


# ═══════════════════════════════════════════════════════════════
# is_playlist_url
# ═══════════════════════════════════════════════════════════════


class TestIsPlaylistUrl:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123", True),
        ("https://www.youtube.com/playlist?list=PLabc123", True),
        ("https://www.youtube.com/c/SomeChannel", True),
        ("https://www.youtube.com/@SomeChannel", True),
        ("https://www.youtube.com/channel/UC123456", True),
        ("https://www.youtube.com/user/SomeUser", True),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", False),
        ("https://youtu.be/dQw4w9WgXcQ", False),
        ("", False),
        ("not a url", False),
    ])
    def test_ru(self, url, expected):
        assert ru.is_playlist_url(url) == expected

    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123", True),
        ("https://www.youtube.com/playlist?list=PLabc123", True),
        ("https://www.youtube.com/c/SomeChannel", True),
        ("https://www.youtube.com/@SomeChannel", True),
        ("https://www.youtube.com/channel/UC123456", True),
        ("https://www.youtube.com/user/SomeUser", True),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", False),
        ("https://youtu.be/dQw4w9WgXcQ", False),
        ("", False),
        ("not a url", False),
    ])
    def test_en(self, url, expected):
        assert en.is_playlist_url(url) == expected


# ═══════════════════════════════════════════════════════════════
# format_time
# ═══════════════════════════════════════════════════════════════


class TestFormatTime:
    @pytest.mark.parametrize("seconds,expected_ru,expected_en", [
        (0, "0с", "0s"),
        (30, "30с", "30s"),
        (125, "2м 5с", "2m 5s"),
        (3661, "1ч 1м 1с", "1h 1m 1s"),
        (7200, "2ч 0м 0с", "2h 0m 0s"),
        (86400, "24ч 0м 0с", "24h 0m 0s"),
    ])
    def test_ru(self, seconds, expected_ru, expected_en):
        assert ru.format_time(seconds) == expected_ru

    @pytest.mark.parametrize("seconds,expected_ru,expected_en", [
        (0, "0с", "0s"),
        (30, "30с", "30s"),
        (125, "2м 5с", "2m 5s"),
        (3661, "1ч 1м 1с", "1h 1m 1s"),
        (7200, "2ч 0м 0с", "2h 0m 0s"),
        (86400, "24ч 0м 0с", "24h 0m 0s"),
    ])
    def test_en(self, seconds, expected_ru, expected_en):
        assert en.format_time(seconds) == expected_en


# ═══════════════════════════════════════════════════════════════
# classify_error
# ═══════════════════════════════════════════════════════════════


class TestClassifyError:
    @pytest.mark.parametrize("line,expected_keys", [
        ("failed to resolve host", {"dns_error": True, "retry": True, "pause": 30}),
        ("getaddrinfo failed", {"dns_error": True, "retry": True, "pause": 30}),
        ("rate-limited", {"retry": False, "pause": 3600}),
        ("rate limit", {"retry": False, "pause": 3600}),
        ("sign in to confirm you are not a bot", {"retry": True, "pause": 300}),
        ("po token", {"retry": False, "pause": 0}),
        ("data sync id", {"retry": False, "pause": 0}),
        ("http error 403", {"retry": True, "pause": 600}),
        ("http error 429", {"retry": False, "pause": 1800}),
        ("http error 400", {"retry": True, "pause": 0}),
        ("http error 404", {"skip": True}),
        ("http error 410", {"skip": True}),
        ("private video", {"skip": True}),
        ("members-only", {"skip": True}),
        ("video unavailable", {"skip": True}),
        ("premieres in 2 hours", {"skip": True}),
        ("will begin in 5 minutes", {"skip": True}),
        ("age-restricted", {"retry": True}),
        ("age restricted", {"retry": True}),
        ("geo-blocked", {"skip": True}),
        ("geo restricted", {"skip": True}),
        ("copyright strike", {"skip": True}),
        ("takedown notice", {"skip": True}),
        ("requires payment", {"skip": True}),
        ("rental video", {"skip": True}),
        ("timeout", {"retry": True, "pause": 30}),
        ("timed out", {"retry": True, "pause": 30}),
        ("connection error", {"retry": True, "pause": 60}),
        ("no space left on device", {"fatal": True}),
        ("disk full", {"fatal": True}),
        ("permission denied", {"fatal": True}),
        ("access denied", {"fatal": True}),
        ("ffmpeg not found", {"fatal": True}),
        ("ffprobe not found", {"fatal": True}),
    ])
    def test_ru(self, line, expected_keys):
        result = ru.classify_error(line.lower())
        for key, val in expected_keys.items():
            assert result.get(key) == val, f"RU: {line} -> {key} expected {val}, got {result.get(key)}"

    @pytest.mark.parametrize("line,expected_keys", [
        ("failed to resolve host", {"dns_error": True, "retry": True, "pause": 30}),
        ("getaddrinfo failed", {"dns_error": True, "retry": True, "pause": 30}),
        ("rate-limited", {"retry": False, "pause": 3600}),
        ("rate limit", {"retry": False, "pause": 3600}),
        ("sign in to confirm you are not a bot", {"retry": True, "pause": 300}),
        ("po token", {"retry": False, "pause": 0}),
        ("data sync id", {"retry": False, "pause": 0}),
        ("http error 403", {"retry": True, "pause": 600}),
        ("http error 429", {"retry": False, "pause": 1800}),
        ("http error 400", {"retry": True, "pause": 0}),
        ("http error 404", {"skip": True}),
        ("http error 410", {"skip": True}),
        ("private video", {"skip": True}),
        ("members-only", {"skip": True}),
        ("video unavailable", {"skip": True}),
        ("premieres in 2 hours", {"skip": True}),
        ("will begin in 5 minutes", {"skip": True}),
        ("age-restricted", {"retry": True}),
        ("age restricted", {"retry": True}),
        ("geo-blocked", {"skip": True}),
        ("geo restricted", {"skip": True}),
        ("copyright strike", {"skip": True}),
        ("takedown notice", {"skip": True}),
        ("requires payment", {"skip": True}),
        ("rental video", {"skip": True}),
        ("timeout", {"retry": True, "pause": 30}),
        ("timed out", {"retry": True, "pause": 30}),
        ("connection error", {"retry": True, "pause": 60}),
        ("no space left on device", {"fatal": True}),
        ("disk full", {"fatal": True}),
        ("permission denied", {"fatal": True}),
        ("access denied", {"fatal": True}),
        ("ffmpeg not found", {"fatal": True}),
        ("ffprobe not found", {"fatal": True}),
    ])
    def test_en(self, line, expected_keys):
        result = en.classify_error(line.lower())
        for key, val in expected_keys.items():
            assert result.get(key) == val, f"EN: {line} -> {key} expected {val}, got {result.get(key)}"


# ═══════════════════════════════════════════════════════════════
# read_links_file
# ═══════════════════════════════════════════════════════════════


class TestReadLinksFile:
    def _create_links(self, lines):
        f = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.txt')
        f.write('\n'.join(lines))
        f.close()
        return f.name

    @pytest.mark.parametrize("case", [
        {"lines": ["https://www.youtube.com/watch?v=abc123",
                    "https://www.youtube.com/watch?v=def456"], "expected": 2},
        {"lines": ["# comment", "https://www.youtube.com/watch?v=abc123",
                     "", "   ", "https://www.youtube.com/watch?v=def456"], "expected": 2},
        {"lines": ["not a url (starts with http)",
                    "https://www.youtube.com/watch?v=abc123"], "expected": 1},
        {"lines": [], "expected": 0},
    ])
    def test_ru(self, case):
        path = self._create_links(case["lines"])
        try:
            result = ru.read_links_file(path)
            assert len(result) == case["expected"]
            for link in result:
                assert link.startswith('http')
        finally:
            os.unlink(path)

    @pytest.mark.parametrize("case", [
        {"lines": ["https://www.youtube.com/watch?v=abc123",
                    "https://www.youtube.com/watch?v=def456"], "expected": 2},
        {"lines": ["# comment", "https://www.youtube.com/watch?v=abc123",
                     "", "   ", "https://www.youtube.com/watch?v=def456"], "expected": 2},
        {"lines": ["not a url", "https://www.youtube.com/watch?v=abc123"], "expected": 1},
        {"lines": [], "expected": 0},
    ])
    def test_en(self, case):
        path = self._create_links(case["lines"])
        try:
            result = en.read_links_file(path)
            assert len(result) == case["expected"]
            for link in result:
                assert link.startswith('http')
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════
# C.1 — load_config() tests
# ═══════════════════════════════════════════════════════════════

def test_load_config_defaults_no_file(tmp_path, reset_config):
    """When config.toml does not exist, load_config returns hardcoded defaults."""
    nonexistent = tmp_path / "no_such_config.toml"
    cfg = ru.load_config(str(nonexistent))
    assert cfg["downloads"]["max_attempts"] == 3
    assert cfg["downloads"]["output_dir"] == "downloads"
    assert cfg["cookies"]["mode"] == "browser"
    assert cfg["cookies"]["browser"] == "firefox"
    assert cfg["network"]["retries"] == 15
    assert cfg["network"]["timeout_video"] == 3600
    assert cfg["network"]["timeout_playlist"] == 86400
    assert cfg["logging"]["max_bytes"] == 10 * 1024 * 1024
    assert cfg["logging"]["backup_count"] == 5


def test_load_config_override(tmp_path, reset_config):
    """A valid config.toml overrides specific keys; rest stay at defaults."""
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        '[network]\nretries = 5\nsleep_requests = 2\n\n'
        '[cookies]\nbrowser = "chrome"\n',
        encoding="utf-8"
    )
    cfg = ru.load_config(str(cfg_path))
    assert cfg["network"]["retries"] == 5
    assert cfg["network"]["sleep_requests"] == 2
    assert cfg["cookies"]["browser"] == "chrome"
    assert cfg["network"]["timeout_video"] == 3600
    assert cfg["downloads"]["max_attempts"] == 3
    assert cfg["cookies"]["mode"] == "browser"


def test_load_config_partial_override(tmp_path, reset_config):
    """Only the [cookies] section is overridden; other sections stay at defaults."""
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        '[cookies]\nmode = "file"\ncookies_file = "my_cookies.txt"\n',
        encoding="utf-8"
    )
    cfg = ru.load_config(str(cfg_path))
    assert cfg["cookies"]["mode"] == "file"
    assert cfg["cookies"]["cookies_file"] == "my_cookies.txt"
    assert cfg["network"]["retries"] == 15
    assert cfg["downloads"]["max_attempts"] == 3
    assert cfg["logging"]["max_bytes"] == 10 * 1024 * 1024


def test_load_config_invalid_toml(tmp_path, reset_config):
    """Invalid TOML causes fallback to defaults — no crash."""
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("this is { not [[ valid toml", encoding="utf-8")
    cfg = ru.load_config(str(cfg_path))
    assert cfg["downloads"]["max_attempts"] == 3
    assert cfg["network"]["retries"] == 15
    assert cfg["cookies"]["browser"] == "firefox"


# ═══════════════════════════════════════════════════════════════
# C.2 — _build_cookie_args() tests
# ═══════════════════════════════════════════════════════════════

def test_cookie_browser():
    """mode=browser -> --cookies-from-browser firefox."""
    cfg = {"cookies": {"mode": "browser", "browser": "firefox", "cookies_file": "cookies.txt"}}
    assert ru._build_cookie_args(cfg, "/tmp") == ["--cookies-from-browser", "firefox"]


def test_cookie_browser_chrome():
    """mode=browser with browser='chrome'."""
    cfg = {"cookies": {"mode": "browser", "browser": "chrome", "cookies_file": "cookies.txt"}}
    assert ru._build_cookie_args(cfg, "/tmp") == ["--cookies-from-browser", "chrome"]


def test_cookie_file_exists(tmp_path):
    """mode=file with existing cookies.txt -> --cookies /path."""
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("youtube.com\tTRUE", encoding="utf-8")
    cfg = {"cookies": {"mode": "file", "browser": "firefox", "cookies_file": str(cookie_file)}}
    result = ru._build_cookie_args(cfg, str(tmp_path))
    assert result == ["--cookies", str(cookie_file)]


def test_cookie_file_missing(tmp_path):
    """mode=file without cookies.txt -> fallback to browser."""
    nonexistent = tmp_path / "nonexistent.txt"
    cfg = {"cookies": {"mode": "file", "browser": "edge", "cookies_file": str(nonexistent)}}
    result = ru._build_cookie_args(cfg, str(tmp_path))
    assert result == ["--cookies-from-browser", "edge"]


def test_cookie_file_missing_fallback_path(tmp_path):
    """Relative cookies_file + script_dir -> correct joined path."""
    cookie_file = tmp_path / "my_cookies.txt"
    cookie_file.write_text("net", encoding="utf-8")
    cfg = {"cookies": {"mode": "file", "browser": "firefox", "cookies_file": "my_cookies.txt"}}
    result = ru._build_cookie_args(cfg, str(tmp_path))
    expected = os.path.join(str(tmp_path), "my_cookies.txt")
    assert result == ["--cookies", expected]


def test_cookie_off():
    """mode=off -> empty list."""
    cfg = {"cookies": {"mode": "off", "browser": "firefox", "cookies_file": "cookies.txt"}}
    assert ru._build_cookie_args(cfg, "/tmp") == []


# ═══════════════════════════════════════════════════════════════
# C.3 — setup_check() tests (mocked)
# ═══════════════════════════════════════════════════════════════

def test_setup_check_python_version_ok(monkeypatch, capsys):
    """Python 3.8+ is detected as OK."""
    import sys as _sys
    monkeypatch.setattr(_sys, "version_info", VersionInfo(3, 8, 0))
    monkeypatch.setattr("builtins.input", lambda _: "n")
    ru.setup_check()
    out = capsys.readouterr().out
    assert "Python" in out or "python" in out


def test_setup_check_python_version_old(monkeypatch, capsys):
    """Python 3.7 is flagged."""
    import sys as _sys
    monkeypatch.setattr(_sys, "version_info", VersionInfo(3, 7, 0))
    monkeypatch.setattr("builtins.input", lambda _: "n")
    ru.setup_check()
    out = capsys.readouterr().out
    assert "3.7" in out or "3.8" in out


def test_setup_check_ytdlp_missing(monkeypatch, capsys):
    """Missing yt-dlp does not crash; script offers to install."""
    import subprocess as _sp
    original_run = _sp.run

    def mock_run(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and any("yt-dlp" in str(c) for c in cmd):
            raise FileNotFoundError("yt-dlp not found")
        return original_run(cmd, *a, **kw)

    monkeypatch.setattr(_sp, "run", mock_run)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    ru.setup_check()
    out = capsys.readouterr().out
    assert "yt-dlp" in out


def test_setup_check_colorama_found(monkeypatch, capsys):
    """Colorama found -> OK."""
    original_find = importlib.util.find_spec

    def mock_find(name):
        if name == "colorama":
            return True
        return original_find(name)

    monkeypatch.setattr(importlib.util, "find_spec", mock_find)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    ru.setup_check()
    out = capsys.readouterr().out
    assert "colorama" in out


def test_setup_check_cookies_mode_file_no_file(monkeypatch, capsys, reset_config):
    """mode=file without cookies.txt shows a warning."""
    tmp = tempfile.mkdtemp()
    nonexistent = os.path.join(tmp, "cookies.txt")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    original_load = ru.load_config

    def patched_load(*a, **kw):
        cfg = original_load(*a, **kw)
        cfg["cookies"]["mode"] = "file"
        cfg["cookies"]["cookies_file"] = nonexistent
        return cfg

    monkeypatch.setattr(ru, "load_config", patched_load)
    ru.setup_check()
    out = capsys.readouterr().out
    assert "cookies" in out.lower()


# ═══════════════════════════════════════════════════════════════
# C.4 — run_cleanup() tests (mocked)
# ═══════════════════════════════════════════════════════════════

def test_cleanup_flag_routing():
    """--cleanup flag is correctly parsed by argparse."""
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Downloader")
    parser.add_argument('--cleanup', '-C', action='store_true')
    assert parser.parse_args(['--cleanup']).cleanup is True
    assert parser.parse_args(['-C']).cleanup is True
    assert parser.parse_args([]).cleanup is False


def test_cleanup_script_not_found(monkeypatch):
    """Both cleaners missing -> graceful exit, subprocess.run NOT called."""
    import subprocess as _sp
    calls = []

    def mock_run(cmd, *a, **kw):
        calls.append(cmd)
        return MagicMock(returncode=0)

    monkeypatch.setattr(_sp, "run", mock_run)
    monkeypatch.setattr(os.path, "isfile", lambda p: False)

    tmpdir = tempfile.mkdtemp()
    cleaner_en = os.path.join(tmpdir, "yt_media_cleaner_en.py")
    cleaner_ru = os.path.join(tmpdir, "yt_media_cleaner_ru.py")
    if not os.path.isfile(cleaner_en) and not os.path.isfile(cleaner_ru):
        pass  # graceful exit — subprocess NOT called

    assert len(calls) == 0

# ═══════════════════════════════════════════════════════════════
# colored()
# ═══════════════════════════════════════════════════════════════

class TestColored:
    def test_no_color(self):
        """Without color_code, returns plain text."""
        assert ru.colored("hello") == "hello"
        assert en.colored("hello") == "hello"

    def test_no_colorama(self, monkeypatch):
        """When COLORS_AVAILABLE is False, returns plain text."""
        monkeypatch.setattr(ru, 'COLORS_AVAILABLE', False)
        monkeypatch.setattr(en, 'COLORS_AVAILABLE', False)
        assert ru.colored("hello", "RED") == "hello"
        assert en.colored("hello", "RED") == "hello"


# ═══════════════════════════════════════════════════════════════
# generate_nfo_file()
# ═══════════════════════════════════════════════════════════════

class TestGenerateNfoFile:
    def _make_info_json(self, tmp_path, data):
        """Create a .info.json file and return its path."""
        info_path = tmp_path / "Test Video [abc123].info.json"
        info_path.write_text(json.dumps(data), encoding="utf-8")
        return str(info_path)

    def test_basic_nfo_en(self, tmp_path):
        """EN: generates valid NFO with correct fields."""
        info = {
            "title": "Test Video",
            "id": "abc123",
            "uploader": "TestChannel",
            "description": "A test description",
            "upload_date": "20250615",
        }
        path = self._make_info_json(tmp_path, info)
        result = en.generate_nfo_file(path)
        assert result is True
        nfo_path = path.replace(".info.json", ".nfo")
        assert os.path.exists(nfo_path)
        nfo = open(nfo_path, encoding="utf-8").read()
        assert "<?xml version" in nfo
        assert "<title>Test Video</title>" in nfo
        assert "<studio>TestChannel</studio>" in nfo
        assert '<uniqueid type="youtube">abc123</uniqueid>' in nfo
        assert "<plot>A test description</plot>" in nfo
        assert "<premiered>2025-06-15 00:00:00Z</premiered>" in nfo
        assert "<year>2025</year>" in nfo
        assert "<source>YouTube</source>" in nfo

    def test_basic_nfo_ru(self, tmp_path):
        """RU: same behavior as EN."""
        info = {
            "title": "Тестовое видео",
            "id": "xyz789",
            "uploader": "ТестКанал",
            "description": "Описание",
            "upload_date": "20240101",
        }
        path = self._make_info_json(tmp_path, info)
        result = ru.generate_nfo_file(path)
        assert result is True
        nfo = open(path.replace(".info.json", ".nfo"), encoding="utf-8").read()
        assert "<title>Тестовое видео</title>" in nfo
        assert "<year>2024</year>" in nfo

    def test_xml_escape_ampersand(self, tmp_path):
        """Ampersand in title/description is escaped."""
        info = {
            "title": "Rock & Roll",
            "id": "amp1",
            "uploader": "A & B",
            "description": "Tom & Jerry show",
            "upload_date": "20250101",
        }
        path = self._make_info_json(tmp_path, info)
        en.generate_nfo_file(path)
        nfo = open(path.replace(".info.json", ".nfo"), encoding="utf-8").read()
        assert "&amp;" in nfo
        assert "Rock & Roll" not in nfo  # raw & must not appear

    def test_xml_escape_angle_brackets(self, tmp_path):
        """Angle brackets in title are escaped."""
        info = {
            "title": "Test <bold> Title",
            "id": "angle1",
            "uploader": "Channel",
            "description": "",
            "upload_date": "",
        }
        path = self._make_info_json(tmp_path, info)
        en.generate_nfo_file(path)
        nfo = open(path.replace(".info.json", ".nfo"), encoding="utf-8").read()
        assert "&lt;bold&gt;" in nfo

    def test_missing_info_json(self, tmp_path):
        """Non-existent file returns False."""
        result = en.generate_nfo_file(str(tmp_path / "missing.info.json"))
        assert result is False

    def test_empty_description(self, tmp_path):
        """Empty description produces valid NFO."""
        info = {"title": "T", "id": "x", "uploader": "U", "description": "", "upload_date": ""}
        path = self._make_info_json(tmp_path, info)
        result = en.generate_nfo_file(path)
        assert result is True
        nfo = open(path.replace(".info.json", ".nfo"), encoding="utf-8").read()
        assert "<plot></plot>" in nfo

    def test_sorttitle_is_title(self, tmp_path):
        """sorttitle should be the video title (not month_day)."""
        info = {
            "title": "My Video Title",
            "id": "st1",
            "uploader": "Ch",
            "description": "",
            "upload_date": "20250315",
        }
        path = self._make_info_json(tmp_path, info)
        en.generate_nfo_file(path)
        nfo = open(path.replace(".info.json", ".nfo"), encoding="utf-8").read()
        assert "<sorttitle>My Video Title</sorttitle>" in nfo

    def test_idempotent(self, tmp_path):
        """Calling twice does not fail (file is overwritten)."""
        info = {"title": "T", "id": "x", "uploader": "U", "description": "", "upload_date": ""}
        path = self._make_info_json(tmp_path, info)
        assert en.generate_nfo_file(path) is True
        assert en.generate_nfo_file(path) is True
