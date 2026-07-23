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

    def test_custom_prompt_directory_can_be_used(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_path = Path(temp_dir) / "custom.txt"
            prompt_path.write_text("自定义系统规则", encoding="utf-8")

            prompt = PromptService(temp_dir).load_system_prompt("custom")

        self.assertEqual(prompt, "自定义系统规则")


if __name__ == "__main__":
    unittest.main()
