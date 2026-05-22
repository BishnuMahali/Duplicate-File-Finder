# core.Blocking.py — Intelligent candidate pair generation (blocking)
"""
Pre-groups files into blocks so we never compare every file against every other.
Uses stem index, token index, prefix index, extension category, and length buckets.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Iterable, List, Set, Tuple

from dff_lite.core.Models import BlockingConfig, FileRecord


def compute_token_signature(tokens: List[str]) -> str:
    """Stable hash of sorted significant tokens for blocking."""
    if not tokens:
        return ""
    key = "|".join(sorted(tokens))
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]


def compute_length_bucket(normalized: str, step: int = 5) -> int:
    """Bucket normalized name length for coarse blocking."""
    if not normalized:
        return 0
    return len(normalized) // step


def enrich_record(record: FileRecord, ext_category_fn) -> FileRecord:
    """Attach blocking fields used by indices."""
    sig = compute_token_signature(record.tokens)
    bucket = compute_length_bucket(record.normalized_name)
    cat = ext_category_fn(record.extension)
    return record.model_copy(
        update={
            "token_signature": sig,
            "length_bucket": bucket,
            "extension_category": cat,
        }
    )


def canonical_pair(path_a: str, path_b: str) -> Tuple[str, str]:
    if path_a < path_b:
        return path_a, path_b
    return path_b, path_a


def register_pairs(
    group: List[FileRecord],
    pairs: Set[Tuple[str, str]],
    max_block_size: int,
) -> None:
    """Add all unique pairs within a block if block size is manageable."""
    n = len(group)
    if n < 2 or n > max_block_size:
        return
    for i in range(n):
        for j in range(i + 1, n):
            pa, pb = group[i].path, group[j].path
            if pa != pb:
                pairs.add(canonical_pair(pa, pb))


def build_candidate_pairs(
    records: List[FileRecord],
    config: BlockingConfig,
    ext_category_fn,
) -> Set[Tuple[str, str]]:
    """
    Multi-index blocking: only compare files that share at least one blocking key.
    """
    enriched = [enrich_record(r, ext_category_fn) for r in records]
    pairs: Set[Tuple[str, str]] = set()
    max_sz = config.max_block_size

    stem_index: Dict[str, List[FileRecord]] = {}
    token_index: Dict[str, List[FileRecord]] = {}
    prefix_index: Dict[str, List[FileRecord]] = {}
    sig_index: Dict[str, List[FileRecord]] = {}
    ext_index: Dict[str, List[FileRecord]] = {}
    len_index: Dict[int, List[FileRecord]] = {}

    for r in enriched:
        if r.normalized_name:
            stem_index.setdefault(r.normalized_name, []).append(r)

        for token in r.tokens:
            if len(token) >= config.min_token_length:
                token_index.setdefault(token, []).append(r)

        if len(r.normalized_name) >= config.prefix_length:
            prefix = r.normalized_name[: config.prefix_length]
            prefix_index.setdefault(prefix, []).append(r)

        if config.use_token_signature and r.token_signature:
            sig_index.setdefault(r.token_signature, []).append(r)

        if config.use_extension_category:
            ext_index.setdefault(r.extension_category, []).append(r)

        if config.use_length_bucket:
            len_index.setdefault(r.length_bucket, []).append(r)

    for index in (
        stem_index,
        token_index,
        prefix_index,
        sig_index,
        ext_index,
        len_index,
    ):
        for group in index.values():
            register_pairs(group, pairs, max_sz)

    return pairs


def iter_pair_batches(
    pairs: Iterable[Tuple[str, str]],
    batch_size: int,
) -> Iterable[List[Tuple[str, str]]]:
    """Yield comparison batches for threaded scoring."""
    batch: List[Tuple[str, str]] = []
    for pair in pairs:
        batch.append(pair)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch
