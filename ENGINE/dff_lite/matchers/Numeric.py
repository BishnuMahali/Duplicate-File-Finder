import re

from dff_lite.core.Models import FileRecord
from dff_lite.matchers.Base import BaseMatcher

REJECT_SCORE = -100.0


class NumericMatcher(BaseMatcher):
    """Years, episodes, and sequence numbers — boost match or hard-reject conflicts."""

    def extract_years(self, text: str) -> set:
        return set(re.findall(r"\b(19\d{2}|20\d{2})\b", text))

    def extract_episodes(self, text: str) -> set:
        normalized = text.lower()
        results: set = set()
        for m in re.findall(r"s(\d+)e(\d+)", normalized):
            results.add(f"s{int(m[0])}e{int(m[1])}")
        for m in re.findall(r"ep[isod]*\s*(\d+)", normalized):
            results.add(f"ep{int(m)}")
        for m in re.findall(r"\b(\d+)x(\d+)\b", normalized):
            results.add(f"s{int(m[0])}e{int(m[1])}")
        return results

    def extract_numbers(self, text: str) -> set:
        return set(re.findall(r"\b(\d+)\b", text))

    def match(self, file_a: FileRecord, file_b: FileRecord) -> float:
        name_a, name_b = file_a.filename, file_b.filename

        eps_a = self.extract_episodes(name_a)
        eps_b = self.extract_episodes(name_b)
        if eps_a and eps_b:
            return REJECT_SCORE if eps_a != eps_b else 100.0

        years_a = self.extract_years(name_a) | self.extract_years(file_a.normalized_name)
        years_b = self.extract_years(name_b) | self.extract_years(file_b.normalized_name)
        if years_a and years_b:
            return REJECT_SCORE if years_a != years_b else 100.0

        nums_a = self.extract_numbers(file_a.normalized_name) - years_a
        nums_b = self.extract_numbers(file_b.normalized_name) - years_b
        if nums_a and nums_b:
            return REJECT_SCORE if nums_a != nums_b else 100.0

        if bool(years_a or eps_a or nums_a) != bool(years_b or eps_b or nums_b):
            return 30.0
        return 100.0
