from dff_lite.core.Models import FileRecord
from dff_lite.matchers.Base import BaseMatcher

EXTENSION_CATEGORIES = {
    "video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".mpg", ".m4v", ".ts", ".m2ts"},
    "audio": {".mp3", ".flac", ".wav", ".aac", ".m4a", ".wma", ".ogg", ".ape", ".opus"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".heic"},
    "document": {".txt", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".md", ".json", ".yaml", ".yml"},
}


def get_extension_category(ext: str) -> str:
    ext_lower = ext.lower()
    for cat, extensions in EXTENSION_CATEGORIES.items():
        if ext_lower in extensions:
            return cat
    return "other"


class ExtensionMatcher(BaseMatcher):
    def match(self, file_a: FileRecord, file_b: FileRecord) -> float:
        if file_a.extension == file_b.extension:
            return 100.0
        if get_extension_category(file_a.extension) == get_extension_category(file_b.extension):
            cat = get_extension_category(file_a.extension)
            return 90.0 if cat != "other" else 50.0
        return 0.0
