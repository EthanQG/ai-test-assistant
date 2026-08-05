from __future__ import annotations

from copy import deepcopy

from agent import TestAnalysisState


def make_test_point(title: str = "库存充足时创建订单") -> dict:
    return {
        "title": title,
        "category": "functional",
        "priority": "P0",
        "scenario": "用户提交订单时校验库存",
        "preconditions": ["商品库存为1"],
        "steps": ["提交包含该商品的订单"],
        "expected_results": ["订单创建成功且库存扣减为0"],
        "sources": ["requirement"],
        "source_refs": ["需求事实：库存充足时创建订单"],
    }


def make_review_result() -> dict:
    return {
        "overall_score": 92,
        "dimension_scores": {
            "requirement_coverage": 95,
            "boundary_exception": 88,
            "executability": 92,
            "traceability": 94,
        },
        "requirement_coverage": [
            {
                "requirement_fact": "库存充足时创建订单",
                "status": "covered",
                "covered_by": ["库存充足时创建订单"],
                "gap": "",
            }
        ],
        "missing_scenarios": [],
        "duplicate_groups": [],
        "hallucination_issues": [],
        "revision_suggestions": [],
    }


def make_eligible_state() -> TestAnalysisState:
    state = TestAnalysisState(
        "用户提交订单时校验库存，库存充足则创建订单并扣减库存。"
    )
    state.requirement_summary = "订单创建前需要校验并扣减库存"
    state.modules = ["订单", "库存"]
    state.requirement_facts = ["库存充足时创建订单"]
    state.business_rules = ["创建订单后库存扣减1"]
    state.state_transitions = ["待提交 -> 已创建"]
    state.inferred_risks = [
        {"risk": "并发超卖", "basis": "库存存在并发扣减"}
    ]
    state.test_points = [make_test_point()]
    state.review_result = make_review_result()
    state.review_passed = True
    state.review_threshold = 80
    state.final_result = {
        "test_points": deepcopy(state.test_points),
        "quality_summary": {"overall_score": 92},
    }
    state.complete("# 订单测试分析报告")
    return state
