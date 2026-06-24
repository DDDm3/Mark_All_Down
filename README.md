# Tài liệu → Markdown

Ứng dụng Streamlit chuyển đổi PDF, Excel và PowerPoint sang Markdown bằng
Microsoft MarkItDown.

## Cài đặt

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Nếu máy nhận lệnh `python` thay vì `py`, thay `py` bằng `python`.

## Chạy ứng dụng

```powershell
streamlit run streamlit_markitdown_app.py
```

Trình duyệt sẽ mở tại `http://localhost:8501`.

## Tính năng

- Upload nhiều PDF, PPT/PPTX và XLS/XLSX.
- Chuyển đổi cục bộ bằng MarkItDown.
- Giao diện sáng/tối.
- Xem bản Markdown đã render hoặc mã nguồn Markdown.
- Tải từng tệp `.md` hoặc tải tất cả dưới dạng `.zip`.
- Không ghi tệp upload vào thư mục dự án; tệp tạm được xóa sau khi chuyển đổi.

## Lưu ý

- PDF scan không có lớp văn bản có thể cần OCR.
- Định dạng Office cũ như `.ppt` và `.xls` phụ thuộc khả năng đọc của các thư
  viện nền; nếu gặp lỗi, nên lưu lại thành `.pptx` hoặc `.xlsx`.
