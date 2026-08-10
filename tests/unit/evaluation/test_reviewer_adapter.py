from agent import TestPointReviewResult
from evaluation.reviewer import review_result_to_defects


def _review_result():
    return TestPointReviewResult.from_dict(
        {
            "overall_score": 60,
            "dimension_scores": {
                "requirement_coverage": 50,
                "boundary_exception": 50,
                "executability": 60,
                "traceability": 60,
            },
            "requirement_coverage": [
                {
                    "requirement_fact": "库存不足时拒绝创建订单",
                    "status": "missing",
                    "covered_by": [],
                    "gap": "没有库存不足场景",
                }
            ],
            "missing_scenarios": [
                "优惠券199.99元边界",
                "普通成功场景",
            ],
            "duplicate_groups": [["库存足够创建", "库存充足下单"]],
            "hallucination_issues": [
                {
                    "test_point_title": "支付回调失败",
                    "issue": "包含无依据行为",
                    "unsupported_claim": "需求没有规定自动重试3次",
                }
            ],
            "revision_suggestions": [
                "库存不足：预期模糊，需要明确预期结果",
                "取消订单支付回调：缺少来源引用",
                "建议优化测试数据准备方式",
            ],
        }
    )


def test_review_result_adapter_maps_all_supported_structured_signals():
    defects = review_result_to_defects(
        _review_result(),
        test_point_titles=("库存不足", "取消订单支付回调"),
    )

    assert {(item.defect_type, item.target) for item in defects} == {
        ("requirement_omission", "库存不足时拒绝创建订单"),
        ("boundary_missing", "优惠券199.99元边界"),
        ("duplicate_test_point", "库存足够创建|库存充足下单"),
        ("unsupported_assertion", "支付回调失败"),
        ("vague_expectation", "库存不足"),
        ("missing_source", "取消订单支付回调"),
    }


def test_review_result_adapter_ignores_unclassified_free_text():
    review = TestPointReviewResult.from_dict(
        {
            "overall_score": 90,
            "dimension_scores": {
                "requirement_coverage": 90,
                "boundary_exception": 90,
                "executability": 90,
                "traceability": 90,
            },
            "requirement_coverage": [],
            "missing_scenarios": ["增加更多业务场景"],
            "duplicate_groups": [],
            "hallucination_issues": [],
            "revision_suggestions": ["可以进一步优化表达"],
        }
    )

    assert review_result_to_defects(review) == ()
