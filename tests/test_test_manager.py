import unittest

from services.rag_service import RAGSearchResult
from utils.test_manager import TestAssistantManager


class FakeLLMService:
    def __init__(self):
        self.last_prompt = ""
        self.last_system_prompt = ""

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        return "generated report"

    def generate_stream(self, prompt: str, system_prompt: str = ""):
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        yield "generated "
        yield "report"


class FakeRAGService:
    def __init__(self):
        self.saved_cases = []

    def search(self, requirement: str, top_k: int = 2):
        return RAGSearchResult(
            context="历史支付重复扣款测试点",
            max_score=0.86,
            matched_count=1,
        )

    def save_case(self, requirement: str, test_points: str) -> bool:
        self.saved_cases.append((requirement, test_points))
        return True

    def count(self) -> int:
        return len(self.saved_cases)


class TestAssistantManagerTests(unittest.TestCase):
    def setUp(self):
        self.llm = FakeLLMService()
        self.rag = FakeRAGService()
        self.manager = TestAssistantManager(
            llm_service=self.llm,
            rag_service=self.rag,
        )

    def test_stream_generation_includes_requirement_and_rag_context(self):
        result = "".join(
            self.manager.generate_test_points_stream(
                "用户提交支付订单",
                "支付接口超时后需要查询订单状态",
            )
        )

        self.assertEqual(result, "generated report")
        self.assertIn("用户提交支付订单", self.llm.last_prompt)
        self.assertIn("支付接口超时后需要查询订单状态", self.llm.last_prompt)
        self.assertIn("历史支付重复扣款测试点", self.llm.last_prompt)

    def test_rag_metrics_are_exposed_after_generation(self):
        self.manager.generate_test_points("用户提交支付订单")

        self.assertTrue(self.manager.get_rag_used())
        self.assertEqual(self.manager.get_rag_matched_count(), 1)
        self.assertEqual(self.manager.get_rag_max_score(), 0.86)

    def test_save_to_rag_uses_service_boundary(self):
        success, message = self.manager.save_to_rag("支付需求", "支付测试点")

        self.assertTrue(success)
        self.assertEqual(message, "保存成功")
        self.assertEqual(self.rag.saved_cases, [("支付需求", "支付测试点")])


if __name__ == "__main__":
    unittest.main()
