import re


_GENERIC_PREFIX = re.compile(
    r"^(?:需求名称|项目名称|功能名称|标题)\s*[:：]\s*",
    re.IGNORECASE,
)


def derive_task_name(
    requirement: str,
    requirement_summary: str = "",
    *,
    max_length: int = 48,
) -> str:
    """Derive a stable display name without an additional LLM call."""

    for source in (requirement, requirement_summary):
        for raw_line in source.splitlines():
            candidate = raw_line.strip()
            if not candidate or candidate.startswith(("![", "|", "```")):
                continue
            candidate = re.sub(r"^#{1,6}\s*", "", candidate)
            candidate = re.sub(r"^[-*+]\s+", "", candidate)
            candidate = _GENERIC_PREFIX.sub("", candidate).strip(" ：:-—")
            if candidate:
                if len(candidate) > 30:
                    short = re.split(r"[，,。；;]", candidate, maxsplit=1)[0]
                    if len(short) >= 6:
                        candidate = short
                return candidate[:max_length]
    return "未命名测试分析"


def safe_report_filename(task_name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", task_name).strip(" ._")
    return f"{(cleaned or '测试分析报告')[:80]}-测试分析报告.md"
