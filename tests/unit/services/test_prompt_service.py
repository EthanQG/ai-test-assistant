import tempfile
import unittest
from pathlib import Path

from services.prompt_service import PromptService


class PromptServiceTests(unittest.TestCase):
    def test_system_prompt_is_loaded_without_dynamic_placeholders(self):
        prompt = PromptService().load_system_prompt("test_points")

        self.assertNotIn("{prd_content}", prompt)
        self.assertNotIn("{bug_kb_content}", prompt)
        self.assertIn("需求事实", prompt)
        self.assertIn("推导风险", prompt)
        self.assertIn("待确认项", prompt)

    def test_user_prompt_contains_each_dynamic_input_once(self):
        prompt = PromptService.build_test_points_prompt(
            requirement="唯一需求内容",
            bug_knowledge="唯一本地知识",
            rag_context="唯一召回内容",
        )

        self.assertEqual(prompt.count("唯一需求内容"), 1)
        self.assertEqual(prompt.count("唯一本地知识"), 1)
        self.assertEqual(prompt.count("唯一召回内容"), 1)

    def test_empty_optional_context_sections_are_omitted(self):
        prompt = PromptService.build_test_points_prompt(
            requirement="文件上传需求",
            bug_knowledge="  ",
            rag_context=None,
        )

        self.assertNotIn("【本地历史 Bug 经验】", prompt)
        self.assertNotIn("【向量检索召回的相似历史测试资产】", prompt)

    def test_requirement_analysis_prompt_contains_requirement_once(self):
        prompt = PromptService.build_requirement_analysis_prompt(
            "  用户提交订单后扣减库存  "
        )

        self.assertEqual(prompt.count("用户提交订单后扣减库存"), 1)
        self.assertIn("【原始需求】", prompt)

    def test_empty_requirement_analysis_prompt_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "requirement cannot be empty",
        ):
            PromptService.build_requirement_analysis_prompt("  ")

    def test_requirement_analysis_prompt_contains_user_clarifications(self):
        prompt = PromptService.build_requirement_analysis_prompt(
            "用户可以使用优惠券",
            user_clarifications=[
                {
                    "question": "优惠券是否允许叠加？",
                    "answer": "不允许叠加",
                }
            ],
            deferred_questions=["优惠券失效时间如何计算？"],
        )

        self.assertIn("用户补充确认", prompt)
        self.assertIn("不允许叠加", prompt)
        self.assertIn("用户暂时无法确认的问题", prompt)
        self.assertIn("优惠券失效时间如何计算？", prompt)

    def test_structured_test_points_prompt_contains_context(self):
        prompt = PromptService.build_structured_test_points_prompt(
            {
                "summary": "订单提交",
                "requirement_facts": ["提交时扣减库存"],
            },
            local_bug_knowledge="关注重复提交",
            rag_context="历史库存重复扣减",
        )

        self.assertIn("订单提交", prompt)
        self.assertIn("提交时扣减库存", prompt)
        self.assertIn("关注重复提交", prompt)
        self.assertIn("历史库存重复扣减", prompt)

    def test_structured_test_points_prompt_omits_empty_context(self):
        prompt = PromptService.build_structured_test_points_prompt(
            {"summary": "订单提交"},
            local_bug_knowledge="",
            rag_context="",
        )

        self.assertNotIn("【本地测试经验】", prompt)
        self.assertNotIn("【相似历史测试资产】", prompt)

    def test_review_prompt_contains_requirements_and_test_points(self):
        prompt = PromptService.build_test_point_review_prompt(
            {
                "summary": "订单库存",
                "requirement_facts": ["提交订单时扣减库存"],
            },
            [{"title": "库存充足时提交订单"}],
        )

        self.assertIn("提交订单时扣减库存", prompt)
        self.assertIn("库存充足时提交订单", prompt)
        self.assertIn("【结构化需求分析】", prompt)
        self.assertIn("【待评审测试点】", prompt)
        self.assertIn("分别最多8项", prompt)
        self.assertNotIn('"requirement_facts": [', prompt)
        self.assertIn('"fact_id":"F001"', prompt)
        self.assertIn("不要重复事实原文", prompt)

    def test_review_prompt_rejects_empty_test_points(self):
        with self.assertRaisesRegex(
            ValueError,
            "test points cannot be empty",
        ):
            PromptService.build_test_point_review_prompt(
                {"requirement_facts": ["需求事实"]},
                [],
            )

    def test_revision_prompt_contains_points_and_review_feedback(self):
        prompt = PromptService.build_test_point_revision_prompt(
            {
                "summary": "订单库存",
                "requirement_facts": ["库存不足时不能提交"],
            },
            [{"title": "库存不足时提交"}],
            {
                "overall_score": 70,
                "revision_suggestions": ["补充库存不变预期"],
            },
        )

        self.assertIn("库存不足时不能提交", prompt)
        self.assertIn("库存不足时提交", prompt)
        self.assertIn("补充库存不变预期", prompt)
        self.assertIn("【Reviewer评审结果】", prompt)
        self.assertIn("不要重写完整测试点集合", prompt)

    def test_revision_prompt_rejects_empty_review(self):
        with self.assertRaisesRegex(
            ValueError,
            "review result or human feedback is required",
        ):
            PromptService.build_test_point_revision_prompt(
                {"requirement_facts": ["需求事实"]},
                [{"title": "测试点"}],
                {},
            )

    def test_human_revision_prompt_contains_hard_scope(self):
        prompt = PromptService.build_test_point_revision_prompt(
            {
                "summary": "订单库存",
                "requirement_facts": ["库存不足时不能提交"],
            },
            [{"title": "库存不足时提交"}],
            human_feedback=[
                {
                    "action": "add",
                    "content": "增加并发提交场景",
                }
            ],
            allowed_actions={"add", "replace"},
            max_operations=3,
        )

        self.assertIn("operations 最多返回 3 项", prompt)
        self.assertIn("action 只能使用：add、replace", prompt)
        self.assertIn("不要顺带重写其他测试点", prompt)

    def test_custom_prompt_directory_can_be_used(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_path = Path(temp_dir) / "custom.txt"
            prompt_path.write_text("自定义系统规则", encoding="utf-8")

            prompt = PromptService(temp_dir).load_system_prompt("custom")

        self.assertEqual(prompt, "自定义系统规则")


if __name__ == "__main__":
    unittest.main()
