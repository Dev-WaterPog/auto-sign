"""Merges multiple already-signed PDFs (as bytes) into one, preserving order."""

import fitz  # PyMuPDF


def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
    if len(pdf_bytes_list) == 1:
        return pdf_bytes_list[0]

    merged = fitz.open()
    for pdf_bytes in pdf_bytes_list:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            merged.insert_pdf(doc)
    output = merged.tobytes(garbage=4, deflate=True)
    merged.close()
    return output
