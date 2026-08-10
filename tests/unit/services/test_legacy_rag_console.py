import builtins

from utils.knowledge_base import MilvusRAGManager


class FakeMilvusClient:
    def get_collection_stats(self, collection_name):
        return {"row_count": 1}

    def search(self, **kwargs):
        return [[{
            "distance": 0.9,
            "entity": {
                "prd_content": "包含特殊字符►的需求",
                "test_points": "验证特殊字符不会破坏检索",
            },
        }]]


def test_rag_logging_does_not_print_full_result_with_console_unsafe_text(
    monkeypatch,
):
    manager = MilvusRAGManager()
    manager.client = FakeMilvusClient()
    monkeypatch.setattr(manager, "_get_embedding", lambda text: [0.1] * 768)
    original_print = builtins.print

    def gbk_console_print(*values, **kwargs):
        " ".join(str(value) for value in values).encode("gbk")
        original_print(*values, **kwargs)

    monkeypatch.setattr(builtins, "print", gbk_console_print)

    context, max_score, count = manager.search_similar_cases("订单需求")

    assert "包含特殊字符►的需求" in context
    assert max_score == 0.9
    assert count == 1
