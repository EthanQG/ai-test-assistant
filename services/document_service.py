from utils.file_parser import extract_text_from_file


class DocumentService:
    """Provides a stable boundary for parsing uploaded requirement documents."""

    @staticmethod
    def extract_text(uploaded_file) -> str:
        return extract_text_from_file(uploaded_file)
