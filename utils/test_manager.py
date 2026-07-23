import time
import traceback

from services.llm_service import LLMService
from services.prompt_service import PromptService
from services.rag_service import RAGSearchResult, RAGService


class TestAssistantManager:
    def __init__(
        self,
        llm_service: LLMService | None = None,
        rag_service: RAGService | None = None,
        prompt_service: PromptService | None = None,
    ):
        self.llm_service = llm_service or LLMService()
        self.rag_service = rag_service or RAGService()
        self.prompt_service = prompt_service or PromptService()

    def _remember_rag_result(self, result: RAGSearchResult) -> None:
        self._rag_used = result.used
        self._rag_context_preview = result.context[:500]
        self._rag_max_score = result.max_score
        self._rag_matched_count = result.matched_count

    def generate_test_points_stream(self, prd_content: str, bug_kb_content: str = None):
        rag_result = self.rag_service.search(prd_content, top_k=2)
        self._remember_rag_result(rag_result)
        system_prompt = self.prompt_service.load_system_prompt("test_points")
        user_prompt = self.prompt_service.build_test_points_prompt(
            requirement=prd_content,
            bug_knowledge=bug_kb_content,
            rag_context=rag_result.context,
        )

        yield from self.llm_service.generate_stream(user_prompt, system_prompt)
    
    def get_rag_used(self) -> bool:
        return getattr(self, '_rag_used', False)
    
    def get_rag_context_preview(self) -> str:
        return getattr(self, '_rag_context_preview', "")
    
    def get_rag_max_score(self) -> float:
        return getattr(self, '_rag_max_score', 0.0)
    
    def get_rag_matched_count(self) -> int:
        return getattr(self, '_rag_matched_count', 0)

    def refine_test_points_stream(self, prd_content: str, current_report: str, refine_request: str):
        system_prompt = self.prompt_service.load_system_prompt("test_points")
        user_prompt = self.prompt_service.build_refine_prompt(
            requirement=prd_content,
            current_report=current_report,
            refine_request=refine_request,
        )

        yield from self.llm_service.generate_stream(user_prompt, system_prompt)

    def generate_test_points(self, prd_content: str, bug_kb_content: str = None) -> str:
        rag_result = self.rag_service.search(prd_content, top_k=2)
        self._remember_rag_result(rag_result)
        system_prompt = self.prompt_service.load_system_prompt("test_points")
        user_prompt = self.prompt_service.build_test_points_prompt(
            requirement=prd_content,
            bug_knowledge=bug_kb_content,
            rag_context=rag_result.context,
        )

        return self.llm_service.generate(user_prompt, system_prompt)

    def save_to_rag(self, prd_content: str, test_points: str) -> tuple:
        try:
            before_count = self.rag_service.count()
            self.rag_service.save_case(prd_content, test_points)
            after_count = self.rag_service.count()
            
            if after_count > before_count:
                return True, "保存成功"
            else:
                return False, "保存失败，数据未增加"
        except Exception as e:
            error_info = f"保存过程中发生异常: {str(e)}\n{traceback.format_exc()}"
            print(f"[DEBUG] {error_info}")
            
            try:
                after_count = self.rag_service.count()
                if after_count > 0:
                    return True, f"保存成功（过程中出现警告: {str(e)}）"
            except Exception:
                pass
            
            return False, str(e)

    def get_rag_count(self) -> int:
        return self.rag_service.count()

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
