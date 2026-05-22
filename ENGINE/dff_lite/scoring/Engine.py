# scoring/engine.py — Weighted multi-algorithm confidence engine
"""Combines enabled matchers with YAML weights into a 0–100 confidence score."""

from __future__ import annotations

from typing import Dict, Optional

from dff_lite.core.Models import AppConfig, FileRecord, MatchResult
from dff_lite.matchers.Char_Freq import CharFreqMatcher
from dff_lite.matchers.Exact import ExactMatcher
from dff_lite.matchers.Extension import ExtensionMatcher, get_extension_category
from dff_lite.matchers.Folder import FolderMatcher
from dff_lite.matchers.Fuzzy import FuzzyMatcher
from dff_lite.matchers.Ngram import NgramMatcher
from dff_lite.matchers.Numeric import NumericMatcher, REJECT_SCORE
from dff_lite.matchers.Semantic import HAS_SENTENCE_TRANSFORMERS, SemanticMatcher
from dff_lite.matchers.Size import SizeMatcher
from dff_lite.matchers.Token import TokenMatcher

WEIGHT_KEY_MAP = {
    "exact_match": "exact_match",
    "token_similarity": "token_similarity",
    "fuzzy_similarity": "fuzzy_similarity",
    "ngram_similarity": "ngram_similarity",
    "char_frequency": "char_frequency",
    "size_similarity": "size_similarity",
    "numeric_validation": "numeric_validation",
    "semantic_similarity": "semantic_similarity",
}


class ScoringEngine:
    def __init__(self, config: AppConfig):
        self.config = config
        self._matchers = {
            "exact_match": ExactMatcher(),
            "token_similarity": TokenMatcher(),
            "fuzzy_similarity": FuzzyMatcher(),
            "ngram_similarity": NgramMatcher(),
            "char_frequency": CharFreqMatcher(),
            "size_similarity": SizeMatcher(),
            "numeric_validation": NumericMatcher(),
        }
        if HAS_SENTENCE_TRANSFORMERS:
            self._matchers["semantic_similarity"] = SemanticMatcher()
        self._extension = ExtensionMatcher()
        self._folder = FolderMatcher()

    def get_category(self, score: float) -> str:
        t = self.config.thresholds
        if score >= t.almost_certain:
            return "almost certain duplicate"
        if score >= t.highly_likely:
            return "highly likely"
        if score >= t.potential:
            return "potential duplicate"
        if score >= t.weak:
            return "weak similarity"
        return "ignore"

    def _is_enabled(self, name: str) -> bool:
        return bool(getattr(self.config.algorithms, name, True))

    def _weight(self, name: str) -> float:
        return float(getattr(self.config.weights, name, 0.0))

    def compute_match(self, file_a: FileRecord, file_b: FileRecord) -> Optional[MatchResult]:
        if not self._is_enabled("extension_intelligence"):
            ext_score = 100.0
        else:
            ext_score = self._extension.match(file_a, file_b)
            if ext_score == 0.0:
                return None

        scores: Dict[str, float] = {}
        weighted_sum = 0.0
        total_weight = 0.0

        if self._is_enabled("numeric_validation"):
            num_score = self._matchers["numeric_validation"].match(file_a, file_b)
            scores["numeric_validation"] = num_score
            if num_score == REJECT_SCORE:
                return None

        for name, matcher in self._matchers.items():
            if not self._is_enabled(name):
                continue
            if name == "semantic_similarity" and not HAS_SENTENCE_TRANSFORMERS:
                continue

            weight = self._weight(name)
            if weight <= 0:
                continue

            raw = matcher.match(file_a, file_b)
            if name == "numeric_validation":
                raw = max(0.0, raw)
            scores[name] = raw
            weighted_sum += raw * weight
            total_weight += weight

        if total_weight == 0:
            return None

        confidence = weighted_sum / total_weight

        if self._is_enabled("folder_context"):
            folder_sim = self._folder.match(file_a, file_b)
            fw = self._weight("folder_context")
            if fw > 0:
                scores["folder_context"] = folder_sim
                confidence = (confidence * total_weight + folder_sim * fw) / (total_weight + fw)
            elif folder_sim == 100.0:
                confidence = min(100.0, confidence + 5.0)
            elif folder_sim >= 90.0:
                confidence = min(100.0, confidence + 3.0)

        if ext_score == 90.0:
            confidence = max(0.0, confidence - 2.0)

        confidence = round(confidence, 2)
        if confidence < self.config.thresholds.weak:
            return None

        return MatchResult(
            path_a=file_a.path,
            path_b=file_b.path,
            file_a_size=file_a.size,
            file_b_size=file_b.size,
            scores=scores,
            confidence_score=confidence,
            category=self.get_category(confidence),
        )


def extension_category_fn(ext: str) -> str:
    return get_extension_category(ext)
