"""Legacy text-only wrapper around the structured document service."""


def extract_text_from_file(uploaded_file) -> str:
    from services.document_service import DocumentService

    if uploaded_file is None:
        return ""
    return DocumentService.extract_text(uploaded_file)
