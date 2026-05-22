from dff_lite.core.Models import FileRecord
from dff_lite.matchers.Base import BaseMatcher

try:
    from sentence_transformers import SentenceTransformer, util

    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


class SemanticMatcher(BaseMatcher):
    """Optional sentence-transformers semantic similarity (e.g. LOTR vs Lord of the Rings)."""

    _model = None
    _cache: dict = {}

    @classmethod
    def get_model(cls):
        if cls._model is None and HAS_SENTENCE_TRANSFORMERS:
            try:
                cls._model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                cls._model = None
        return cls._model

    def _embedding(self, text: str):
        model = self.get_model()
        if not model:
            return None
        if text not in self._cache:
            self._cache[text] = model.encode(text, convert_to_tensor=True)
        return self._cache[text]

    def match(self, file_a: FileRecord, file_b: FileRecord) -> float:
        if not HAS_SENTENCE_TRANSFORMERS:
            return 0.0
        s1, s2 = file_a.normalized_name, file_b.normalized_name
        if not s1 or not s2:
            return 100.0 if s1 == s2 else 0.0
        try:
            emb_a = self._embedding(s1)
            emb_b = self._embedding(s2)
            if emb_a is None or emb_b is None:
                return 0.0
            cos = util.cos_sim(emb_a, emb_b).item()
            return round(max(0.0, min(100.0, cos * 100.0)), 2)
        except Exception:
            return 0.0
