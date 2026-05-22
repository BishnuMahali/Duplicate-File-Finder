# normalizer.Normalizer.py — Aggressive filename normalization engine
"""
Strips scene/release tags, codecs, resolutions, hashes, and punctuation noise.
Example: "The.Dark.Knight.2008.1080p.BluRay.x264-YIFY" -> "the dark knight 2008"
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from dff_lite.core.Models import NormalizationConfig

STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "but", "is", "are", "was", "were", "this", "that",
})

# Built-in patterns always applied before YAML custom rules
BUILTIN_STRIP_PATTERNS: List[str] = [
    r"\b(1080p|720p|2160p|1440p|4k|8k|480p|360p|240p)\b",
    r"\b(uhd|fhd|hd|sd)\b",
    r"\b(h264|h265|x264|x265|hevc|avc|divx|xvid|vp9|av1)\b",
    r"\b(bluray|blu\s*ray|bdrip|brrip|webrip|web\s*rip|webdl|web\s*dl|dvdrip|hdtv|cam|ts|tc)\b",
    r"\b(aac|mp3|dts|dd5\.1|ac3|atmos|truehd|flac|opus)\b",
    r"\b(hdr|dv|hdr10|hdr10plus|dolby\s*vision|sdr)\b",
    r"\b(rarbg|yify|yts|sparks|amiable|ettv|eztv|fgt|ion10|dimension|proper|repack)\b",
    r"\b(extended|remastered|unrated|directors?\s*cut|imax|limited|internal|readnfo)\b",
    r"\b(proper|repack|rerip|dual|audio|multi|subs?)\b",
    r"\b\d{3,4}p\b",
    r"\b\d{1,2}bit\b",
    r"\b\d+ch\b",
    r"\b\d+fps\b",
    r"\b\d+gb\b",
    r"\b\d+mb\b",
]

HASH_PATTERN = re.compile(
    r"\b[a-f0-9]{8,64}\b|\b[A-F0-9]{8,64}\b|\[[a-f0-9]{6,}\]",
    re.IGNORECASE,
)

RELEASE_GROUP_SUFFIX = re.compile(
    r"[-\.](yify|yts|rarbg|ettv|sparks|amiable|fgt|ion10|dimension|rarbg|publichd)\b",
    re.IGNORECASE,
)


def clean_repeated_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _apply_patterns(stem: str, patterns: List[str]) -> str:
    for pattern in patterns:
        try:
            stem = re.sub(pattern, " ", stem, flags=re.IGNORECASE)
        except re.error:
            continue
    return stem


def normalize_filename(filename: str, config: NormalizationConfig) -> Tuple[str, List[str]]:
    stem = Path(filename).stem

    if config.lowercase:
        stem = stem.lower()

    if config.replace_separators:
        stem = re.sub(r"[\._\-\[\]\(\)\{\}\+\=\+]", " ", stem)

    if config.strip_hashes:
        stem = HASH_PATTERN.sub(" ", stem)
        stem = RELEASE_GROUP_SUFFIX.sub(" ", stem)

    stem = _apply_patterns(stem, BUILTIN_STRIP_PATTERNS)
    stem = _apply_patterns(stem, config.remove_patterns)

    if config.remove_punctuation:
        stem = re.sub(r"[^\w\s]", " ", stem)

    normalized = clean_repeated_spaces(stem)

    tokens: List[str] = []
    for token in normalized.split():
        if not token:
            continue
        if config.remove_stop_words and token in STOP_WORDS:
            continue
        if len(token) == 1 and not token.isdigit():
            continue
        tokens.append(token)

    if tokens:
        normalized = " ".join(tokens)

    return normalized, tokens
