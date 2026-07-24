from dataclasses import dataclass
from enum import Enum

from utils.knowledge_base import MilvusRAGManager


class RAGSearchStatus(str, Enum):
    MATCHED = "matched"
    NO_MATCH = "no_match"
    FAILED = "failed"


@dataclass(frozen=True)
class RAGSearchResult:
    context: str
    max_score: float
    matched_count: int
    status: RAGSearchStatus = RAGSearchStatus.NO_MATCH
    error_message: str | None = None

    @property
    def used(self) -> bool:
        return self.status == RAGSearchStatus.MATCHED

    @property
    def failed(self) -> bool:
        return self.status == RAGSearchStatus.FAILED


class RAGService:
    """Application-facing boundary for historical test asset retrieval."""

    def __init__(self, manager: MilvusRAGManager | None = None):
        self._manager = manager or MilvusRAGManager()

    def search(
        self,
        requirement: str,
        top_k: int = 2,
        similarity_threshold: float = 0.60,
    ) -> RAGSearchResult:
        try:
            context, max_score, matched_count = (
                self._manager.search_similar_cases(
                    requirement,
                    top_k=top_k,
                    similarity_threshold=similarity_threshold,
                    raise_on_error=True,
                )
            )
        except Exception as exc:
            return RAGSearchResult(
                context="",
                max_score=0.0,
                matched_count=0,
                status=RAGSearchStatus.FAILED,
                error_message=str(exc),
            )

        status = (
            RAGSearchStatus.MATCHED
            if context and matched_count > 0
            else RAGSearchStatus.NO_MATCH
        )
        return RAGSearchResult(
            context=context,
            max_score=max_score,
            matched_count=matched_count,
            status=status,
        )

    def save_case(self, requirement: str, test_points: str) -> bool:
        return self._manager.save_case(requirement, test_points)

    def count(self) -> int:
        return self._manager.get_total_count()
