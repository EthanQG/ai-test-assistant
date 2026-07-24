import json
from pathlib import Path


class PromptService:
    """Loads stable system prompts and builds task-specific user prompts."""

    def __init__(self, prompts_dir: Path | str | None = None):
        default_dir = Path(__file__).resolve().parent.parent / "prompts"
        self._prompts_dir = Path(prompts_dir) if prompts_dir else default_dir

    def load_system_prompt(self, prompt_name: str) -> str:
        prompt_path = self._prompts_dir / f"{prompt_name}.txt"
        if not prompt_path.exists():
            return ""
        return prompt_path.read_text(encoding="utf-8").strip()

    @staticmethod
    def build_test_points_prompt(
        requirement: str,
        bug_knowledge: str | None = None,
        rag_context: str | None = None,
    ) -> str:
        sections = [
            "请分析以下需求，并生成测试点分析文档。",
            f"【当前需求】\n{requirement.strip()}",
        ]

        if bug_knowledge and bug_knowledge.strip():
            sections.append(
                "【本地历史 Bug 经验】\n"
                f"{bug_knowledge.strip()}"
            )

        if rag_context and rag_context.strip():
            sections.append(
                "【向量检索召回的相似历史测试资产】\n"
                f"{rag_context.strip()}"
            )

        sections.append(
            "请先核对需求事实，再区分“需求事实”“推导风险”和“待确认项”，"
            "最后按照系统要求输出完整的测试点分析文档。"
        )
        return "\n\n".join(sections)

    @staticmethod
    def build_requirement_analysis_prompt(requirement: str) -> str:
        cleaned_requirement = requirement.strip()
        if not cleaned_requirement:
            raise ValueError("requirement cannot be empty")
        return (
            "请对以下原始需求进行结构化分析，并严格按照系统要求只返回 JSON。\n\n"
            f"【原始需求】\n{cleaned_requirement}"
        )

    @staticmethod
    def build_structured_test_points_prompt(
        requirement_analysis: dict,
        local_bug_knowledge: str | None = None,
        rag_context: str | None = None,
    ) -> str:
        if not requirement_analysis.get("summary"):
            raise ValueError("requirement analysis summary cannot be empty")

        sections = [
            "请根据以下结构化需求分析生成测试点，并严格按照系统要求只返回 JSON。",
            "【结构化需求分析】\n"
            + json.dumps(
                requirement_analysis,
                ensure_ascii=False,
                indent=2,
            ),
        ]
        if local_bug_knowledge and local_bug_knowledge.strip():
            sections.append(
                "【本地测试经验】\n" + local_bug_knowledge.strip()
            )
        if rag_context and rag_context.strip():
            sections.append(
                "【相似历史测试资产】\n" + rag_context.strip()
            )
        sections.append(
            "历史资产只能提供测试思路，不能覆盖当前需求事实；"
            "每个测试点必须通过 sources 和 source_refs 说明来源。"
        )
        return "\n\n".join(sections)

    @staticmethod
    def build_test_point_review_prompt(
        requirement_analysis: dict,
        test_points: list[dict],
    ) -> str:
        if not requirement_analysis.get("requirement_facts"):
            raise ValueError("requirement facts cannot be empty")
        if not test_points:
            raise ValueError("test points cannot be empty")
        return (
            "请评审以下结构化测试点，并严格按照系统要求只返回 JSON。\n\n"
            "【结构化需求分析】\n"
            + json.dumps(
                requirement_analysis,
                ensure_ascii=False,
                indent=2,
            )
            + "\n\n【待评审测试点】\n"
            + json.dumps(
                test_points,
                ensure_ascii=False,
                indent=2,
            )
        )

    @staticmethod
    def build_test_point_revision_prompt(
        requirement_analysis: dict,
        current_test_points: list[dict],
        review_result: dict | None = None,
        human_feedback: list[dict] | None = None,
    ) -> str:
        if not requirement_analysis.get("requirement_facts"):
            raise ValueError("requirement facts cannot be empty")
        if not current_test_points:
            raise ValueError("current test points cannot be empty")
        if not review_result and not human_feedback:
            raise ValueError(
                "review result or human feedback is required"
            )
        prompt = (
            "请根据评审结果定向修正测试点，并严格按照系统要求只返回 JSON。\n\n"
            "【结构化需求分析】\n"
            + json.dumps(
                requirement_analysis,
                ensure_ascii=False,
                indent=2,
            )
            + "\n\n【当前测试点】\n"
            + json.dumps(
                current_test_points,
                ensure_ascii=False,
                indent=2,
            )
        )
        if review_result:
            prompt += (
                "\n\n【Reviewer评审结果】\n"
                + json.dumps(
                    review_result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
        if human_feedback:
            prompt += (
                "\n\n【已确认的人工反馈】\n"
                + json.dumps(
                    human_feedback,
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return prompt

    @staticmethod
    def build_refine_prompt(
        requirement: str,
        current_report: str,
        refine_request: str,
    ) -> str:
        return f"""请根据用户的修改意见，对当前测试分析报告进行修正。

【原始需求】
{requirement.strip()}

【当前测试分析报告】
{current_report.strip()}

【用户修改意见】
{refine_request.strip()}

请输出修正后的完整测试分析报告。要求：
1. 保持报告的整体结构和格式
2. 只根据用户意见进行针对性修改，不随意改动其他部分
3. 不将修改意见中未经需求确认的信息错误标记为需求事实
4. 输出完整报告，而不是只输出修改部分"""
