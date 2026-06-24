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
        "theme": "light",
        "results": {},
        "errors": {},
        "selected_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def theme_tokens(theme: str) -> dict[str, str]:
    if theme == "dark":
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
    return {
        "bg": "#f8f6f1",
        "surface": "#fffdf9",
        "surface_alt": "#f1eee7",
        "text": "#252129",
        "muted": "#716a74",
        "line": "#ddd7df",
        "accent": "#7358b8",
        "accent_hover": "#60469f",
        "accent_text": "#ffffff",
        "success": "#267653",
        "danger": "#a93d4b",
        "chip": "#eee9f5",
        "code_bg": "#f2efe9",
    }


def inject_styles(theme: str) -> None:
    t = theme_tokens(theme)
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

        html, body, [data-testid="stAppViewContainer"], .stApp {{
            background: var(--app-bg);
            color: var(--text);
        }}

        [data-testid="stHeader"] {{
            background: transparent;
        }}

        [data-testid="stToolbar"] {{
            right: 1.5rem;
        }}

        .block-container {{
            max-width: 1320px;
            padding-top: 2.1rem;
            padding-bottom: 7rem;
        }}

        h1, h2, h3, p, label, [data-testid="stMarkdownContainer"] {{
            color: var(--text);
        }}

        h1 {{
            font-size: clamp(2.1rem, 4vw, 3.65rem) !important;
            line-height: 1.04 !important;
            letter-spacing: -0.045em !important;
            font-weight: 650 !important;
            margin: 0 0 0.7rem !important;
        }}

        h2 {{
            letter-spacing: -0.025em !important;
            font-size: 1.35rem !important;
        }}

        h3 {{
            letter-spacing: -0.015em !important;
        }}

        .eyebrow {{
            color: var(--accent);
            font-size: 0.76rem;
            font-weight: 750;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            margin-bottom: 0.8rem;
        }}

        .hero-copy {{
            color: var(--muted);
            font-size: 1.04rem;
            line-height: 1.7;
            max-width: 670px;
            margin: 0;
        }}

        .privacy-note {{
            color: var(--muted);
            font-size: 0.84rem;
            text-align: right;
            padding-top: 0.35rem;
        }}

        .section-kicker {{
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin: 2.2rem 0 0.65rem;
        }}

        .format-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 1rem;
        }}

        .format-chip {{
            background: var(--chip);
            color: var(--text);
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 700;
            padding: 0.34rem 0.68rem;
        }}

        .metric-line {{
            display: flex;
            gap: 1.6rem;
            align-items: center;
            color: var(--muted);
            font-size: 0.88rem;
            padding: 0.7rem 0 0.25rem;
        }}

        .metric-line strong {{
            color: var(--text);
            font-weight: 700;
        }}

        .file-row {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto auto;
            align-items: center;
            gap: 1rem;
            border-bottom: 1px solid var(--line);
            padding: 0.9rem 0.1rem;
        }}

        .file-row:last-child {{
            border-bottom: 0;
        }}

        .file-name {{
            color: var(--text);
            font-weight: 650;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .file-meta {{
            color: var(--muted);
            font-size: 0.8rem;
            margin-top: 0.2rem;
        }}

        .status-ready, .status-done, .status-error {{
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 750;
            padding: 0.3rem 0.62rem;
            white-space: nowrap;
        }}

        .status-ready {{
            background: var(--surface-alt);
            color: var(--muted);
        }}

        .status-done {{
            background: color-mix(in srgb, var(--success) 14%, transparent);
            color: var(--success);
        }}

        .status-error {{
            background: color-mix(in srgb, var(--danger) 14%, transparent);
            color: var(--danger);
        }}

        [data-testid="stFileUploader"] {{
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 0.35rem;
        }}

        [data-testid="stFileUploaderDropzone"] {{
            background: transparent;
            border: 1px dashed var(--line);
            border-radius: 14px;
            min-height: 168px;
        }}

        [data-testid="stFileUploaderDropzone"]:hover {{
            border-color: var(--accent);
        }}

        [data-testid="stFileUploader"] small,
        [data-testid="stFileUploader"] span {{
            color: var(--muted);
        }}

        .stButton > button,
        .stDownloadButton > button {{
            border-radius: 999px;
            min-height: 2.75rem;
            font-weight: 700;
            transition: 150ms ease;
        }}

        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"] {{
            background: var(--accent);
            border-color: var(--accent);
            color: var(--accent-text);
        }}

        .stButton > button[kind="primary"]:hover,
        .stDownloadButton > button[kind="primary"]:hover {{
            background: var(--accent-hover);
            border-color: var(--accent-hover);
        }}

        .stButton > button[kind="secondary"],
        .stDownloadButton > button[kind="secondary"] {{
            background: transparent;
            border-color: var(--line);
            color: var(--text);
        }}

        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--surface);
            border-color: var(--line);
            border-radius: 18px;
        }}

        [data-testid="stTabs"] [data-baseweb="tab-list"] {{
            gap: 1.2rem;
            border-bottom: 1px solid var(--line);
        }}

        [data-testid="stTabs"] button {{
            color: var(--muted);
        }}

        [data-testid="stTabs"] button[aria-selected="true"] {{
            color: var(--accent);
        }}

        [data-testid="stCodeBlock"] {{
            background: var(--code-bg);
            border: 1px solid var(--line);
            border-radius: 14px;
        }}

        [data-testid="stAlert"] {{
            background: var(--surface);
            color: var(--text);
            border-color: var(--line);
        }}

        [data-testid="stSelectbox"] > div > div,
        [data-testid="stToggle"] {{
            color: var(--text);
        }}

        .stSelectbox [data-baseweb="select"] > div {{
            background: var(--surface);
            border-color: var(--line);
            color: var(--text);
        }}

        hr {{
            border-color: var(--line) !important;
        }}

        @media (max-width: 760px) {{
            .block-container {{
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 1.25rem;
            }}
            .privacy-note {{
                text-align: left;
            }}
            .file-row {{
                grid-template-columns: minmax(0, 1fr) auto;
            }}
            .file-row > :nth-child(2) {{
                display: none;
            }}
        }}
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

    return MarkItDown(enable_plugins=False)


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
    title_col, theme_col = st.columns([5, 1.25], vertical_alignment="top")
    with title_col:
        st.markdown('<div class="eyebrow">Editorial workspace</div>', unsafe_allow_html=True)
        st.markdown(f"# {APP_TITLE}")
        st.markdown(
            '<p class="hero-copy">Chuyển PDF, Excel và PowerPoint thành Markdown '
            "sạch để đọc, tìm kiếm và làm việc cùng mô hình ngôn ngữ.</p>",
            unsafe_allow_html=True,
        )
    with theme_col:
        is_dark = st.toggle(
            "Chế độ tối",
            value=st.session_state.theme == "dark",
            key="theme_toggle",
        )
        new_theme = "dark" if is_dark else "light"
        if new_theme != st.session_state.theme:
            st.session_state.theme = new_theme
            st.rerun()
        st.markdown(
            '<div class="privacy-note">Tệp được xử lý cục bộ<br>trong phiên làm việc.</div>',
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
            with st.container(border=True):
                st.markdown(preview)
                if truncated:
                    st.info(
                        "Bản xem trước đã được rút gọn để giữ giao diện mượt. "
                        "Tệp tải xuống vẫn chứa đầy đủ nội dung."
                    )
        with source_tab:
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
    inject_styles(st.session_state.theme)
    render_header()

    st.markdown('<div class="section-kicker">Thêm tài liệu</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Kéo thả tài liệu vào đây",
        type=SUPPORTED_TYPES,
        accept_multiple_files=True,
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
