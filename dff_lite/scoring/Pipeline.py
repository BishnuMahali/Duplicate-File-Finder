# scoring.Pipeline.py — End-to-end compare pipeline with blocking and threading
"""Orchestrates blocking, batched pairwise scoring, and result persistence."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Set, Tuple

from dff_lite.core.Blocking import build_candidate_pairs, iter_pair_batches
from dff_lite.core.Models import AppConfig, FileRecord, MatchResult
from dff_lite.database.DB import DFFDatabase
from dff_lite.matchers.Extension import get_extension_category
from dff_lite.scoring.Engine import ScoringEngine

logger = logging.getLogger("dff_lite.pipeline")


def run_compare_pipeline(
    records: List[FileRecord],
    config: AppConfig,
    db: Optional[DFFDatabase] = None,
    threshold_override: Optional[float] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[MatchResult]:
    if not records:
        return []

    pairs = build_candidate_pairs(records, config.blocking, get_extension_category)
    logger.info("Blocking reduced comparisons to %d candidate pairs", len(pairs))

    record_map: Dict[str, FileRecord] = {r.path: r for r in records}
    engine = ScoringEngine(config)
    min_thresh = (
        threshold_override if threshold_override is not None else config.thresholds.weak
    )

    results: List[MatchResult] = []
    pair_list = list(pairs)
    total = len(pair_list)
    done = 0

    def score_pair(pair: Tuple[str, str]) -> Optional[MatchResult]:
        a, b = record_map.get(pair[0]), record_map.get(pair[1])
        if not a or not b:
            return None
        match = engine.compute_match(a, b)
        if match and match.confidence_score >= min_thresh:
            return match
        return None

    batches = list(iter_pair_batches(pair_list, config.scan.batch_size))

    if config.scan.multithreading and len(pair_list) > 50:
        with ThreadPoolExecutor(max_workers=config.scan.max_workers) as pool:
            for batch in batches:
                futures = [pool.submit(score_pair, p) for p in batch]
                for fut in as_completed(futures):
                    m = fut.result()
                    if m:
                        results.append(m)
                    done += 1
                    if progress_callback:
                        progress_callback(done, total)
    else:
        for batch in batches:
            for pair in batch:
                m = score_pair(pair)
                if m:
                    results.append(m)
                done += 1
                if progress_callback:
                    progress_callback(done, total)

    results.sort(key=lambda x: x.confidence_score, reverse=True)
    if db is not None:
        db.save_matches(results)
    return results
