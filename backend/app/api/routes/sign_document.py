import uuid
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.core.config import settings
from app.services.placeholder_signer import sign_document_with_placeholder

router = APIRouter(prefix="/api", tags=["sign-document"])


@router.post("/sign-document")
async def sign_document(
    template: UploadFile, signature: UploadFile, date_value: str | None = Form(None)
) -> Response:
    if template.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Template must be a PDF file")
    if signature.content_type != "image/png":
        raise HTTPException(status_code=400, detail="Signature must be a PNG image")

    parsed_date = None
    if date_value:
        try:
            parsed_date = datetime.strptime(date_value, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date_value must be in YYYY-MM-DD format") from exc

    template_bytes = await template.read()
    signature_bytes = await signature.read()

    try:
        signed_pdf = sign_document_with_placeholder(template_bytes, signature_bytes, date_value=parsed_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job_id = uuid.uuid4().hex
    (settings.output_dir / f"{job_id}.pdf").write_bytes(signed_pdf)

    return Response(
        content=signed_pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="signed-{job_id}.pdf"',
            "X-Job-Id": job_id,
        },
    )
