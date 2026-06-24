from __future__ import annotations

import hashlib
import io
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import streamlit as st


APP_TITLE = "Tài liệu → Markdown"
SUPPORTED_TYPES = ["pdf", "ppt", "pptx", "xls", "xlsx"]
MAX_PREVIEW_CHARS = 120_000


@dataclass
class ConversionResult:
    source_name: str
    output_name: str
    markdown: str
    size: int


def init_state() -> None:
    defaults = {
        "results": {},
        "errors": {},
        "selected_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def theme_tokens() -> dict[str, str]:
    return {
        "bg": "#141217",
        "surface": "#1c1920",
        "surface_alt": "#242028",
        "text": "#f2edf4",
        "muted": "#aaa1ad",
        "line": "#39323d",
        "accent": "#b9a1f8",
        "accent_hover": "#c9b6ff",
        "accent_text": "#211a31",
        "success": "#72cda2",
        "danger": "#f0959f",
        "chip": "#2c2632",
        "code_bg": "#100e12",
    }


def inject_styles() -> None:
    t = theme_tokens()
    stylesheet = Path(__file__).with_name("styles.css").read_text(encoding="utf-8")
    st.markdown(
        f"""
        <style>
        :root {{
            --app-bg: {t["bg"]};
            --surface: {t["surface"]};
            --surface-alt: {t["surface_alt"]};
            --text: {t["text"]};
            --muted: {t["muted"]};
            --line: {t["line"]};
            --accent: {t["accent"]};
            --accent-hover: {t["accent_hover"]};
            --accent-text: {t["accent_text"]};
            --success: {t["success"]};
            --danger: {t["danger"]};
            --chip: {t["chip"]};
            --code-bg: {t["code_bg"]};
        }}
        {stylesheet}
        </style>
        """,
        unsafe_allow_html=True,
    )


def readable_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def file_key(name: str, data: bytes) -> str:
    digest = hashlib.sha1(data, usedforsecurity=False).hexdigest()[:12]
    return f"{name}:{digest}"


@st.cache_resource(show_spinner=False)
def get_converter():
    from markitdown import MarkItDown

    return MarkItDown()


def convert_upload(name: str, data: bytes) -> str:
    safe_name = Path(name).name

    with tempfile.TemporaryDirectory(prefix="markitdown_") as temp_dir:
        source = Path(temp_dir) / safe_name
        source.write_bytes(data)
        result = get_converter().convert_local(source)

    markdown = result.text_content
    if not markdown or not markdown.strip():
        raise ValueError(
            "Không trích xuất được nội dung. PDF dạng scan có thể cần OCR."
        )
    return markdown


def make_zip(results: dict[str, ConversionResult]) -> bytes:
    buffer = io.BytesIO()
    used_names: set[str] = set()

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for result in results.values():
            candidate = result.output_name
            stem = Path(candidate).stem
            counter = 2
            while candidate.lower() in used_names:
                candidate = f"{stem}-{counter}.md"
                counter += 1
            used_names.add(candidate.lower())
            archive.writestr(candidate, result.markdown.encode("utf-8"))

    return buffer.getvalue()


def render_header() -> None:
    st.markdown('<div class="eyebrow">Editorial workspace</div>', unsafe_allow_html=True)
    st.markdown(f"# {APP_TITLE}")
    st.markdown(
        '<p class="hero-copy">Chuyển PDF, Excel và PowerPoint thành Markdown '
        "sạch để đọc, tìm kiếm và làm việc cùng mô hình ngôn ngữ.</p>",
        unsafe_allow_html=True,
    )


def render_file_queue(uploaded_files) -> list[tuple[str, str, bytes, int]]:
    normalized = []
    for uploaded in uploaded_files:
        data = uploaded.getvalue()
        key = file_key(uploaded.name, data)
        normalized.append((key, uploaded.name, data, len(data)))

    if not normalized:
        return normalized

    total_size = sum(item[3] for item in normalized)
    st.markdown('<div class="section-kicker">Hàng đợi chuyển đổi</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="metric-line"><span><strong>{len(normalized)}</strong> tệp</span>'
        f'<span><strong>{readable_size(total_size)}</strong> tổng dung lượng</span></div>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        for key, name, _, size in normalized:
            if key in st.session_state.results:
                status_class, status_text = "status-done", "Đã chuyển"
            elif key in st.session_state.errors:
                status_class, status_text = "status-error", "Có lỗi"
            else:
                status_class, status_text = "status-ready", "Sẵn sàng"

            extension = Path(name).suffix.upper().lstrip(".")
            st.markdown(
                f"""
                <div class="file-row">
                    <div>
                        <div class="file-name">{escape_html(name)}</div>
                        <div class="file-meta">{escape_html(extension)} · {readable_size(size)}</div>
                    </div>
                    <div class="file-meta">{escape_html(Path(name).stem)}.md</div>
                    <div class="{status_class}">{status_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if key in st.session_state.errors:
                st.caption(f"Lỗi: {st.session_state.errors[key]}")

    return normalized


def escape_html(value: str) -> str:
    import html

    return html.escape(value, quote=True)


def process_files(files: list[tuple[str, str, bytes, int]]) -> None:
    if not files:
        return

    progress = st.progress(0, text="Đang chuẩn bị chuyển đổi…")
    for index, (key, name, data, size) in enumerate(files, start=1):
        progress.progress(
            (index - 1) / len(files),
            text=f"Đang xử lý {name} ({index}/{len(files)})",
        )
        try:
            markdown = convert_upload(name, data)
            st.session_state.results[key] = ConversionResult(
                source_name=name,
                output_name=f"{Path(name).stem}.md",
                markdown=markdown,
                size=size,
            )
            st.session_state.errors.pop(key, None)
            st.session_state.selected_result = key
        except Exception as exc:
            st.session_state.errors[key] = str(exc)
            st.session_state.results.pop(key, None)

    progress.progress(1.0, text="Hoàn tất chuyển đổi.")


def render_results() -> None:
    results: dict[str, ConversionResult] = st.session_state.results
    if not results:
        st.markdown('<div class="section-kicker">Không gian đọc</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("### Markdown sẽ xuất hiện ở đây")
            st.write(
                "Sau khi chuyển đổi, bạn có thể chọn từng tài liệu, đọc bản hiển thị "
                "hoặc kiểm tra mã Markdown trước khi tải xuống."
            )
        return

    st.markdown('<div class="section-kicker">Không gian đọc</div>', unsafe_allow_html=True)
    keys = list(results)
    if st.session_state.selected_result not in results:
        st.session_state.selected_result = keys[0]

    label_to_key = {
        f"{result.source_name} · {len(result.markdown):,} ký tự": key
        for key, result in results.items()
    }
    current_label = next(
        label for label, key in label_to_key.items()
        if key == st.session_state.selected_result
    )

    nav_col, preview_col = st.columns([1.05, 3], gap="large")
    with nav_col:
        st.markdown("### Tài liệu")
        selected_label = st.selectbox(
            "Chọn tài liệu",
            options=list(label_to_key),
            index=list(label_to_key).index(current_label),
            label_visibility="collapsed",
        )
        st.session_state.selected_result = label_to_key[selected_label]
        selected = results[st.session_state.selected_result]

        st.caption("Tệp đầu ra")
        st.markdown(f"**{selected.output_name}**")
        st.caption(
            f"{readable_size(selected.size)} nguồn · "
            f"{len(selected.markdown):,} ký tự Markdown"
        )
        st.download_button(
            "Tải tệp Markdown",
            data=selected.markdown.encode("utf-8"),
            file_name=selected.output_name,
            mime="text/markdown",
            use_container_width=True,
            type="primary",
        )
        if len(results) > 1:
            st.download_button(
                "Tải tất cả (.zip)",
                data=make_zip(results),
                file_name="markdown-documents.zip",
                mime="application/zip",
                use_container_width=True,
            )

    with preview_col:
        selected = results[st.session_state.selected_result]
        preview = selected.markdown[:MAX_PREVIEW_CHARS]
        truncated = len(selected.markdown) > MAX_PREVIEW_CHARS
        rendered_tab, source_tab = st.tabs(["Bản đọc", "Mã Markdown"])
        with rendered_tab:
            with st.container(height=560, border=True):
                st.markdown(preview)
                if truncated:
                    st.info(
                        "Bản xem trước đã được rút gọn để giữ giao diện mượt. "
                        "Tệp tải xuống vẫn chứa đầy đủ nội dung."
                    )
        with source_tab:
            with st.container(height=560, border=True):
                st.code(preview, language="markdown", line_numbers=True)
                if truncated:
                    st.caption("Đang hiển thị phần đầu của tài liệu.")


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=None,
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    init_state()
    inject_styles()
    render_header()

    st.markdown('<div class="section-kicker">Thêm tài liệu</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Kéo thả tài liệu vào đây",
        type=SUPPORTED_TYPES,
        accept_multiple_files=True,
        key="document_uploader",
        help="Hỗ trợ PDF, PPT/PPTX và XLS/XLSX. PDF scan có thể cần OCR.",
    )
    st.markdown(
        """
        <div class="format-row">
            <span class="format-chip">PDF</span>
            <span class="format-chip">PPTX</span>
            <span class="format-chip">XLSX</span>
            <span class="format-chip">Nhiều tệp cùng lúc</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    queue = render_file_queue(uploaded_files or [])
    st.markdown('<div style="height: 16px"></div>', unsafe_allow_html=True)
    action_left, action_right = st.columns([1, 3], vertical_alignment="center")
    with action_left:
        convert_clicked = st.button(
            f"Chuyển đổi {len(queue)} tệp" if queue else "Chuyển đổi",
            type="primary",
            use_container_width=True,
            disabled=not queue,
        )
    with action_right:
        if queue:
            st.caption(
                "Các tệp có cùng nội dung đã chuyển sẽ được giữ lại trong phiên; "
                "bấm lại để thử lại những tệp gặp lỗi."
            )

    if convert_clicked:
        process_files(queue)
        st.rerun()

    render_results()


if __name__ == "__main__":
    main()
