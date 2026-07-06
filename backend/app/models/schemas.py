from typing import Literal

from pydantic import BaseModel


class UploadedFile(BaseModel):
    id: str
    filename: str
    url: str


class SignRequest(BaseModel):
    template_id: str
    signature_id: str
    signature_anchor: str | None = None
    date_anchor: str | None = None
    date_format: str = "%d/%m/%Y"
    signature_position: Literal["right", "above", "below"] = "right"
    date_value: str | None = None  # ISO "YYYY-MM-DD"; defaults to today when omitted
    require_date: bool = True  # set false for templates with no date field to stamp


class SignBatchRequest(BaseModel):
    template_ids: list[str]
    signature_id: str
    signature_anchor: str | None = None
    date_anchor: str | None = None
    date_format: str = "%d/%m/%Y"
    signature_position: Literal["right", "above", "below"] = "right"
    date_value: str | None = None  # ISO "YYYY-MM-DD"; defaults to today when omitted
    require_date: bool = True  # set false for templates with no date field to stamp


class SignResult(BaseModel):
    job_id: str
    download_url: str
    signature_placed: bool
    date_placed: bool
