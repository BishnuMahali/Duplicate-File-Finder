import difflib

from dff_lite.core.Models import FileRecord
from dff_lite.matchers.Base import BaseMatcher

try:
    from rapidfuzz import fuzz

    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False


class FuzzyMatcher(BaseMatcher):
    """Levenshtein-based ratios via RapidFuzz (ratio, partial, token_sort, token_set)."""

    def match(self, file_a: FileRecord, file_b: FileRecord) -> float:
        s1, s2 = file_a.normalized_name, file_b.normalized_name
        if not s1 or not s2:
            return 100.0 if s1 == s2 else 0.0

        if HAS_RAPIDFUZZ:
            ratio = fuzz.ratio(s1, s2)
            partial = fuzz.partial_ratio(s1, s2)
            token_sort = fuzz.token_sort_ratio(s1, s2)
            token_set = fuzz.token_set_ratio(s1, s2)
            score = ratio * 0.25 + partial * 0.2 + token_sort * 0.25 + token_set * 0.3
            return round(score, 2)

        return round(difflib.SequenceMatcher(None, s1, s2).ratio() * 100.0, 2)
