import asyncio
import fitz  # pymupdf


def _extract_text_sync(file_path: str) -> str:
    doc = fitz.open(file_path)
    pages = []
    for page in doc:
        text = page.get_text("text")
        if text and text.strip():
            pages.append(text.strip())
    doc.close()
    return "\n\n".join(pages)


async def extract_pdf_text(file_path: str) -> str:
    return await asyncio.to_thread(_extract_text_sync, file_path)
