import os
from io import BytesIO


def extract_text_from_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    filename = uploaded_file.name
    file_ext = os.path.splitext(filename)[1].lower()

    try:
        if file_ext in ['.txt', '.md']:
            return uploaded_file.read().decode('utf-8')

        elif file_ext == '.pdf':
            return _extract_text_from_pdf(uploaded_file)

        elif file_ext == '.docx':
            return _extract_text_from_docx(uploaded_file)

        else:
            raise ValueError(f"不支持的文件格式: {file_ext}")

    except Exception as e:
        raise ValueError(f"文件解析失败: {str(e)}")


def _extract_text_from_pdf(uploaded_file) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(uploaded_file.read()))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n\n"
    return text.strip()


def _extract_text_from_docx(uploaded_file) -> str:
    from docx import Document

    doc = Document(BytesIO(uploaded_file.read()))
    text = ""
    for para in doc.paragraphs:
        if para.text.strip():
            text += para.text + "\n\n"
    return text.strip()