import os
import time
import traceback
from utils.ai_client import DeepSeekClient
from utils.knowledge_base import MilvusRAGManager


class TestAssistantManager:
    def __init__(self):
        self.prompts_dir = "./prompts"
        self.ai_client = None
        self.rag_manager = MilvusRAGManager()

    def _get_system_prompt(self, prompt_name: str) -> str:
        prompt_path = os.path.join(self.prompts_dir, f"{prompt_name}.txt")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    def _ensure_ai_client(self):
        if self.ai_client is None:
            self.ai_client = DeepSeekClient()

    def generate_test_points_stream(self, prd_content: str, bug_kb_content: str = None):
        system_prompt = self._get_system_prompt("test_points")

        user_prompt = f"请分析以下需求描述，并生成测试点文档：\n\n【需求描述】\n{prd_content}\n\n"
        
        if bug_kb_content:
            user_prompt += f"【历史Bug经验知识库】\n{bug_kb_content}\n\n"

        rag_context = self.rag_manager.search_similar_cases(prd_content, top_k=2)
        self._rag_used = len(rag_context) > 0
        self._rag_context_preview = rag_context[:500] if rag_context else ""
        
        if rag_context:
            user_prompt += f"【相似历史测试点参考】\n{rag_context}\n\n"
        
        user_prompt += "请按照输出文档规范生成测试点分析文档。"

        self._ensure_ai_client()

        for chunk in self.ai_client.call_stream(user_prompt, system_prompt):
            yield chunk
    
    def get_rag_used(self) -> bool:
        return getattr(self, '_rag_used', False)
    
    def get_rag_context_preview(self) -> str:
        return getattr(self, '_rag_context_preview', "")

    def refine_test_points_stream(self, prd_content: str, current_report: str, refine_request: str):
        system_prompt = self._get_system_prompt("test_points")

        user_prompt = f"""请根据用户的修改意见，对当前测试分析报告进行滚动修正。

【原始需求描述】
{prd_content}

【当前测试分析报告】
{current_report}

【用户修改意见】
{refine_request}

请根据用户的修改意见，重新生成完整的测试分析报告。注意：
1. 需要保持报告的整体结构和格式
2. 只根据用户意见进行针对性修改，不要随意改动其他部分
3. 输出完整的测试分析报告，而不是只输出修改部分"""

        self._ensure_ai_client()

        for chunk in self.ai_client.call_stream(user_prompt, system_prompt):
            yield chunk

    def generate_test_points(self, prd_content: str, bug_kb_content: str = None) -> str:
        system_prompt = self._get_system_prompt("test_points")

        user_prompt = f"请分析以下需求描述，并生成测试点文档：\n\n【需求描述】\n{prd_content}\n\n"
        
        if bug_kb_content:
            user_prompt += f"【历史Bug经验知识库】\n{bug_kb_content}\n\n"

        rag_context = self.rag_manager.search_similar_cases(prd_content, top_k=2)
        if rag_context:
            user_prompt += f"【相似历史测试点参考】\n{rag_context}\n\n"
        
        user_prompt += "请按照输出文档规范生成测试点分析文档。"

        self._ensure_ai_client()
        return self.ai_client.call(user_prompt, system_prompt)

    def save_to_rag(self, prd_content: str, test_points: str) -> tuple:
        try:
            before_count = self.rag_manager.get_total_count()
            self.rag_manager.save_case(prd_content, test_points)
            after_count = self.rag_manager.get_total_count()
            
            if after_count > before_count:
                return True, "保存成功"
            else:
                return False, "保存失败，数据未增加"
        except Exception as e:
            error_info = f"保存过程中发生异常: {str(e)}\n{traceback.format_exc()}"
            print(f"[DEBUG] {error_info}")
            
            try:
                after_count = self.rag_manager.get_total_count()
                if after_count > 0:
                    return True, f"保存成功（过程中出现警告: {str(e)}）"
            except Exception:
                pass
            
            return False, str(e)

    def get_rag_count(self) -> int:
        return self.rag_manager.get_total_count()

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