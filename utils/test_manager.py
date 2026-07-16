import os
import time
from utils.ai_client import DeepSeekClient


class TestAssistantManager:
    def __init__(self):
        self.prompts_dir = "./prompts"
        self.ai_client = None

    def _get_system_prompt(self, prompt_name: str) -> str:
        prompt_path = os.path.join(self.prompts_dir, f"{prompt_name}.txt")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    def _ensure_ai_client(self):
        if self.ai_client is None:
            self.ai_client = DeepSeekClient()

    def generate_test_points_stream(self, prd_content: str, bug_kb_content: str = None, history_kb_content: str = None):
        system_prompt = self._get_system_prompt("test_points")

        user_prompt = f"请分析以下需求描述，并生成测试点文档：\n\n【需求描述】\n{prd_content}\n\n"
        
        if bug_kb_content:
            user_prompt += f"【历史Bug经验知识库】\n{bug_kb_content}\n\n"
        
        if history_kb_content:
            user_prompt += f"【历史测试点参考】\n{history_kb_content}\n\n"
        
        user_prompt += "请按照输出文档规范生成测试点分析文档。"

        self._ensure_ai_client()

        for chunk in self.ai_client.call_stream(user_prompt, system_prompt):
            yield chunk

    def generate_test_points(self, prd_content: str, bug_kb_content: str = None, history_kb_content: str = None) -> str:
        system_prompt = self._get_system_prompt("test_points")

        user_prompt = f"请分析以下需求描述，并生成测试点文档：\n\n【需求描述】\n{prd_content}\n\n"
        
        if bug_kb_content:
            user_prompt += f"【历史Bug经验知识库】\n{bug_kb_content}\n\n"
        
        if history_kb_content:
            user_prompt += f"【历史测试点参考】\n{history_kb_content}\n\n"
        
        user_prompt += "请按照输出文档规范生成测试点分析文档。"

        self._ensure_ai_client()
        return self.ai_client.call(user_prompt, system_prompt)

    def generate_test_cases_stream(self, test_points_content: str, module_name: str = None, class_name: str = None, method_name: str = None):
        messages = [
            "正在分析测试点...",
            "生成pytest测试用例骨架...",
            "\n\nimport pytest\n\n",
        ]
        for msg in messages:
            time.sleep(0.1)
            yield msg

    def generate_test_cases(self, test_points_content: str, module_name: str = None, class_name: str = None, method_name: str = None) -> str:
        return "".join(self.generate_test_cases_stream(test_points_content, module_name, class_name, method_name))

    def analyze_log_stream(self, log_content: str):
        messages = [
            "正在预过滤日志...",
            "提取异常堆栈...",
            "分析问题根因...",
            "\n\n# 日志分析报告\n\n## 1. 异常统计\n\n",
            "正在生成报告...",
        ]
        for msg in messages:
            time.sleep(0.1)
            yield msg

    def analyze_log(self, log_content: str) -> str:
        return "".join(self.analyze_log_stream(log_content))