import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.models.schemas import SignRequest, SignResult
from app.services.pdf_signer import sign_pdf
from app.services.storage import find_by_id

router = APIRouter(prefix="/api/sign", tags=["sign"])


@router.post("", response_model=SignResult)
async def create_signed_document(request: SignRequest) -> SignResult:
    template_path = find_by_id(settings.templates_dir, request.template_id)
    if template_path is None:
        raise HTTPException(status_code=404, detail="Template not found")

    signature_path = find_by_id(settings.signatures_dir, request.signature_id)
    if signature_path is None:
        raise HTTPException(status_code=404, detail="Signature not found")

    date_value = None
    if request.date_value:
        try:
            date_value = datetime.strptime(request.date_value, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date_value must be in YYYY-MM-DD format") from exc

    job_id = uuid.uuid4().hex
    output_path = settings.output_dir / f"{job_id}.pdf"

    signature_placed, date_placed = sign_pdf(
        template_path=template_path,
        signature_path=signature_path,
        output_path=output_path,
        signature_anchor_pattern=request.signature_anchor or settings.default_signature_anchor,
        date_anchor_pattern=request.date_anchor or settings.default_date_anchor,
        date_format=request.date_format,
        signature_position=request.signature_position,
        date_value=date_value,
    )

    return SignResult(
        job_id=job_id,
        download_url=f"/api/sign/{job_id}/download",
        signature_placed=signature_placed,
        date_placed=date_placed,
    )


@router.get("/{job_id}/download")
async def download_signed_document(job_id: str) -> FileResponse:
    path = settings.output_dir / f"{job_id}.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Signed document not found")
    return FileResponse(path, media_type="application/pdf", filename=f"signed-{job_id}.pdf")
