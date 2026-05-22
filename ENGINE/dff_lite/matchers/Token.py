from dff_lite.core.Models import FileRecord
from dff_lite.matchers.Base import BaseMatcher


class TokenMatcher(BaseMatcher):
    """Jaccard and Dice coefficient on token sets."""

    def match(self, file_a: FileRecord, file_b: FileRecord) -> float:
        set_a = set(file_a.tokens)
        set_b = set(file_b.tokens)
        if not set_a and not set_b:
            return 100.0 if file_a.normalized_name == file_b.normalized_name else 0.0
        if not set_a or not set_b:
            return 0.0

        inter = set_a & set_b
        union = set_a | set_b
        jaccard = len(inter) / len(union) if union else 0.0
        dice = (2.0 * len(inter)) / (len(set_a) + len(set_b))
        return round(((jaccard + dice) / 2.0) * 100.0, 2)
