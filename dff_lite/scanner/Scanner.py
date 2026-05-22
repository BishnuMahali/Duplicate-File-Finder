# scanner.Scanner.py — Multithreaded recursive scan engine
"""Discovers files across multiple roots with extension filters and incremental SQLite cache."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List, Optional, Set

from dff_lite.core.Models import FileRecord, NormalizationConfig, ScanConfig
from dff_lite.database.DB import DFFDatabase
from dff_lite.normalizer.Normalizer import normalize_filename

logger = logging.getLogger("dff_lite.scanner")


def get_files_in_dir(
    root: Path,
    scan_config: ScanConfig,
    progress_callback: Optional[Callable[[str], None]] = None,
    recursive: bool = True
) -> List[Path]:
    exclude_set = {f.lower() for f in scan_config.exclude_folders}
    include_extensions = {ext.lower() for ext in scan_config.include_extensions}
    candidates: List[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        if not recursive:
            dirnames.clear()
        else:
            dirnames[:] = [d for d in dirnames if d.lower() not in exclude_set]
        
        if progress_callback:
            progress_callback(f"Scanning: {dirpath}")

        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if not include_extensions or ext in include_extensions:
                candidates.append(Path(dirpath) / name)

    return candidates


def process_single_file(
    file_path: Path,
    norm_config: NormalizationConfig,
) -> Optional[FileRecord]:
    try:
        if not file_path.is_file():
            return None
        stat = file_path.stat()
        resolved = str(file_path.resolve())
        normalized_name, tokens = normalize_filename(file_path.name, norm_config)
        return FileRecord(
            path=resolved,
            filename=file_path.name,
            extension=file_path.suffix.lower(),
            size=stat.st_size,
            mtime=stat.st_mtime,
            parent_folder=str(file_path.parent),
            normalized_name=normalized_name,
            tokens=tokens,
        )
    except (PermissionError, OSError, FileNotFoundError) as exc:
        logger.debug("Skipped inaccessible file %s: %s", file_path, exc)
        return None


def scan_folders(
    roots: List[str],
    db: DFFDatabase,
    scan_config: ScanConfig,
    norm_config: NormalizationConfig,
    progress_callback: Optional[Callable[[str], None]] = None,
    progress_update_records: Optional[Callable[[int], None]] = None,
    recursive: bool = True
) -> List[FileRecord]:
    all_paths: List[Path] = []
    for root_str in roots:
        root = Path(root_str)
        if not root.exists():
            logger.warning("Root does not exist: %s", root)
            continue
        all_paths.extend(get_files_in_dir(root, scan_config, progress_callback, recursive))

    if progress_callback:
        progress_callback(f"Found {len(all_paths)} candidate files. Checking cache...")

    cache_map = db.get_cached_files()
    cached_records = {r.path: r for r in db.load_file_records()}
    active_paths: Set[str] = set()
    active_records: List[FileRecord] = []
    uncached: List[Path] = []

    for path in all_paths:
        try:
            path_str = str(path.resolve())
            active_paths.add(path_str)
            stat = path.stat()
            if path_str in cache_map:
                cached_mtime, cached_size = cache_map[path_str]
                if abs(cached_mtime - stat.st_mtime) < 0.01 and cached_size == stat.st_size:
                    if path_str in cached_records:
                        active_records.append(cached_records[path_str])
                        continue
            uncached.append(path)
        except (PermissionError, OSError):
            continue

    if progress_callback:
        progress_callback(f"Processing {len(uncached)} new/changed files...")

    records_to_save: List[FileRecord] = []

    def _process_batch(paths: List[Path]) -> None:
        nonlocal active_records, records_to_save
        if scan_config.multithreading and len(paths) > 1:
            with ThreadPoolExecutor(max_workers=scan_config.max_workers) as pool:
                futures = {
                    pool.submit(process_single_file, p, norm_config): p for p in paths
                }
                count = 0
                for fut in as_completed(futures):
                    rec = fut.result()
                    if rec:
                        active_records.append(rec)
                        records_to_save.append(rec)
                    count += 1
                    if progress_update_records:
                        progress_update_records(count)
        else:
            for i, p in enumerate(paths, 1):
                rec = process_single_file(p, norm_config)
                if rec:
                    active_records.append(rec)
                    records_to_save.append(rec)
                if progress_update_records:
                    progress_update_records(i)

    for i in range(0, len(uncached), scan_config.batch_size):
        _process_batch(uncached[i : i + scan_config.batch_size])

    if records_to_save:
        db.save_file_records(records_to_save)

    db.remove_stale_files(active_paths)
    return active_records
