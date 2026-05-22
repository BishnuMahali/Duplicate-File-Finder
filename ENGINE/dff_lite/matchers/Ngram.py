from dff_lite.core.Models import FileRecord
from dff_lite.matchers.Base import BaseMatcher


def character_ngrams(text: str, n: int) -> set:
    if len(text) < n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


class NgramMatcher(BaseMatcher):
    """Bi-gram and tri-gram Jaccard similarity."""

    def match(self, file_a: FileRecord, file_b: FileRecord) -> float:
        s1, s2 = file_a.normalized_name, file_b.normalized_name
        if not s1 or not s2:
            return 100.0 if s1 == s2 else 0.0

        bg_a, bg_b = character_ngrams(s1, 2), character_ngrams(s2, 2)
        tg_a, tg_b = character_ngrams(s1, 3), character_ngrams(s2, 3)

        def jaccard(a: set, b: set) -> float:
            u = a | b
            return len(a & b) / len(u) if u else 0.0

        score = (jaccard(bg_a, bg_b) + jaccard(tg_a, tg_b)) / 2.0
        return round(score * 100.0, 2)
