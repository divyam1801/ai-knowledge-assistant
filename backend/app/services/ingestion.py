from pathlib import Path

from pypdf import PdfReader

from app.models import FileType
from app.services.ocr import extract_text_from_image
from app.utils.chunking import split_text
from app.utils.text_cleaning import clean_text


def extract_text(file_path: str | Path, file_type: FileType) -> str:
    file_path = Path(file_path)

    match file_type:
        case FileType.TXT | FileType.MD:
            return file_path.read_text(encoding="utf-8", errors="replace")
        case FileType.PDF:
            return _extract_pdf(file_path)
        case FileType.IMAGE:
            return extract_text_from_image(file_path)
        case _:
            raise ValueError(f"Unsupported file type: {file_type}")


def process_document_text(file_path: str | Path, file_type: FileType) -> list[dict]:
    raw_text = extract_text(file_path, file_type)
    cleaned = clean_text(raw_text)
    if not cleaned:
        return []
    return split_text(cleaned)


def _extract_pdf(file_path: Path) -> str:
    reader = PdfReader(file_path)
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)
