import unittest

from services.rag_service import (
    RAGSearchStatus,
    RAGService,
)


class FakeMilvusManager:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result or ("", 0.0, 0)
        self.error = error
        self.last_query = ""
        self.raise_on_error = None

    def search_similar_cases(
        self,
        requirement: str,
        top_k: int,
        similarity_threshold: float,
        raise_on_error: bool,
    ):
        self.last_query = requirement
        self.raise_on_error = raise_on_error
        if self.error:
            raise self.error
        return self.result


class RAGServiceTests(unittest.TestCase):
    def test_matched_result_has_explicit_status(self):
        manager = FakeMilvusManager(
            ("历史订单测试点", 0.88, 2)
        )
        service = RAGService(manager=manager)

        result = service.search("订单提交")

        self.assertEqual(result.status, RAGSearchStatus.MATCHED)
        self.assertTrue(result.used)
        self.assertFalse(result.failed)
        self.assertTrue(manager.raise_on_error)

    def test_empty_result_is_no_match_not_failure(self):
        service = RAGService(manager=FakeMilvusManager())

        result = service.search("订单提交")

        self.assertEqual(result.status, RAGSearchStatus.NO_MATCH)
        self.assertFalse(result.used)
        self.assertFalse(result.failed)
        self.assertIsNone(result.error_message)

    def test_manager_error_becomes_failed_result(self):
        service = RAGService(
            manager=FakeMilvusManager(
                error=ConnectionError("milvus unavailable")
            )
        )

        result = service.search("订单提交")

        self.assertEqual(result.status, RAGSearchStatus.FAILED)
        self.assertTrue(result.failed)
        self.assertEqual(result.matched_count, 0)
        self.assertIn("milvus unavailable", result.error_message)


if __name__ == "__main__":
    unittest.main()
