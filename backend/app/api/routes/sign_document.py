import uuid
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.core.config import settings
from app.core.limits import MAX_SIGNATURE_SIZE, MAX_TEMPLATE_SIZE, read_within_limit
from app.services.pdf_merge import merge_pdfs
from app.services.placeholder_signer import sign_document_with_placeholder

router = APIRouter(prefix="/api", tags=["sign-document"])


@router.post("/sign-document")
async def sign_document(
    templates: list[UploadFile] = File(...),
    signature: UploadFile = File(...),
    date_value: str | None = Form(None),
    require_date: bool = Form(True),
) -> Response:
    if not templates:
        raise HTTPException(status_code=400, detail="At least one template is required")
    for template in templates:
        if template.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Every template must be a PDF file")
    if signature.content_type != "image/png":
        raise HTTPException(status_code=400, detail="Signature must be a PNG image")

    parsed_date = None
    if date_value:
        try:
            parsed_date = datetime.strptime(date_value, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date_value must be in YYYY-MM-DD format") from exc

    signature_bytes = await read_within_limit(signature, MAX_SIGNATURE_SIZE, "Signature")

    signed_pdfs: list[bytes] = []
    for template in templates:
        template_bytes = await read_within_limit(template, MAX_TEMPLATE_SIZE, f"Template '{template.filename}'")
        try:
            signed_pdfs.append(
                sign_document_with_placeholder(
                    template_bytes, signature_bytes, date_value=parsed_date, require_date=require_date
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"{template.filename}: {exc}") from exc

    merged_pdf = merge_pdfs(signed_pdfs)

    job_id = uuid.uuid4().hex
    (settings.output_dir / f"{job_id}.pdf").write_bytes(merged_pdf)

    return Response(
        content=merged_pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="signed-{job_id}.pdf"',
            "X-Job-Id": job_id,
        },
    )
