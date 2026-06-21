#!/usr/bin/env python3
"""Tests for yt-download — minimal pure-function tests.

Tests cover: is_playlist_url, format_time, classify_error, read_links_file
for both RU and EN versions. No network calls, no real downloads.
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# ── Import RU and EN scripts ──────────────────────────────────────────
# Both files have dots in the name, so we use importlib from the file path.
SCRIPT_DIR = Path(__file__).resolve().parent.parent


def _import_from_path(module_name, filename):
    """Import a Python file by its filesystem path."""
    filepath = SCRIPT_DIR / filename
    if not filepath.exists():
        pytest.skip(f"{filename} not found")
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    ru = _import_from_path("yt_download5_4_RU", "yt-download5.4_RU.py")
    RU_AVAILABLE = True
except Exception as e:
    ru = None
    RU_AVAILABLE = False
    print(f"[WARN] RU import failed: {e}")

try:
    en = _import_from_path("yt_download5_4_EN", "yt-download5.4_EN.py")
    EN_AVAILABLE = True
except Exception as e:
    en = None
    EN_AVAILABLE = False
    print(f"[WARN] EN import failed: {e}")


# ── Test helpers ───────────────────────────────────────────────────────


def _check_module(module, name):
    if module is None:
        pytest.skip(f"{name} not available")


# ═══════════════════════════════════════════════════════════════════════
# is_playlist_url
# ═══════════════════════════════════════════════════════════════════════


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
        _check_module(ru, "RU")
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
        _check_module(en, "EN")
        assert en.is_playlist_url(url) == expected


# ═══════════════════════════════════════════════════════════════════════
# format_time
# ═══════════════════════════════════════════════════════════════════════


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
        _check_module(ru, "RU")
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
        _check_module(en, "EN")
        assert en.format_time(seconds) == expected_en


# ═══════════════════════════════════════════════════════════════════════
# classify_error
# ═══════════════════════════════════════════════════════════════════════


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
        _check_module(ru, "RU")
        result = ru.classify_error(line.lower(), [])
        for key, val in expected_keys.items():
            assert result.get(key) == val, f"RU: {line} → {key} expected {val}, got {result.get(key)}"

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
        _check_module(en, "EN")
        result = en.classify_error(line.lower(), [])
        for key, val in expected_keys.items():
            assert result.get(key) == val, f"EN: {line} → {key} expected {val}, got {result.get(key)}"


# ═══════════════════════════════════════════════════════════════════════
# read_links_file
# ═══════════════════════════════════════════════════════════════════════


class TestReadLinksFile:
    def _create_links(self, lines):
        """Create a temp links file with given lines."""
        f = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.txt')
        f.write('\n'.join(lines))
        f.close()
        return f.name

    @pytest.mark.parametrize("case", [
        {
            "lines": [
                "https://www.youtube.com/watch?v=abc123",
                "https://www.youtube.com/watch?v=def456",
            ],
            "expected": 2,
        },
        {
            "lines": [
                "# This is a comment",
                "https://www.youtube.com/watch?v=abc123",
                "",
                "   ",
                "https://www.youtube.com/watch?v=def456",
            ],
            "expected": 2,
        },
        {
            "lines": [
                "not a url (starts with http)",
                "https://www.youtube.com/watch?v=abc123",
            ],
            "expected": 1,
        },
        {
            "lines": [],
            "expected": 0,
        },
    ])
    def test_ru(self, case):
        _check_module(ru, "RU")
        path = self._create_links(case["lines"])
        try:
            result = ru.read_links_file(path)
            assert len(result) == case["expected"], f"RU: expected {case['expected']}, got {len(result)}: {result}"
            # Verify all returned links start with http
            for link in result:
                assert link.startswith('http'), f"RU: link does not start with http: {link}"
        finally:
            os.unlink(path)

    @pytest.mark.parametrize("case", [
        {
            "lines": [
                "https://www.youtube.com/watch?v=abc123",
                "https://www.youtube.com/watch?v=def456",
            ],
            "expected": 2,
        },
        {
            "lines": [
                "# This is a comment",
                "https://www.youtube.com/watch?v=abc123",
                "",
                "   ",
                "https://www.youtube.com/watch?v=def456",
            ],
            "expected": 2,
        },
        {
            "lines": [
                "not a url",
                "https://www.youtube.com/watch?v=abc123",
            ],
            "expected": 1,
        },
        {
            "lines": [],
            "expected": 0,
        },
    ])
    def test_en(self, case):
        _check_module(en, "EN")
        path = self._create_links(case["lines"])
        try:
            result = en.read_links_file(path)
            assert len(result) == case["expected"], f"EN: expected {case['expected']}, got {len(result)}: {result}"
            for link in result:
                assert link.startswith('http'), f"EN: link does not start with http: {link}"
        finally:
            os.unlink(path)