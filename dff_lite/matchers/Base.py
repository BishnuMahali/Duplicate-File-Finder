from abc import ABC, abstractmethod

from dff_lite.core.Models import FileRecord


class BaseMatcher(ABC):
    @abstractmethod
    def match(self, file_a: FileRecord, file_b: FileRecord) -> float:
        """Return similarity 0.0–100.0 (or -100.0 for hard reject from numeric matcher)."""
