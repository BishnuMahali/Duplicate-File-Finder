import math
from collections import Counter

from dff_lite.core.Models import FileRecord
from dff_lite.matchers.Base import BaseMatcher


class CharFreqMatcher(BaseMatcher):
    """Cosine similarity of letter frequency vectors."""

    def match(self, file_a: FileRecord, file_b: FileRecord) -> float:
        s1 = "".join(c for c in file_a.normalized_name if c.isalnum())
        s2 = "".join(c for c in file_b.normalized_name if c.isalnum())
        if not s1 or not s2:
            return 100.0 if s1 == s2 else 0.0

        ca, cb = Counter(s1), Counter(s2)
        chars = set(ca) | set(cb)
        dot = sum(ca[c] * cb[c] for c in chars)
        mag_a = math.sqrt(sum(v * v for v in ca.values()))
        mag_b = math.sqrt(sum(v * v for v in cb.values()))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return round((dot / (mag_a * mag_b)) * 100.0, 2)
