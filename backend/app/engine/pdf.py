"""PDF text extraction helpers."""

from __future__ import annotations

import io

import pdfplumber

from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_PDF_BYTES = 5 * 1024 * 1024


class PDFParseError(Exception):
    pass


def extract_text_from_pdf(file_bytes: bytes) -> str:
    if len(file_bytes) > MAX_PDF_BYTES:
        raise PDFParseError("El PDF supera el tamaño máximo de 5MB")
    if len(file_bytes) == 0:
        raise PDFParseError("El archivo PDF está vacío")

    try:
        texts: list[str] = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    texts.append(page_text)
        combined = "\n".join(texts).strip()
        if len(combined) < 50:
            raise PDFParseError("No se pudo extraer texto suficiente del PDF")
        logger.info("pdf_extracted", pages=len(texts), chars=len(combined))
        return combined
    except PDFParseError:
        raise
    except Exception as exc:
        logger.warning("pdf_parse_failed", error=str(exc))
        raise PDFParseError(f"Error al parsear PDF: {exc}") from exc
