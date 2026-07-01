"""Locates signing anchors in a PDF via regex and stamps a signature image + date onto it."""

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

import fitz  # PyMuPDF

from app.services.fonts import DATE_FONT_NAME, DATE_FONT_PATH

SIGNATURE_BOX_SIZE = (110, 45)  # points (w, h); used only when no anchor is found (bottom-right fallback)
FALLBACK_MARGIN = 36  # points from the page edge when no anchor text is found
ANCHOR_GAP = 4  # points between the anchor text and the stamped signature

# The signature height scales with the matched anchor text's own line height,
# so it looks proportionate whether the anchor is 8pt table text or a 14pt
# heading, then gets clamped to whatever whitespace is actually available
# next to it (see `_available_gap`) so it never overlaps a neighboring line.
SIGNATURE_HEIGHT_MULTIPLIER = 4.0
MIN_SIGNATURE_HEIGHT = 18.0
MAX_SIGNATURE_HEIGHT = 90.0
ABSOLUTE_MIN_SIGNATURE_HEIGHT = 10.0  # last-resort floor when space is very tight

SignaturePosition = Literal["right", "above", "below"]


def _line_rects(page: "fitz.Page") -> list["fitz.Rect"]:
    text_dict = page.get_text("dict")
    rects: list[fitz.Rect] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            rect = fitz.Rect(spans[0]["bbox"])
            for span in spans[1:]:
                rect |= fitz.Rect(span["bbox"])
            rects.append(rect)
    return rects


def _find_all_anchor_rects(page: "fitz.Page", pattern: re.Pattern[str]) -> list["fitz.Rect"]:
    """Returns the rect of every line on the page matching `pattern`. Forms
    commonly repeat a label like "วันที่" once per signature block, so callers
    that care about a specific block should disambiguate by proximity via
    `_find_nearest_anchor_rect` rather than just taking the first result.
    """
    text_dict = page.get_text("dict")
    rects: list[fitz.Rect] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            # Fast path: the anchor text lives entirely within one span.
            matched_span = next((span for span in spans if pattern.search(span["text"])), None)
            if matched_span is not None:
                rects.append(fitz.Rect(matched_span["bbox"]))
                continue
            # Some PDF generators split a single line of text across several
            # spans (font-fallback per glyph, kerning tables, etc.), which
            # would otherwise hide an anchor like "วันที่" from a per-span
            # search. Fall back to matching against the whole line.
            if len(spans) > 1:
                line_text = "".join(span["text"] for span in spans)
                if pattern.search(line_text):
                    rect = fitz.Rect(spans[0]["bbox"])
                    for span in spans[1:]:
                        rect |= fitz.Rect(span["bbox"])
                    rects.append(rect)
    return rects


def _find_anchor_rect(page: "fitz.Page", pattern: re.Pattern[str]) -> "fitz.Rect | None":
    rects = _find_all_anchor_rects(page, pattern)
    return rects[0] if rects else None


def _find_nearest_anchor_rect(
    page: "fitz.Page", pattern: re.Pattern[str], reference: "fitz.Rect"
) -> "fitz.Rect | None":
    """Like `_find_anchor_rect`, but when the pattern matches more than once
    on the page (e.g. a form with several "วันที่" fields, one per signature
    block), picks the occurrence closest to `reference` instead of the first
    one in document order.
    """
    rects = _find_all_anchor_rects(page, pattern)
    if not rects:
        return None

    def distance(rect: "fitz.Rect") -> float:
        cx, cy = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
        rx, ry = (reference.x0 + reference.x1) / 2, (reference.y0 + reference.y1) / 2
        return ((cx - rx) ** 2 + (cy - ry) ** 2) ** 0.5

    return min(rects, key=distance)


def _available_gap(lines: list["fitz.Rect"], anchor: "fitz.Rect", position: SignaturePosition) -> float | None:
    """Vertical space between the anchor and the nearest other line of text
    in the stamping direction, or None if there's no such line to avoid."""

    def overlaps_horizontally(rect: "fitz.Rect") -> bool:
        return rect.x1 > anchor.x0 and rect.x0 < anchor.x1

    if position == "above":
        edges = [ln.y1 for ln in lines if ln.y1 <= anchor.y0 + 0.5 and overlaps_horizontally(ln)]
        return anchor.y0 - max(edges) if edges else None
    if position == "below":
        edges = [ln.y0 for ln in lines if ln.y0 >= anchor.y1 - 0.5 and overlaps_horizontally(ln)]
        return min(edges) - anchor.y1 if edges else None
    return None


def _signature_box_size(
    anchor: "fitz.Rect", signature_path: Path, max_height: float | None = None
) -> tuple[float, float]:
    pix = fitz.Pixmap(str(signature_path))
    aspect_ratio = pix.width / pix.height
    height = min(max(anchor.height * SIGNATURE_HEIGHT_MULTIPLIER, MIN_SIGNATURE_HEIGHT), MAX_SIGNATURE_HEIGHT)
    if max_height is not None:
        height = min(height, max(max_height, ABSOLUTE_MIN_SIGNATURE_HEIGHT))
    return height * aspect_ratio, height


def _find_underline_near(page: "fitz.Page", anchor: "fitz.Rect") -> "fitz.Rect | None":
    """Finds the blank underline of a form field (e.g. "วันที่ ______") to
    the right of `anchor` on roughly the same baseline, so text can be
    centered within it instead of just following the label.
    """
    best: fitz.Rect | None = None
    best_distance: float | None = None
    for path in page.get_drawings():
        rect = path["rect"]
        if rect.width < 10 or rect.height > 3:  # a horizontal rule is wide and very thin
            continue
        if rect.x0 < anchor.x1 - 2:
            continue
        if not (anchor.y0 - 6 <= rect.y0 <= anchor.y1 + 10):
            continue
        distance = rect.x0 - anchor.x1
        if best_distance is None or distance < best_distance:
            best, best_distance = rect, distance
    return best


_DATE_FONT = fitz.Font(fontfile=str(DATE_FONT_PATH))


def _centered_text_x(line: "fitz.Rect", text: str, fontsize: float) -> float:
    text_width = _DATE_FONT.text_length(text, fontsize=fontsize)
    return max(line.x0, line.x0 + (line.width - text_width) / 2)


def _stamp_date(page: "fitz.Page", anchor: "fitz.Rect", text: str, fontsize: float = 10) -> None:
    underline = _find_underline_near(page, anchor)
    if underline is not None:
        x = _centered_text_x(underline, text, fontsize)
        y = underline.y0 - 2
    else:
        x, y = anchor.x1 + 5, anchor.y1 - 2
    page.insert_text((x, y), text, fontsize=fontsize, fontname=DATE_FONT_NAME, fontfile=str(DATE_FONT_PATH))


def _signature_rect(anchor: "fitz.Rect", position: SignaturePosition, box_size: tuple[float, float]) -> "fitz.Rect":
    w, h = box_size
    if position == "above":
        cx = (anchor.x0 + anchor.x1) / 2
        return fitz.Rect(cx - w / 2, anchor.y0 - ANCHOR_GAP - h, cx + w / 2, anchor.y0 - ANCHOR_GAP)
    if position == "below":
        cx = (anchor.x0 + anchor.x1) / 2
        return fitz.Rect(cx - w / 2, anchor.y1 + ANCHOR_GAP, cx + w / 2, anchor.y1 + ANCHOR_GAP + h)
    # "right" (default): vertically centered on the anchor's left-to-right baseline
    return fitz.Rect(anchor.x1 + 5, anchor.y0 - h / 2, anchor.x1 + 5 + w, anchor.y0 + h / 2)


def _sign_page(
    page: "fitz.Page",
    sig_regex: re.Pattern[str],
    date_regex: re.Pattern[str],
    signature_path: Path,
    signature_position: SignaturePosition,
    today_str: str,
) -> tuple[bool, bool]:
    """Stamps the signature (and its nearest date label) onto `page` if the
    signature anchor matches there. Returns (signature_placed, date_placed)
    for this page only.
    """
    anchor = _find_anchor_rect(page, sig_regex)
    if anchor is None:
        return False, False

    gap = _available_gap(_line_rects(page), anchor, signature_position)
    max_height = (gap - 2 * ANCHOR_GAP) if gap is not None else None
    box_size = _signature_box_size(anchor, signature_path, max_height)
    rect = _signature_rect(anchor, signature_position, box_size)
    page.insert_image(rect, filename=str(signature_path), keep_proportion=True)

    # Forms often repeat the date label once per signature block, so prefer
    # the occurrence closest to wherever the signature landed on this page
    # over the first one in the document.
    date_placed = False
    date_anchor = _find_nearest_anchor_rect(page, date_regex, anchor)
    if date_anchor is not None:
        _stamp_date(page, date_anchor, today_str)
        date_placed = True
    return True, date_placed


def sign_pdf(
    template_path: Path,
    signature_path: Path,
    output_path: Path,
    signature_anchor_pattern: str,
    date_anchor_pattern: str,
    date_format: str,
    signature_position: SignaturePosition = "right",
    date_value: datetime | None = None,
) -> tuple[bool, bool]:
    """Stamps `signature_path` and a date onto *every* page of
    `template_path` where the anchor regexes match (e.g. a multi-page
    document with one signature block per page), writing the result to
    `output_path`. `date_value` defaults to today when not given. Returns
    (signature_placed, date_placed) — true if at least one page matched.
    """
    sig_regex = re.compile(signature_anchor_pattern, re.IGNORECASE)
    date_regex = re.compile(date_anchor_pattern, re.IGNORECASE)
    today_str = (date_value or datetime.now()).strftime(date_format)

    doc = fitz.open(template_path)
    signature_placed = False
    date_placed = False

    for page in doc:
        page_signature_placed, page_date_placed = _sign_page(
            page, sig_regex, date_regex, signature_path, signature_position, today_str
        )
        signature_placed = signature_placed or page_signature_placed
        date_placed = date_placed or page_date_placed

    if not date_placed:
        for page in doc:
            anchor = _find_anchor_rect(page, date_regex)
            if anchor is not None:
                _stamp_date(page, anchor, today_str)
                date_placed = True
                break

    # Fall back to stamping the bottom-right of the last page so the
    # document is never left unsigned just because the anchor text wasn't found.
    if not signature_placed or not date_placed:
        last_page = doc[-1]
        page_rect = last_page.rect
        if not signature_placed:
            w, h = SIGNATURE_BOX_SIZE
            rect = fitz.Rect(
                page_rect.x1 - FALLBACK_MARGIN - w,
                page_rect.y1 - FALLBACK_MARGIN - h,
                page_rect.x1 - FALLBACK_MARGIN,
                page_rect.y1 - FALLBACK_MARGIN,
            )
            last_page.insert_image(rect, filename=str(signature_path), keep_proportion=True)
            signature_placed = True
        if not date_placed:
            last_page.insert_text(
                (page_rect.x1 - FALLBACK_MARGIN - SIGNATURE_BOX_SIZE[0], page_rect.y1 - FALLBACK_MARGIN - SIGNATURE_BOX_SIZE[1] - 4),
                today_str,
                fontsize=10,
                fontname=DATE_FONT_NAME,
                fontfile=str(DATE_FONT_PATH),
            )
            date_placed = True

    doc.save(output_path)
    doc.close()
    return signature_placed, date_placed
