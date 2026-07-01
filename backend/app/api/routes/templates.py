from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.limits import MAX_TEMPLATE_SIZE, read_within_limit
from app.models.schemas import UploadedFile
from app.services.storage import find_by_id, save_bytes

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.post("", response_model=UploadedFile)
async def upload_template(file: UploadFile) -> UploadedFile:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Template must be a PDF file")
    content = await read_within_limit(file, MAX_TEMPLATE_SIZE, "Template")
    file_id, _ = save_bytes(content, file.filename, settings.templates_dir)
    return UploadedFile(id=file_id, filename=file.filename or "", url=f"/api/templates/{file_id}")


@router.get("", response_model=list[UploadedFile])
async def list_templates() -> list[UploadedFile]:
    return [
        UploadedFile(id=p.stem, filename=p.name, url=f"/api/templates/{p.stem}")
        for p in sorted(settings.templates_dir.iterdir())
    ]


@router.get("/{template_id}")
async def get_template(template_id: str) -> FileResponse:
    path = find_by_id(settings.templates_dir, template_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return FileResponse(path)
