"""OCR fallback for scanned PDFs using locally installed Tesseract."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


TESSERACT_PATHS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


def find_tesseract() -> str:
    """Return the local Tesseract executable or raise a helpful error."""
    executable = shutil.which("tesseract")
    if executable:
        return executable

    for candidate in TESSERACT_PATHS:
        if candidate.is_file():
            return str(candidate)

    raise RuntimeError(
        "Không tìm thấy Tesseract OCR. Hãy cài Tesseract cùng dữ liệu ngôn ngữ "
        "tiếng Việt (vie) và tiếng Anh (eng)."
    )


def ocr_pdf_to_markdown(source: Path, *, languages: str = "vie+eng", dpi: int = 200) -> str:
    """Render each PDF page and extract its text with Tesseract."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Thiếu PyMuPDF. Hãy cài lại các thư viện trong requirements.txt.") from exc

    tesseract = find_tesseract()
    scale = dpi / 72
    pages: list[str] = []

    with fitz.open(source) as document, tempfile.TemporaryDirectory(prefix="markitdown_ocr_") as temp_dir:
        temp_path = Path(temp_dir)
        for page_number, page in enumerate(document, start=1):
            image_path = temp_path / f"page-{page_number}.png"
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(image_path)
            completed = subprocess.run(
                [tesseract, str(image_path), "stdout", "-l", languages, "--psm", "3"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            if completed.returncode:
                message = completed.stderr.strip() or "Tesseract không thể đọc trang này."
                raise RuntimeError(f"OCR thất bại ở trang {page_number}: {message}")

            text = completed.stdout.strip()
            if text:
                pages.append(f"## Trang {page_number}\n\n{text}")

    if not pages:
        raise ValueError("OCR không nhận diện được văn bản nào trong PDF này.")

    return "\n\n".join(pages) + "\n"
