from repositories import InMemoryTaskRepository

from .service import TestAnalysisApplicationService


def build_session_application_service() -> TestAnalysisApplicationService:
    """Build dependencies owned by one Streamlit user session."""
    return TestAnalysisApplicationService(InMemoryTaskRepository())
