import re
from pathlib import Path

from dff_lite.core.Models import FileRecord
from dff_lite.matchers.Base import BaseMatcher
from dff_lite.normalizer.Normalizer import clean_repeated_spaces


class FolderMatcher(BaseMatcher):
    def match(self, file_a: FileRecord, file_b: FileRecord) -> float:
        parent_a = Path(file_a.path).parent
        parent_b = Path(file_b.path).parent
        if parent_a == parent_b:
            return 100.0

        def clean(name: str) -> str:
            return clean_repeated_spaces(re.sub(r"[\._\-\[\]\(\)\{\}]", " ", name.lower()))

        da, db = clean(parent_a.name), clean(parent_b.name)
        if da == db and da:
            return 90.0
        if da and db and (da in db or db in da):
            return 80.0
        return 50.0
