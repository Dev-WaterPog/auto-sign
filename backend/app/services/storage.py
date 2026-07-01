import uuid
from pathlib import Path

from fastapi import UploadFile


def save_upload(file: UploadFile, directory: Path) -> tuple[str, Path]:
    """Saves an UploadFile under `directory` using a generated id as the
    filename stem, preserving the original extension. Returns (id, path).
    """
    file_id = uuid.uuid4().hex
    suffix = Path(file.filename or "").suffix
    dest = directory / f"{file_id}{suffix}"
    with dest.open("wb") as out:
        out.write(file.file.read())
    return file_id, dest


def find_by_id(directory: Path, file_id: str) -> Path | None:
    matches = list(directory.glob(f"{file_id}.*"))
    return matches[0] if matches else None
