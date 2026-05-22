from dff_lite.core.Models import FileRecord
from dff_lite.matchers.Base import BaseMatcher


class SizeMatcher(BaseMatcher):
    def match(self, file_a: FileRecord, file_b: FileRecord) -> float:
        a, b = file_a.size, file_b.size
        if a == b:
            return 100.0
        mx = max(a, b)
        if mx == 0:
            return 100.0
        diff = abs(a - b) / mx
        if diff <= 0.02:
            return 90.0
        if diff <= 0.05:
            return 75.0
        if diff <= 0.10:
            return 50.0
        if diff <= 0.25:
            return 25.0
        return 0.0
