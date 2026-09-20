from io import BytesIO
from pathlib import Path
from docx import Document
from pypdf import PdfReader

MAX_CHARS = 60_000


def extract_resume(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(data))
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
    elif suffix == ".docx":
        document = Document(BytesIO(data))
        text = "\n".join(p.text for p in document.paragraphs)
    elif suffix == ".txt":
        text = data.decode("utf-8", errors="replace")
    else:
        raise ValueError("Supported files: PDF, DOCX, and TXT")
    text = text.strip()
    if not text:
        raise ValueError("No text could be extracted. Scanned PDFs are not supported yet.")
    return text[:MAX_CHARS]
