from fastapi import HTTPException, UploadFile

MAX_SIGNATURE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_TEMPLATE_SIZE = 25 * 1024 * 1024  # 25 MB


async def read_within_limit(file: UploadFile, max_size: int, label: str) -> bytes:
    """Reads at most `max_size + 1` bytes so an oversized upload is rejected
    without ever buffering the whole (potentially huge) file in memory.
    """
    content = await file.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"{label} exceeds the {max_size // (1024 * 1024)} MB limit")
    return content
