#!/usr/bin/env python3
"""
File Deduplicator & Orphan Media Cleaner
- Находит дубли файлов по SHA-256 хэшу
- Находит .json и .jpg без парного .mp4
- Поддерживает ручной и автоматический режим удаления дублей
- Жёсткая защита: удаляются ТОЛЬКО файлы .jpg / .jpeg / .json
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
from pathlib import Path
from collections import defaultdict
from typing import Optional, List

# Корректный вывод UTF-8 в Windows (CMD, PowerShell, Windows Terminal)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ─── КОНСТАНТЫ ────────────────────────────────────────────────────────────────

# ЖЁСТКИЙ СПИСОК: скрипт физически не может удалить файл с другим расширением
DELETABLE_EXTENSIONS = {".jpg", ".jpeg", ".json"}

# ─── КОНФИГ ───────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "media_cleaner_config.json"

DEFAULT_CONFIG: dict = {
    # Путь к рабочей директории.
    # Если пустая строка "" — используется директория запуска скрипта.
    "work_dir": "",
    "duplicate_mode": "manual",        # "manual" | "auto"
    "auto_keep_strategy": "shortest_path",  # "shortest_path" | "oldest" | "newest"
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"  [OK] Настройки сохранены: {CONFIG_PATH}")
    except OSError as e:
        print(f"  [!!] Не удалось сохранить настройки: {e}")


def resolve_work_dir(cfg: dict) -> Path:
    """Вернуть рабочую директорию из настроек или CWD."""
    raw = cfg.get("work_dir", "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        if p.is_dir():
            return p
        else:
            print(f"  [!!] Путь из настроек не найден: {p}")
            print(f"       Используется текущая директория.")
    return Path(".").resolve()


def show_config(cfg: dict) -> None:
    wd = cfg.get("work_dir", "").strip()
    wd_label = wd if wd else "(не задан -- используется директория запуска)"
    mode_label = "[AUTO] Авто" if cfg["duplicate_mode"] == "auto" else "[HAND] Ручной"
    strat_labels = {
        "shortest_path": "оставить файл с кратчайшим путём",
        "oldest":        "оставить самый старый файл",
        "newest":        "оставить самый новый файл",
    }
    strat = strat_labels.get(cfg["auto_keep_strategy"], cfg["auto_keep_strategy"])
    print(f"  Рабочая директория    : {wd_label}")
    print(f"  Режим удаления дублей : {mode_label}")
    if cfg["duplicate_mode"] == "auto":
        print(f"  Стратегия авто-режима : {strat}")
    print(f"  Защищённые расширения : только .jpg/.jpeg/.json могут быть удалены")


def settings_menu(cfg: dict) -> dict:
    print("\n+--------------------------------------------------+")
    print("|              [S] Настройки                       |")
    print("+--------------------------------------------------+")
    show_config(cfg)
    print("\n  Что изменить?")
    print("  1 -- Рабочая директория")
    print("  2 -- Режим удаления дублей (ручной / авто)")
    print("  3 -- Стратегия авто-режима")
    print("  0 -- Назад")

    while True:
        raw = input("\nВаш выбор: ").strip()

        if raw == "0":
            break

        elif raw == "1":
            print("\n  Введите полный путь к рабочей директории.")
            print("  Примеры:")
            print("    Windows : D:\\Media\\Downloads")
            print("    Пусто   : оставить пустым для использования директории запуска")
            new_path = input("  Путь: ").strip()
            if new_path == "":
                cfg["work_dir"] = ""
                print("  >> Рабочая директория: директория запуска скрипта")
            else:
                p = Path(new_path).expanduser().resolve()
                if p.is_dir():
                    cfg["work_dir"] = str(p)
                    print(f"  >> Рабочая директория установлена: {p}")
                else:
                    print(f"  [!!] Путь не существует или не является директорией: {p}")
                    print("       Настройка не изменена.")
            save_config(cfg)
            break

        elif raw == "2":
            print("\n  Режим удаления дублей:")
            print("  1 -- Ручной  (спрашивать для каждой группы)")
            print("  2 -- Авто    (удалять автоматически по стратегии)")
            sub = input("  Выбор: ").strip()
            if sub == "1":
                cfg["duplicate_mode"] = "manual"
                print("  >> Режим: Ручной")
            elif sub == "2":
                cfg["duplicate_mode"] = "auto"
                print("  >> Режим: Авто")
            save_config(cfg)
            break

        elif raw == "3":
            print("\n  Стратегия авто-режима (какой файл из группы ОСТАВИТЬ):")
            print("  1 -- Файл с кратчайшим путём (ближе к корню)")
            print("  2 -- Самый старый по дате изменения")
            print("  3 -- Самый новый по дате изменения")
            sub = input("  Выбор: ").strip()
            mapping = {"1": "shortest_path", "2": "oldest", "3": "newest"}
            if sub in mapping:
                cfg["auto_keep_strategy"] = mapping[sub]
                print(f"  >> Стратегия: {mapping[sub]}")
                save_config(cfg)
            break

        else:
            print("  Введите 0, 1, 2 или 3.")

    return cfg


# ─── УТИЛИТЫ ──────────────────────────────────────────────────────────────────

def is_deletable(path: Path) -> bool:
    """
    ЖЁСТКАЯ проверка безопасности.
    Возвращает True только если расширение файла входит в DELETABLE_EXTENSIONS.
    Проверка выполняется по нижнему регистру, .info.json тоже считается .json.
    """
    name_lower = path.name.lower()
    if name_lower.endswith(".info.json"):
        return True
    return path.suffix.lower() in DELETABLE_EXTENSIONS


def safe_unlink(path: Path) -> bool:
    """
    Удалить файл с проверкой безопасности.
    Возвращает True при успехе, False при любой ошибке или блокировке.
    """
    if not is_deletable(path):
        print(f"  [BLOCK] Удаление заблокировано (расширение не в списке): {path}")
        return False
    try:
        path.unlink()
        print(f"  [OK] Удалён: {path}")
        return True
    except PermissionError:
        print(f"  [!!] Нет доступа (файл занят или защищён): {path}")
        return False
    except OSError as e:
        print(f"  [!!] Ошибка удаления: {e}")
        return False


def calc_hash(filepath: Path, chunk_size: int = 65536) -> Optional[str]:
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, PermissionError) as e:
        print(f"  [!] Не удалось прочитать {filepath}: {e}")
        return None


def fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        yield Path(dirpath), filenames


# ─── 1. ДУБЛИ ─────────────────────────────────────────────────────────────────

def find_duplicates(root: Path) -> dict:
    print("\n[>>] Сканирую файлы для поиска дублей...")
    hash_map: dict = defaultdict(list)
    total = 0

    for dir_path, filenames in walk(root):
        for name in filenames:
            if name.startswith("."):
                continue
            fp = dir_path / name
            if not fp.is_file():
                continue
            total += 1
            if total % 50 == 0:
                print(f"  Файлов обработано: {total}", end="\r", flush=True)
            h = calc_hash(fp)
            if h:
                hash_map[h].append(fp)

    print(f"  Всего файлов проверено: {total}               ")
    return {h: paths for h, paths in hash_map.items() if len(paths) > 1}


def pick_file_to_keep(paths: List[Path], strategy: str) -> Path:
    if strategy == "shortest_path":
        return min(paths, key=lambda p: len(str(p)))
    elif strategy == "oldest":
        return min(paths, key=lambda p: p.stat().st_mtime)
    elif strategy == "newest":
        return max(paths, key=lambda p: p.stat().st_mtime)
    return paths[0]


def handle_duplicates(duplicates: dict, cfg: dict) -> None:
    if not duplicates:
        print("\n[OK] Дублей не найдено.")
        return

    groups = list(duplicates.items())
    mode = cfg["duplicate_mode"]
    strategy = cfg["auto_keep_strategy"]

    print(f"\n[!!] Найдено групп дублей: {len(groups)}")
    print(f"     Внимание: файлы с расширением вне .jpg/.jpeg/.json удалены не будут.")

    if mode == "auto":
        _handle_duplicates_auto(groups, strategy)
    else:
        _handle_duplicates_manual(groups)


def _handle_duplicates_auto(groups: list, strategy: str) -> None:
    strat_labels = {
        "shortest_path": "кратчайший путь",
        "oldest":        "самый старый",
        "newest":        "самый новый",
    }
    print(f"  Режим: Авто  |  Стратегия: {strat_labels.get(strategy, strategy)}\n")

    to_delete: list = []
    skipped_protected: int = 0

    for file_hash, paths in groups:
        try:
            keep = pick_file_to_keep(paths, strategy)
        except OSError:
            keep = paths[0]
        for p in paths:
            if p != keep:
                if is_deletable(p):
                    to_delete.append((keep, p))
                else:
                    skipped_protected += 1

    if skipped_protected:
        print(f"  [BLOCK] Пропущено защищённых файлов: {skipped_protected} (расширение не .jpg/.jpeg/.json)")

    if not to_delete:
        print("  [OK] Нечего удалять.")
        return

    for i, (keep, delete) in enumerate(to_delete, 1):
        try:
            sz = delete.stat().st_size
        except OSError:
            sz = 0
        print(f"  {i:>4}. УДАЛИТЬ : {delete}  [{fmt_size(sz)}]")
        print(f"        ОСТАВИТЬ: {keep}\n")

    confirm = input(
        f"\n  Удалить {len(to_delete)} файл(ов) автоматически? (y/n): "
    ).strip().lower()
    if confirm == "y":
        deleted = sum(1 for _, p in to_delete if safe_unlink(p))
        print(f"\n  Удалено файлов: {deleted}/{len(to_delete)}")
    else:
        print("  Отменено.")


def _handle_duplicates_manual(groups: list) -> None:
    for g_idx, (file_hash, paths) in enumerate(groups, 1):
        print(f"\n{'='*72}")
        print(f"Группа {g_idx}/{len(groups)}")
        print("\nВыберите файл для удаления (0 -- пропустить, q -- выход):\n")

        infos: list = []
        for i, p in enumerate(paths, 1):
            try:
                sz = p.stat().st_size
            except OSError:
                sz = 0
            protected = not is_deletable(p)
            tag = " [ЗАЩИЩЁН -- удаление невозможно]" if protected else ""
            infos.append((p, sz, protected))
            print(f"  {i}. {p.name}{tag}")
            print(f"     Хэш:    {file_hash}")
            print(f"     Размер: {fmt_size(sz)}")
            print(f"     Путь:   {p}\n")

        # Если все файлы в группе защищены -- пропустить автоматически
        if all(protected for _, _, protected in infos):
            print("  [BLOCK] Все файлы группы защищены. Пропуск.\n")
            continue

        while True:
            raw = input("Ваш выбор: ").strip().lower()
            if raw == "q":
                print("\nВыход.")
                sys.exit(0)
            if raw == "0":
                print("  Пропущено.\n")
                break
            if raw.isdigit() and 1 <= int(raw) <= len(infos):
                chosen, _, protected = infos[int(raw) - 1]
                if protected:
                    print(f"  [BLOCK] Нельзя удалить: расширение не входит в .jpg/.jpeg/.json")
                    continue
                conf = input(
                    f"\n  Удалить:\n     {chosen}\n  Подтвердите (y/n): "
                ).strip().lower()
                if conf == "y":
                    safe_unlink(chosen)
                else:
                    print("  Отменено.\n")
                break
            else:
                print(f"  Введите число 0--{len(infos)}, или q.")


# ─── 2. ОСИРОТЕВШИЕ МЕДИАФАЙЛЫ ────────────────────────────────────────────────

def get_base_stem(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".info.json"):
        return name[: -len(".info.json")]
    return Path(name).stem


def find_orphans(root: Path) -> List[Path]:
    print("\n[>>] Ищу .json/.jpg без парного .mp4...")

    mp4_stems: dict = defaultdict(set)
    for dir_path, filenames in walk(root):
        for name in filenames:
            if name.lower().endswith(".mp4"):
                mp4_stems[dir_path].add(Path(name).stem)

    orphans: List[Path] = []
    ext_targets = (".json", ".jpg", ".jpeg")

    for dir_path, filenames in walk(root):
        dir_mp4 = mp4_stems.get(dir_path, set())
        for name in filenames:
            lower = name.lower()
            if any(lower.endswith(ext) for ext in ext_targets):
                stem = get_base_stem(name)
                if stem not in dir_mp4:
                    orphans.append(dir_path / name)

    return orphans


def handle_orphans(orphans: List[Path]) -> None:
    if not orphans:
        print("\n[OK] Осиротевших файлов не найдено.")
        return

    print(f"\n[!!] Найдено осиротевших файлов: {len(orphans)}\n")
    for i, p in enumerate(orphans, 1):
        try:
            sz = p.stat().st_size
        except OSError:
            sz = 0
        print(f"  {i:>4}. [{fmt_size(sz):>10}]  {p}")

    print("\nДоступные действия:")
    print("  all      -- удалить все")
    print("  1,3,5    -- удалить выбранные по номерам")
    print("  skip     -- пропустить")
    print("  q        -- выход")

    while True:
        raw = input("\nВаш выбор: ").strip().lower()

        if raw == "q":
            print("\nВыход.")
            sys.exit(0)

        elif raw == "skip":
            print("  Пропущено.")
            break

        elif raw == "all":
            conf = input(
                f"  Удалить все {len(orphans)} файлов? (y/n): "
            ).strip().lower()
            if conf == "y":
                deleted = sum(1 for p in orphans if safe_unlink(p))
                print(f"\n  Удалено: {deleted}/{len(orphans)}")
            else:
                print("  Отменено.")
            break

        else:
            try:
                nums = [int(x.strip()) for x in raw.split(",") if x.strip()]
                selected: List[Path] = []
                valid = True
                for n in nums:
                    if 1 <= n <= len(orphans):
                        selected.append(orphans[n - 1])
                    else:
                        print(f"  [!!] Неверный номер: {n} (доступно 1--{len(orphans)})")
                        valid = False
                        break

                if valid and selected:
                    print(f"\n  Будут удалены ({len(selected)} шт.):")
                    for p in selected:
                        print(f"    - {p}")
                    conf = input("  Подтвердите (y/n): ").strip().lower()
                    if conf == "y":
                        deleted = sum(1 for p in selected if safe_unlink(p))
                        print(f"  Удалено: {deleted}/{len(selected)}")
                    else:
                        print("  Отменено.")
                    break
            except ValueError:
                print("  Введите 'all', 'skip', 'q' или номера через запятую (1,3,5).")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    cfg = load_config()
    root = resolve_work_dir(cfg)

    print("=" * 72)
    print("   File Deduplicator & Orphan Media Cleaner")
    print("=" * 72)
    print(f"  Рабочая директория: {root}")
    print(f"  Файл настроек     : {CONFIG_PATH}")
    print()
    show_config(cfg)

    print("\nРежим работы:")
    print("  1 -- Найти и удалить дубли файлов (по SHA-256)")
    print("  2 -- Найти и удалить осиротевшие .json / .jpg (без парного .mp4)")
    print("  3 -- Оба режима")
    print("  s -- Настройки")
    print("  q -- Выход")

    while True:
        mode = input("\nВыберите режим: ").strip().lower()

        if mode == "q":
            sys.exit(0)

        elif mode == "s":
            cfg = settings_menu(cfg)
            root = resolve_work_dir(cfg)
            print()
            print(f"  Рабочая директория: {root}")
            show_config(cfg)

        elif mode in ("1", "2", "3"):
            break

        else:
            print("  Введите 1, 2, 3, s или q.")

    if mode in ("1", "3"):
        dupes = find_duplicates(root)
        handle_duplicates(dupes, cfg)

    if mode in ("2", "3"):
        orphans = find_orphans(root)
        handle_orphans(orphans)

    print("\n[OK] Готово.")


if __name__ == "__main__":
    main()
