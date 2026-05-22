from dff_lite.core.Models import FileRecord
from dff_lite.matchers.Base import BaseMatcher


class ExactMatcher(BaseMatcher):
    def match(self, file_a: FileRecord, file_b: FileRecord) -> float:
        if file_a.normalized_name == file_b.normalized_name and file_a.normalized_name:
            return 100.0
        if file_a.filename.lower() == file_b.filename.lower():
            return 95.0
        return 0.0
