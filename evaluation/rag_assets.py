"""Synthetic authoritative assets used only by the RAG evaluation."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from agent import InferredRisk, TestPoint, TestPointReviewResult
from knowledge_assets import (
    KnowledgeAsset,
    KnowledgeAssetStatus,
    StructuredRequirement,
    build_content_hash,
)


def load_rag_seed_assets(path: Path) -> tuple[KnowledgeAsset, ...]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    if dataset.get("schema_version") != 1:
        raise ValueError("unsupported RAG asset seed schema_version")
    confirmed_at = datetime.fromisoformat(dataset["confirmed_at"])
    if confirmed_at.tzinfo is None:
        raise ValueError("RAG asset seed confirmed_at must include timezone")
    assets = tuple(
        _build_asset(item, confirmed_at) for item in dataset["assets"]
    )
    if len({asset.asset_id for asset in assets}) != len(assets):
        raise ValueError("RAG asset seed asset_id values must be unique")
    return assets


def _build_asset(item: dict, confirmed_at: datetime) -> KnowledgeAsset:
    fact = item["fact"].strip()
    title = item["test_title"].strip()
    test_point = TestPoint.from_dict(
        {
            "title": title,
            "category": "functional",
            "priority": "P0",
            "scenario": item["requirement"].strip(),
            "preconditions": ["使用满足该业务场景的测试账号和数据"],
            "steps": [title],
            "expected_results": [item["rule"].strip()],
            "sources": ["requirement"],
            "source_refs": [fact],
        }
    )
    requirement = StructuredRequirement(
        summary=item["summary"].strip(),
        modules=(item["module"].strip(),),
        requirement_facts=(fact,),
        business_rules=(item["rule"].strip(),),
        state_transitions=(),
        inferred_risks=(
            InferredRisk(
                risk=item["risk"].strip(),
                basis=item["requirement"].strip(),
            ),
        ),
    )
    review = TestPointReviewResult.from_dict(
        {
            "overall_score": 90,
            "dimension_scores": {
                "requirement_coverage": 90,
                "boundary_exception": 90,
                "executability": 90,
                "traceability": 90,
            },
            "requirement_coverage": [
                {
                    "requirement_fact": fact,
                    "status": "covered",
                    "covered_by": [title],
                    "gap": "",
                }
            ],
            "missing_scenarios": [],
            "duplicate_groups": [],
            "hallucination_issues": [],
            "revision_suggestions": [],
        }
    )
    test_points = (test_point,)
    original_requirement = item["requirement"].strip()
    return KnowledgeAsset(
        asset_id=item["asset_id"].strip(),
        source_task_id=item["source_task_id"].strip(),
        asset_version=1,
        content_hash=build_content_hash(
            original_requirement,
            requirement,
            test_points,
        ),
        status=KnowledgeAssetStatus.PENDING_INDEX,
        original_requirement=original_requirement,
        structured_requirement=requirement,
        test_points=test_points,
        review_result=review,
        final_report=f"# {item['summary'].strip()}\n\n合成RAG评测资产。",
        user_confirmed=True,
        data_safety_confirmed=True,
        confirmed_at=confirmed_at,
        created_at=confirmed_at,
    )
