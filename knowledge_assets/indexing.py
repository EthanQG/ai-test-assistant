from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import KnowledgeAsset


class KnowledgeAssetChunkType(str, Enum):
    OVERVIEW = "overview"
    REQUIREMENT_FACT = "requirement_fact"
    BUSINESS_RULE = "business_rule"
    RISK = "risk"
    TEST_POINT = "test_point"


@dataclass(frozen=True)
class KnowledgeAssetChunk:
    chunk_id: str
    asset_id: str
    source_task_id: str
    asset_version: int
    content_hash: str
    chunk_type: KnowledgeAssetChunkType
    chunk_index: int
    search_text: str
    was_truncated: bool = False


@dataclass(frozen=True)
class KnowledgeAssetChunkBuildResult:
    chunks: tuple[KnowledgeAssetChunk, ...]
    candidate_count: int
    omitted_count: int


class KnowledgeAssetChunkBuilder:
    """Builds bounded, self-contained semantic units without using an LLM."""

    def __init__(
        self,
        *,
        max_chunks: int = 32,
        max_text_chars: int = 1600,
    ):
        if max_chunks <= 0:
            raise ValueError("max_chunks must be positive")
        if max_text_chars < 200:
            raise ValueError("max_text_chars must be at least 200")
        self._max_chunks = max_chunks
        self._max_text_chars = max_text_chars

    def build(self, asset: KnowledgeAsset) -> KnowledgeAssetChunkBuildResult:
        candidates = self._candidate_texts(asset)
        selected = candidates[: self._max_chunks]
        chunks = tuple(
            self._chunk(asset, chunk_type, index, text)
            for index, (chunk_type, text) in enumerate(selected)
        )
        return KnowledgeAssetChunkBuildResult(
            chunks=chunks,
            candidate_count=len(candidates),
            omitted_count=max(0, len(candidates) - len(chunks)),
        )

    def _candidate_texts(
        self,
        asset: KnowledgeAsset,
    ) -> list[tuple[KnowledgeAssetChunkType, str]]:
        requirement = asset.structured_requirement
        modules = "、".join(requirement.modules) or "未标注"
        prefix = (
            f"需求主题：{requirement.summary}\n"
            f"所属模块：{modules}\n"
        )
        candidates: list[tuple[KnowledgeAssetChunkType, str]] = [
            (
                KnowledgeAssetChunkType.OVERVIEW,
                prefix
                + "知识类型：需求概览\n"
                + f"原始需求摘要：{asset.original_requirement}",
            )
        ]
        candidates.extend(
            (
                KnowledgeAssetChunkType.REQUIREMENT_FACT,
                prefix + "知识类型：需求事实\n" + f"需求事实：{fact}",
            )
            for fact in requirement.requirement_facts
        )
        candidates.extend(
            (
                KnowledgeAssetChunkType.BUSINESS_RULE,
                prefix + "知识类型：业务规则\n" + f"业务规则：{rule}",
            )
            for rule in requirement.business_rules
        )
        candidates.extend(
            (
                KnowledgeAssetChunkType.RISK,
                prefix
                + "知识类型：推导风险\n"
                + f"风险：{risk.risk}\n推导依据：{risk.basis}",
            )
            for risk in requirement.inferred_risks
        )
        candidates.extend(
            (
                KnowledgeAssetChunkType.TEST_POINT,
                prefix
                + "知识类型：结构化测试点\n"
                + f"标题：{point.title}\n"
                + f"分类：{point.category.value}\n"
                + f"优先级：{point.priority.value}\n"
                + f"场景：{point.scenario}\n"
                + "预期结果："
                + "；".join(point.expected_results),
            )
            for point in asset.test_points
        )
        return candidates

    def _chunk(
        self,
        asset: KnowledgeAsset,
        chunk_type: KnowledgeAssetChunkType,
        index: int,
        text: str,
    ) -> KnowledgeAssetChunk:
        cleaned = text.strip()
        was_truncated = len(cleaned) > self._max_text_chars
        if was_truncated:
            cleaned = cleaned[: self._max_text_chars].rstrip() + "…"
        return KnowledgeAssetChunk(
            chunk_id=(
                f"{asset.asset_id}:{asset.asset_version}:"
                f"{chunk_type.value}:{index}"
            ),
            asset_id=asset.asset_id,
            source_task_id=asset.source_task_id,
            asset_version=asset.asset_version,
            content_hash=asset.content_hash,
            chunk_type=chunk_type,
            chunk_index=index,
            search_text=cleaned,
            was_truncated=was_truncated,
        )
