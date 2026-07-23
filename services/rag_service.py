from dataclasses import dataclass

from utils.knowledge_base import MilvusRAGManager


@dataclass(frozen=True)
class RAGSearchResult:
    context: str
    max_score: float
    matched_count: int

    @property
    def used(self) -> bool:
        return bool(self.context)


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
        context, max_score, matched_count = self._manager.search_similar_cases(
            requirement,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )
        return RAGSearchResult(
            context=context,
            max_score=max_score,
            matched_count=matched_count,
        )

    def save_case(self, requirement: str, test_points: str) -> bool:
        return self._manager.save_case(requirement, test_points)

    def count(self) -> int:
        return self._manager.get_total_count()
