from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.limits import MAX_SIGNATURE_SIZE, read_within_limit
from app.models.schemas import UploadedFile
from app.services.storage import find_by_id, save_bytes

router = APIRouter(prefix="/api/signatures", tags=["signatures"])

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg"}


@router.post("", response_model=UploadedFile)
async def upload_signature(file: UploadFile) -> UploadedFile:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Signature must be a PNG or JPEG image")
    content = await read_within_limit(file, MAX_SIGNATURE_SIZE, "Signature")
    file_id, _ = save_bytes(content, file.filename, settings.signatures_dir)
    return UploadedFile(id=file_id, filename=file.filename or "", url=f"/api/signatures/{file_id}")


@router.get("", response_model=list[UploadedFile])
async def list_signatures() -> list[UploadedFile]:
    return [
        UploadedFile(id=p.stem, filename=p.name, url=f"/api/signatures/{p.stem}")
        for p in sorted(settings.signatures_dir.iterdir())
    ]


@router.get("/{signature_id}")
async def get_signature(signature_id: str) -> FileResponse:
    path = find_by_id(settings.signatures_dir, signature_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Signature not found")
    return FileResponse(path)
