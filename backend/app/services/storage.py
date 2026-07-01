import uuid
from pathlib import Path


def save_bytes(content: bytes, original_filename: str | None, directory: Path) -> tuple[str, Path]:
    """Saves `content` under `directory` using a generated id as the filename
    stem, preserving the extension from `original_filename`. Returns (id, path).
    """
    file_id = uuid.uuid4().hex
    suffix = Path(original_filename or "").suffix
    dest = directory / f"{file_id}{suffix}"
    dest.write_bytes(content)
    return file_id, dest


def find_by_id(directory: Path, file_id: str) -> Path | None:
    matches = list(directory.glob(f"{file_id}.*"))
    return matches[0] if matches else None
