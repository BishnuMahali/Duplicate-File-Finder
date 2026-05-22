# database/db.py — SQLite persistence for scans and match results
"""Incremental scan cache and stored comparison results."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Tuple

from dff_lite.core.Models import FileRecord, MatchResult

logger = logging.getLogger("dff_lite.database")


class DFFDatabase:
    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path).resolve())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    mtime REAL NOT NULL,
                    parent_folder TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    tokens TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    path_a TEXT NOT NULL,
                    path_b TEXT NOT NULL,
                    file_a_size INTEGER NOT NULL,
                    file_b_size INTEGER NOT NULL,
                    scores TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    category TEXT NOT NULL,
                    PRIMARY KEY (path_a, path_b)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_normalized ON files(normalized_name)"
            )
            conn.commit()

    def get_cached_files(self) -> Dict[str, Tuple[float, int]]:
        with self._connect() as conn:
            cur = conn.execute("SELECT path, mtime, size FROM files")
            return {row["path"]: (row["mtime"], row["size"]) for row in cur.fetchall()}

    def load_file_records(self) -> List[FileRecord]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM files")
            return [
                FileRecord(
                    path=row["path"],
                    filename=row["filename"],
                    extension=row["extension"],
                    size=row["size"],
                    mtime=row["mtime"],
                    parent_folder=row["parent_folder"],
                    normalized_name=row["normalized_name"],
                    tokens=json.loads(row["tokens"]),
                )
                for row in cur.fetchall()
            ]

    def save_file_records(self, records: List[FileRecord]) -> None:
        if not records:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO files
                (path, filename, extension, size, mtime, parent_folder, normalized_name, tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r.path,
                        r.filename,
                        r.extension,
                        r.size,
                        r.mtime,
                        r.parent_folder,
                        r.normalized_name,
                        json.dumps(r.tokens),
                    )
                    for r in records
                ],
            )
            conn.commit()
        logger.info("Cached %d file records", len(records))

    def remove_stale_files(self, active_paths: Set[str]) -> None:
        with self._connect() as conn:
            cur = conn.execute("SELECT path FROM files")
            cached = {row["path"] for row in cur.fetchall()}
            stale = list(cached - active_paths)
            if not stale:
                return
            chunk = 900
            for i in range(0, len(stale), chunk):
                part = stale[i : i + chunk]
                placeholders = ",".join("?" * len(part))
                conn.execute(f"DELETE FROM files WHERE path IN ({placeholders})", part)
            conn.commit()
            logger.info("Removed %d stale cache entries", len(stale))

    def get_cached_matches(self) -> List[MatchResult]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM matches ORDER BY confidence_score DESC")
            return [
                MatchResult(
                    path_a=row["path_a"],
                    path_b=row["path_b"],
                    file_a_size=row["file_a_size"],
                    file_b_size=row["file_b_size"],
                    scores=json.loads(row["scores"]),
                    confidence_score=row["confidence_score"],
                    category=row["category"],
                )
                for row in cur.fetchall()
            ]

    def save_matches(self, matches: List[MatchResult]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM matches")
            if matches:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO matches
                    (path_a, path_b, file_a_size, file_b_size, scores, confidence_score, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            m.path_a,
                            m.path_b,
                            m.file_a_size,
                            m.file_b_size,
                            json.dumps(m.scores),
                            m.confidence_score,
                            m.category,
                        )
                        for m in matches
                    ],
                )
            conn.commit()

    def clear_cache(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM files")
            conn.execute("DELETE FROM matches")
            conn.commit()

