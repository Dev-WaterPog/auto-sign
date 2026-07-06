import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.models.schemas import SignBatchRequest, SignRequest, SignResult
from app.services.pdf_merge import merge_pdfs
from app.services.pdf_signer import sign_pdf
from app.services.storage import find_by_id

router = APIRouter(prefix="/api/sign", tags=["sign"])


def _parse_date_value(date_value: str | None) -> datetime | None:
    if not date_value:
        return None
    try:
        return datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date_value must be in YYYY-MM-DD format") from exc


@router.post("", response_model=SignResult)
async def create_signed_document(request: SignRequest) -> SignResult:
    template_path = find_by_id(settings.templates_dir, request.template_id)
    if template_path is None:
        raise HTTPException(status_code=404, detail="Template not found")

    signature_path = find_by_id(settings.signatures_dir, request.signature_id)
    if signature_path is None:
        raise HTTPException(status_code=404, detail="Signature not found")

    date_value = _parse_date_value(request.date_value)

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
        require_date=request.require_date,
    )

    return SignResult(
        job_id=job_id,
        download_url=f"/api/sign/{job_id}/download",
        signature_placed=signature_placed,
        date_placed=date_placed,
    )


@router.post("/batch", response_model=SignResult)
async def create_signed_document_batch(request: SignBatchRequest) -> SignResult:
    if not request.template_ids:
        raise HTTPException(status_code=400, detail="At least one template is required")

    signature_path = find_by_id(settings.signatures_dir, request.signature_id)
    if signature_path is None:
        raise HTTPException(status_code=404, detail="Signature not found")

    date_value = _parse_date_value(request.date_value)

    job_id = uuid.uuid4().hex
    part_paths: list[Path] = []
    signature_placed = True
    date_placed = True
    try:
        for index, template_id in enumerate(request.template_ids):
            template_path = find_by_id(settings.templates_dir, template_id)
            if template_path is None:
                raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")

            part_path = settings.output_dir / f"{job_id}_{index}.pdf"
            part_signature_placed, part_date_placed = sign_pdf(
                template_path=template_path,
                signature_path=signature_path,
                output_path=part_path,
                signature_anchor_pattern=request.signature_anchor or settings.default_signature_anchor,
                date_anchor_pattern=request.date_anchor or settings.default_date_anchor,
                date_format=request.date_format,
                signature_position=request.signature_position,
                date_value=date_value,
                require_date=request.require_date,
            )
            signature_placed = signature_placed and part_signature_placed
            date_placed = date_placed and part_date_placed
            part_paths.append(part_path)

        merged_pdf = merge_pdfs([p.read_bytes() for p in part_paths])
        (settings.output_dir / f"{job_id}.pdf").write_bytes(merged_pdf)
    finally:
        for part_path in part_paths:
            part_path.unlink(missing_ok=True)

    return SignResult(
        job_id=job_id,
        download_url=f"/api/sign/{job_id}/download",
        signature_placed=signature_placed,
        date_placed=date_placed if request.require_date else True,
    )


@router.get("/{job_id}/download")
async def download_signed_document(job_id: str) -> FileResponse:
    path = settings.output_dir / f"{job_id}.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Signed document not found")
    return FileResponse(path, media_type="application/pdf", filename=f"signed-{job_id}.pdf")
