# core.Models.py — Pydantic data models for DFF Lite Cursor
"""Strongly typed domain models used across the pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class FileRecord(BaseModel):
    """Metadata and normalized fields for one scanned file."""

    path: str
    filename: str
    extension: str
    size: int
    mtime: float
    parent_folder: str
    normalized_name: str
    tokens: List[str] = Field(default_factory=list)
    token_signature: str = ""
    length_bucket: int = 0
    extension_category: str = "other"


class MatchResult(BaseModel):
    """Pairwise similarity result with per-algorithm breakdown."""

    path_a: str
    path_b: str
    file_a_size: int
    file_b_size: int
    scores: Dict[str, float] = Field(default_factory=dict)
    confidence_score: float
    category: str


class ScanConfig(BaseModel):
    include_extensions: List[str] = Field(default_factory=list)
    exclude_folders: List[str] = Field(default_factory=list)
    multithreading: bool = True
    max_workers: int = 8
    batch_size: int = 500


class NormalizationConfig(BaseModel):
    lowercase: bool = True
    remove_punctuation: bool = True
    replace_separators: bool = True
    remove_stop_words: bool = True
    strip_hashes: bool = True
    remove_patterns: List[str] = Field(default_factory=list)


class AlgorithmsConfig(BaseModel):
    """Enable or disable individual matchers in the scoring.Pipeline."""

    exact_match: bool = True
    token_similarity: bool = True
    fuzzy_similarity: bool = True
    ngram_similarity: bool = True
    char_frequency: bool = True
    size_similarity: bool = True
    numeric_validation: bool = True
    extension_intelligence: bool = True
    folder_context: bool = True
    semantic_similarity: bool = False


class WeightsConfig(BaseModel):
    exact_match: float = 40.0
    token_similarity: float = 20.0
    fuzzy_similarity: float = 15.0
    ngram_similarity: float = 10.0
    char_frequency: float = 5.0
    size_similarity: float = 5.0
    numeric_validation: float = 5.0
    extension_intelligence: float = 0.0
    folder_context: float = 0.0
    semantic_similarity: float = 10.0


class ThresholdsConfig(BaseModel):
    almost_certain: float = 95.0
    highly_likely: float = 80.0
    potential: float = 60.0
    weak: float = 40.0


class BlockingConfig(BaseModel):
    """Pre-grouping limits to avoid O(N²) comparisons."""

    max_block_size: int = 500
    min_token_length: int = 3
    prefix_length: int = 4
    use_extension_category: bool = True
    use_length_bucket: bool = True
    use_token_signature: bool = True


class DatabaseConfig(BaseModel):
    db_path: str = "TEMP/dff_lite.db"
    use_cache: bool = True


class AppConfig(BaseModel):
    scan: ScanConfig = Field(default_factory=ScanConfig)
    normalization: NormalizationConfig = Field(default_factory=NormalizationConfig)
    algorithms: AlgorithmsConfig = Field(default_factory=AlgorithmsConfig)
    weights: WeightsConfig = Field(default_factory=WeightsConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    blocking: BlockingConfig = Field(default_factory=BlockingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
