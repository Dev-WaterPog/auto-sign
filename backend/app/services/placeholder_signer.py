"""Finds the literal `{{signature}}` placeholder in a PDF via regex and stamps
a signature image plus today's date over it."""

import re
from collections import defaultdict
from datetime import datetime

import fitz  # PyMuPDF

from app.services.fonts import DATE_FONT_NAME, DATE_FONT_PATH

SIGNATURE_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*signature\s*\}\}", re.IGNORECASE)
SIGNATURE_TARGET_WIDTH = 130  # points
DATE_GAP = 4  # points between the signature image and the date text
DATE_FONT_SIZE = 10


def _find_placeholder_rects(
    doc: "fitz.Document", pattern: re.Pattern[str]
) -> dict[int, list["fitz.Rect"]]:
    matches: dict[int, list[fitz.Rect]] = defaultdict(list)
    for page_index, page in enumerate(doc):
        for x0, y0, x1, y1, word, *_ in page.get_text("words"):
            if pattern.search(word):
                matches[page_index].append(fitz.Rect(x0, y0, x1, y1))
    return matches


def sign_document_with_placeholder(
    template_bytes: bytes,
    signature_bytes: bytes,
    placeholder_pattern: re.Pattern[str] = SIGNATURE_PLACEHOLDER_PATTERN,
    date_format: str = "%d/%m/%Y",
    date_value: datetime | None = None,
    require_date: bool = True,
) -> bytes:
    """Returns the signed PDF as bytes. `date_value` defaults to today when
    not given. Set `require_date=False` for templates with no date field —
    only the signature image is stamped. Raises ValueError if the
    placeholder is not found anywhere in the document.
    """
    doc = fitz.open(stream=template_bytes, filetype="pdf")
    placeholders_by_page = _find_placeholder_rects(doc, placeholder_pattern)
    if not placeholders_by_page:
        doc.close()
        raise ValueError("Placeholder '{{signature}}' was not found in the PDF")

    sig_pixmap = fitz.Pixmap(signature_bytes)
    sig_width = SIGNATURE_TARGET_WIDTH
    sig_height = sig_width * (sig_pixmap.height / sig_pixmap.width)

    today_str = (date_value or datetime.now()).strftime(date_format)

    for page_index, rects in placeholders_by_page.items():
        page = doc[page_index]
        for rect in rects:
            page.add_redact_annot(rect)
        page.apply_redactions()

        for rect in rects:
            sig_rect = fitz.Rect(rect.x0, rect.y0, rect.x0 + sig_width, rect.y0 + sig_height)
            page.insert_image(sig_rect, stream=signature_bytes, keep_proportion=True)
            if require_date:
                page.insert_text(
                    (rect.x0, sig_rect.y1 + DATE_GAP + DATE_FONT_SIZE),
                    today_str,
                    fontsize=DATE_FONT_SIZE,
                    fontname=DATE_FONT_NAME,
                    fontfile=str(DATE_FONT_PATH),
                )

    output = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return output
