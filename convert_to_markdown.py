#!/usr/bin/env python3
"""
Chuyển PDF, Excel và PowerPoint sang Markdown bằng Microsoft MarkItDown.

Ví dụ:
    python convert_to_markdown.py report.pdf slides.pptx data.xlsx
    python convert_to_markdown.py ./tai_lieu -o ./markdown --recursive
    python convert_to_markdown.py ./tai_lieu -o ./markdown --overwrite
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from ocr_pdf import ocr_pdf_to_markdown

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
}


def configure_console_encoding() -> None:
    """Ưu tiên UTF-8 để thông báo tiếng Việt hiển thị đúng trên Windows."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (AttributeError, OSError):
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Chuyển các file PDF, Excel và PowerPoint thành Markdown "
            "bằng Microsoft MarkItDown."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python convert_to_markdown.py report.pdf
  python convert_to_markdown.py report.pdf slides.pptx data.xlsx -o markdown
  python convert_to_markdown.py tai_lieu -o markdown --recursive

Cài thư viện:
  python -m pip install "markitdown[pdf,pptx,xlsx,xls]"
  hoặc:
  python -m pip install "markitdown[all]"
""",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Một hoặc nhiều file/thư mục cần chuyển đổi.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help=(
            "Thư mục chứa kết quả. Nếu bỏ qua, file Markdown được đặt "
            "cạnh file nguồn."
        ),
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Tìm file trong toàn bộ thư mục con.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Ghi đè file Markdown đã tồn tại.",
    )
    return parser


def load_markitdown():
    try:
        from markitdown import MarkItDown
    except ImportError:
        print(
            "Lỗi: chưa tìm thấy thư viện 'markitdown'.\n"
            'Hãy cài bằng: python -m pip install "markitdown[all]"',
            file=sys.stderr,
        )
        raise SystemExit(2)
    return MarkItDown


def discover_files(inputs: Iterable[Path], recursive: bool) -> tuple[list[Path], int]:
    discovered: list[Path] = []
    missing_count = 0

    for raw_path in inputs:
        path = raw_path.expanduser()

        if not path.exists():
            print(f"[KHÔNG TỒN TẠI] {path}", file=sys.stderr)
            missing_count += 1
            continue

        if path.is_file():
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                discovered.append(path.resolve())
            else:
                print(f"[BỎ QUA ĐỊNH DẠNG] {path}")
            continue

        pattern = "**/*" if recursive else "*"
        for candidate in path.glob(pattern):
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                discovered.append(candidate.resolve())

    # Loại bỏ file trùng nhưng giữ nguyên thứ tự đầu vào.
    return list(dict.fromkeys(discovered)), missing_count


def common_input_root(files: list[Path]) -> Path | None:
    if not files:
        return None

    try:
        import os

        return Path(os.path.commonpath([str(file.parent) for file in files]))
    except ValueError:
        # Có thể xảy ra trên Windows khi file nằm ở nhiều ổ đĩa khác nhau.
        return None


def output_path_for(
    source: Path,
    output_dir: Path | None,
    root: Path | None,
) -> Path:
    if output_dir is None:
        return source.with_suffix(".md")

    if root is not None:
        try:
            relative_parent = source.parent.relative_to(root)
            return output_dir / relative_parent / f"{source.stem}.md"
        except ValueError:
            pass

    return output_dir / f"{source.stem}.md"


def convert_files(
    files: list[Path],
    output_dir: Path | None,
    overwrite: bool,
) -> tuple[int, int, int]:
    MarkItDown = load_markitdown()
    converter = MarkItDown()
    root = common_input_root(files) if output_dir else None

    succeeded = 0
    skipped = 0
    failed = 0

    for source in files:
        destination = output_path_for(source, output_dir, root)

        if destination.exists() and not overwrite:
            print(f"[BỎ QUA ĐÃ CÓ] {destination}")
            skipped += 1
            continue

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)

            # convert_local chỉ cho phép đọc file cục bộ, an toàn và đúng mục đích hơn
            # convert() vốn còn có thể nhận URL hoặc các nguồn dữ liệu khác.
            try:
                markdown = converter.convert_local(source).text_content
            except Exception:
                if source.suffix.lower() != ".pdf":
                    raise
                markdown = ""

            if not markdown or not markdown.strip():
                if source.suffix.lower() != ".pdf":
                    raise ValueError("Không trích xuất được nội dung từ tệp này.")
                print(f"[OCR] {source}")
                markdown = ocr_pdf_to_markdown(source)

            destination.write_text(markdown, encoding="utf-8")
            print(f"[THÀNH CÔNG] {source} -> {destination}")
            succeeded += 1
        except Exception as exc:
            print(f"[LỖI] {source}: {exc}", file=sys.stderr)
            failed += 1

    return succeeded, skipped, failed


def main() -> int:
    configure_console_encoding()
    args = build_parser().parse_args()
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else None
    files, missing_count = discover_files(args.inputs, args.recursive)

    if not files:
        print(
            "Không tìm thấy file được hỗ trợ. "
            "Các định dạng hợp lệ: PDF, PPT, PPTX, XLS, XLSX.",
            file=sys.stderr,
        )
        return 1

    print(f"Tìm thấy {len(files)} file cần xử lý.")
    succeeded, skipped, failed = convert_files(
        files=files,
        output_dir=output_dir,
        overwrite=args.overwrite,
    )

    print(
        "\nHoàn tất: "
        f"{succeeded} thành công, "
        f"{skipped} bỏ qua, "
        f"{failed + missing_count} lỗi."
    )
    return 1 if failed or missing_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
