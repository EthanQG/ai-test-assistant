import json
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from agent import (
    AgentEvent,
    AgentEventType,
    AgentStatus,
    AgentStep,
    KnowledgeRetrievalStatus,
    OrchestratorAction,
    OrchestratorDecision,
    TestAnalysisState,
)
from application import (
    NodeExecutionMetric,
    SNAPSHOT_SCHEMA_VERSION,
    SnapshotValidationError,
    TaskRecord,
    TaskSnapshotSerializer,
    UnsupportedSnapshotVersionError,
    migrate_snapshot,
)


TEST_POINT = {
    "title": "库存充足时创建订单",
    "category": "functional",
    "priority": "P0",
    "scenario": "用户提交订单且库存充足",
    "preconditions": ["商品库存为10"],
    "steps": ["提交购买数量为1的订单"],
    "expected_results": ["订单创建成功", "库存扣减为9"],
    "sources": ["requirement", "historical_asset"],
    "source_refs": ["需求事实1", "历史资产A"],
}

REVIEW_RESULT = {
    "overall_score": 78,
    "dimension_scores": {
        "requirement_coverage": 80,
        "boundary_exception": 70,
        "executability": 85,
        "traceability": 77,
    },
    "requirement_coverage": [
        {
            "requirement_fact": "库存充足时创建订单",
            "status": "covered",
            "covered_by": ["库存充足时创建订单"],
            "gap": "",
        }
    ],
    "missing_scenarios": ["库存并发扣减"],
    "duplicate_groups": [],
    "hallucination_issues": [],
    "revision_suggestions": ["补充并发场景"],
}


def build_full_record() -> TaskRecord:
    created_at = datetime(
        2026,
        7,
        30,
        8,
        0,
        tzinfo=timezone(timedelta(hours=8)),
    )
    updated_at = created_at + timedelta(minutes=3)
    state = TestAnalysisState(
        "用户提交订单时校验库存",
        task_id="task-snapshot-001",
    )
    state.status = AgentStatus.RUNNING
    state.current_step = AgentStep.REVISE_TEST_POINTS
    state.requirement_summary = "订单创建与库存扣减"
    state.modules = ["订单", "库存"]
    state.requirement_facts = ["库存充足时创建订单"]
    state.business_rules = ["库存不可为负数"]
    state.state_transitions = ["待提交 -> 已创建"]
    state.inferred_risks = [
        {"risk": "并发超卖", "basis": "库存会被并发扣减"}
    ]
    state.open_questions = ["库存锁策略是什么？"]
    state.user_clarifications = [
        {"question": "是否允许超卖？", "answer": "不允许"}
    ]
    state.deferred_questions = ["库存锁策略是什么？"]
    state.local_bug_knowledge = "曾发生重复扣减"
    state.rag_context = "历史资产：并发扣减测试"
    state.rag_max_score = 0.91
    state.rag_matched_count = 2
    state.knowledge_retrieval_status = (
        KnowledgeRetrievalStatus.MATCHED
    )
    state.rag_error_message = None
    state.test_points = [deepcopy(TEST_POINT)]
    state.review_result = deepcopy(REVIEW_RESULT)
    state.review_passed = False
    state.review_threshold = 80
    state.review_history = [
        {
            "review_round": 1,
            "revision_count": 0,
            "automatic_revision_count": 0,
            "human_revision_count": 0,
            "passed": False,
            "result": deepcopy(REVIEW_RESULT),
        }
    ]
    state.revision_count = 1
    state.automatic_revision_count = 1
    state.human_revision_count = 0
    state.max_revision_count = 2
    state.revision_history = [
        {
            "revision_count": 1,
            "revision_source": "automatic_review",
            "before_test_points": [deepcopy(TEST_POINT)],
            "after_test_points": [deepcopy(TEST_POINT)],
            "review_result": deepcopy(REVIEW_RESULT),
            "applied_feedback_ids": [],
        }
    ]
    state.human_feedback = [
        {
            "feedback_id": "feedback-001",
            "action": "add",
            "feedback_type": "business_rule",
            "target": "业务规则",
            "content": "库存不可为负数",
            "reason": "需要限制超卖",
            "status": "applied",
        }
    ]
    state.final_result = {
        "requirement_summary": state.requirement_summary,
        "modules": ["订单", "库存"],
        "test_point_count": 1,
        "category_counts": {"functional": 1},
        "priority_counts": {"P0": 1},
        "source_counts": {"requirement": 1, "historical_asset": 1},
        "coverage_summary": {
            "total": 1,
            "covered": 1,
            "partial": 0,
            "missing": 0,
        },
        "quality_summary": {
            "overall_score": 78,
            "review_threshold": 80,
            "dimension_scores": deepcopy(
                REVIEW_RESULT["dimension_scores"]
            ),
            "review_rounds": 1,
            "revision_count": 1,
            "automatic_revision_count": 1,
            "human_revision_count": 0,
        },
        "inferred_risks": deepcopy(state.inferred_risks),
        "test_points": [deepcopy(TEST_POINT)],
        "warnings": [],
    }
    state.report = "# 测试分析报告"
    state.error_message = None
    state.events = [
        AgentEvent(
            event_type=AgentEventType.STEP_COMPLETED,
            step=AgentStep.REVIEW_TEST_POINTS,
            message="结构化测试点质量评审完成",
            data={"overall_score": 78, "passed": False},
            occurred_at=updated_at,
        )
    ]
    state.created_at = created_at
    state.updated_at = updated_at
    return TaskRecord(
        state=state,
        decisions=[
            OrchestratorDecision(
                action=OrchestratorAction.REVISE_TEST_POINTS,
                reason="当前测试点未通过质量评审",
                duration_seconds=0.02,
            )
        ],
        auto_run=True,
        pending_clarifications={
            "库存锁策略是什么？": "使用数据库行锁"
        },
        execution_steps=5,
        in_progress=True,
        next_action=OrchestratorAction.REVISE_TEST_POINTS.value,
        metrics=[
            NodeExecutionMetric(
                action=OrchestratorAction.REVIEW_TEST_POINTS.value,
                started_at=created_at,
                finished_at=updated_at,
                duration_seconds=180.0,
                succeeded=True,
            ),
            NodeExecutionMetric(
                action=OrchestratorAction.REVISE_TEST_POINTS.value,
                started_at=updated_at,
                finished_at=updated_at + timedelta(seconds=2),
                duration_seconds=2.0,
                succeeded=False,
                error_type="TimeoutError",
            ),
        ],
    )


class TaskSnapshotSerializerTests(unittest.TestCase):
    def setUp(self):
        self.record = build_full_record()
        self.payload = TaskSnapshotSerializer.to_dict(self.record)

    def test_full_record_dict_round_trip_preserves_business_semantics(self):
        restored = TaskSnapshotSerializer.from_dict(self.payload)

        self.assertEqual(restored.state.task_id, "task-snapshot-001")
        self.assertEqual(
            TaskSnapshotSerializer.to_dict(restored),
            self.payload,
        )
        self.assertEqual(restored.decisions, self.record.decisions)
        self.assertEqual(restored.metrics, self.record.metrics)
        self.assertEqual(
            restored.pending_clarifications,
            self.record.pending_clarifications,
        )
        self.assertEqual(restored.next_action, self.record.next_action)
        self.assertFalse(restored.in_progress)

    def test_json_round_trip_uses_standard_json(self):
        raw = TaskSnapshotSerializer.to_json(self.record)
        decoded = json.loads(raw)
        restored = TaskSnapshotSerializer.from_json(raw)

        self.assertEqual(
            decoded["schema_version"],
            SNAPSHOT_SCHEMA_VERSION,
        )
        self.assertEqual(
            restored.state.requirement_summary,
            "订单创建与库存扣减",
        )
        json.dumps(self.payload)

    def test_enums_are_restored_as_domain_types(self):
        restored = TaskSnapshotSerializer.from_dict(self.payload)

        self.assertIsInstance(restored.state.status, AgentStatus)
        self.assertIsInstance(restored.state.current_step, AgentStep)
        self.assertIsInstance(
            restored.state.knowledge_retrieval_status,
            KnowledgeRetrievalStatus,
        )
        self.assertIsInstance(
            restored.state.events[0].event_type,
            AgentEventType,
        )
        self.assertIsInstance(
            restored.decisions[0].action,
            OrchestratorAction,
        )

    def test_times_are_restored_as_timezone_aware_utc_datetimes(self):
        restored = TaskSnapshotSerializer.from_dict(self.payload)

        times = [
            restored.state.created_at,
            restored.state.updated_at,
            restored.state.events[0].occurred_at,
            restored.metrics[0].started_at,
            restored.metrics[0].finished_at,
        ]
        self.assertTrue(all(item.utcoffset() is not None for item in times))
        self.assertTrue(
            all(item.utcoffset() == timedelta(0) for item in times)
        )

    def test_agent_event_is_restored_as_agent_event(self):
        restored = TaskSnapshotSerializer.from_dict(self.payload)
        event = restored.state.events[0]

        self.assertIsInstance(event, AgentEvent)
        self.assertEqual(event.data["overall_score"], 78)

    def test_test_point_nested_lists_are_restored(self):
        restored = TaskSnapshotSerializer.from_dict(self.payload)
        point = restored.state.test_points[0]

        self.assertEqual(point["steps"], TEST_POINT["steps"])
        self.assertEqual(
            point["expected_results"],
            TEST_POINT["expected_results"],
        )
        self.assertEqual(point["sources"], TEST_POINT["sources"])

    def test_waiting_for_clarification_state_is_restorable(self):
        self.payload["state"]["status"] = "waiting_for_user"
        self.payload["state"]["current_step"] = "analyze_requirement"
        restored = TaskSnapshotSerializer.from_dict(self.payload)

        self.assertEqual(restored.state.status, AgentStatus.WAITING_FOR_USER)
        self.assertEqual(
            restored.pending_clarifications[
                "库存锁策略是什么？"
            ],
            "使用数据库行锁",
        )

    def test_waiting_for_business_rule_confirmation_is_restorable(self):
        self.payload["state"]["status"] = "waiting_for_user"
        self.payload["state"]["human_feedback"][0]["status"] = (
            "pending_confirmation"
        )
        self.payload["application"]["pending_clarifications"] = None
        restored = TaskSnapshotSerializer.from_dict(self.payload)

        self.assertEqual(
            restored.state.human_feedback[0]["status"],
            "pending_confirmation",
        )

    def test_failed_review_waiting_for_revision_is_restorable(self):
        restored = TaskSnapshotSerializer.from_dict(self.payload)

        self.assertFalse(restored.state.review_passed)
        self.assertEqual(restored.state.revision_count, 1)
        self.assertEqual(
            restored.next_action,
            OrchestratorAction.REVISE_TEST_POINTS.value,
        )

    def test_completed_state_is_restorable(self):
        self.payload["state"]["status"] = "completed"
        self.payload["state"]["current_step"] = "finalize"
        self.payload["application"]["auto_run"] = False
        self.payload["application"]["next_action"] = "terminal"
        restored = TaskSnapshotSerializer.from_dict(self.payload)

        self.assertEqual(restored.state.status, AgentStatus.COMPLETED)
        self.assertEqual(restored.state.report, "# 测试分析报告")
        self.assertIsNotNone(restored.state.final_result)

    def test_failed_state_and_error_are_restorable(self):
        self.payload["state"]["status"] = "failed"
        self.payload["state"]["error_message"] = "LLM响应超时"
        self.payload["application"]["auto_run"] = False
        self.payload["application"]["next_action"] = "terminal"
        restored = TaskSnapshotSerializer.from_dict(self.payload)

        self.assertEqual(restored.state.status, AgentStatus.FAILED)
        self.assertEqual(restored.state.error_message, "LLM响应超时")

    def test_human_feedback_rag_and_metrics_are_restored(self):
        restored = TaskSnapshotSerializer.from_dict(self.payload)

        self.assertEqual(
            restored.state.human_feedback[0]["feedback_id"],
            "feedback-001",
        )
        self.assertEqual(restored.state.rag_matched_count, 2)
        self.assertEqual(restored.state.rag_max_score, 0.91)
        self.assertEqual(restored.metrics[1].error_type, "TimeoutError")

    def test_empty_lists_and_optional_fields_are_supported(self):
        record = TaskRecord(TestAnalysisState("简单需求"))
        record.state.events = []
        restored = TaskSnapshotSerializer.from_json(
            TaskSnapshotSerializer.to_json(record)
        )

        self.assertEqual(restored.state.events, [])
        self.assertEqual(restored.state.test_points, [])
        self.assertIsNone(restored.state.review_result)
        self.assertIsNone(restored.pending_clarifications)

    def test_missing_schema_version_is_rejected(self):
        self.payload.pop("schema_version")

        with self.assertRaisesRegex(
            SnapshotValidationError,
            "schema_version",
        ):
            TaskSnapshotSerializer.from_dict(self.payload)

    def test_missing_required_state_field_is_rejected(self):
        self.payload["state"].pop("requirement")

        with self.assertRaisesRegex(
            SnapshotValidationError,
            "requirement",
        ):
            TaskSnapshotSerializer.from_dict(self.payload)

    def test_invalid_enum_is_rejected(self):
        self.payload["state"]["status"] = "unknown"

        with self.assertRaisesRegex(
            SnapshotValidationError,
            "invalid enum",
        ):
            TaskSnapshotSerializer.from_dict(self.payload)

    def test_invalid_or_naive_datetime_is_rejected(self):
        for value in ("not-a-time", "2026-07-30T08:00:00"):
            with self.subTest(value=value):
                payload = deepcopy(self.payload)
                payload["state"]["created_at"] = value
                with self.assertRaises(SnapshotValidationError):
                    TaskSnapshotSerializer.from_dict(payload)

    def test_unsupported_schema_version_is_rejected(self):
        self.payload["schema_version"] = 99

        with self.assertRaises(UnsupportedSnapshotVersionError):
            TaskSnapshotSerializer.from_dict(self.payload)

    def test_unknown_fields_are_rejected_at_each_contract_layer(self):
        targets = [
            self.payload,
            self.payload["state"],
            self.payload["application"],
            self.payload["state"]["events"][0],
        ]
        for index, target in enumerate(targets):
            with self.subTest(index=index):
                payload = deepcopy(self.payload)
                if index == 0:
                    selected = payload
                elif index == 1:
                    selected = payload["state"]
                elif index == 2:
                    selected = payload["application"]
                else:
                    selected = payload["state"]["events"][0]
                selected["future_field"] = "unsupported"
                with self.assertRaisesRegex(
                    SnapshotValidationError,
                    "unknown fields",
                ):
                    TaskSnapshotSerializer.from_dict(payload)

    def test_runtime_service_object_is_rejected(self):
        self.record.state.events[0].data["client"] = object()

        with self.assertRaisesRegex(
            SnapshotValidationError,
            "unsupported runtime value",
        ):
            TaskSnapshotSerializer.to_dict(self.record)

    def test_uncontracted_runtime_field_is_rejected(self):
        self.record.state.runtime_client = object()

        with self.assertRaisesRegex(
            SnapshotValidationError,
            "unknown fields",
        ):
            TaskSnapshotSerializer.to_dict(self.record)

    def test_round_trip_does_not_share_mutable_references(self):
        restored = TaskSnapshotSerializer.from_dict(self.payload)
        restored.state.test_points[0]["steps"].append("新步骤")
        restored.state.events[0].data["overall_score"] = 100
        self.record.state.business_rules.append("新规则")

        self.assertEqual(
            self.record.state.test_points[0]["steps"],
            ["提交购买数量为1的订单"],
        )
        self.assertEqual(
            self.payload["state"]["events"][0]["data"]["overall_score"],
            78,
        )
        self.assertNotIn(
            "新规则",
            restored.state.business_rules,
        )

    def test_task_id_mismatch_cannot_be_introduced(self):
        self.assertNotIn("task_id", self.payload["state"])
        restored = TaskSnapshotSerializer.from_dict(self.payload)
        self.assertEqual(restored.state.task_id, self.payload["task_id"])

    def test_in_progress_is_process_local_and_resets_on_restore(self):
        self.assertNotIn("in_progress", self.payload["application"])
        restored = TaskSnapshotSerializer.from_dict(self.payload)
        self.assertFalse(restored.in_progress)

    def test_same_version_migration_returns_isolated_copy(self):
        migrated = migrate_snapshot(
            self.payload,
            SNAPSHOT_SCHEMA_VERSION,
            SNAPSHOT_SCHEMA_VERSION,
        )
        migrated["state"]["modules"].append("支付")

        self.assertNotIn("支付", self.payload["state"]["modules"])

    def test_unknown_migration_path_is_rejected(self):
        with self.assertRaises(UnsupportedSnapshotVersionError):
            migrate_snapshot(self.payload, 1, 2)

    def test_invalid_json_is_rejected_with_snapshot_error(self):
        with self.assertRaisesRegex(
            SnapshotValidationError,
            "JSON is invalid",
        ):
            TaskSnapshotSerializer.from_json("{")

    def test_non_object_json_is_rejected(self):
        with self.assertRaisesRegex(
            SnapshotValidationError,
            "snapshot must be an object",
        ):
            TaskSnapshotSerializer.from_json("[]")

    def test_missing_task_id_is_rejected(self):
        self.payload.pop("task_id")

        with self.assertRaisesRegex(
            SnapshotValidationError,
            "task_id",
        ):
            TaskSnapshotSerializer.from_dict(self.payload)

    def test_invalid_next_action_is_rejected(self):
        self.payload["application"]["next_action"] = "unknown_action"

        with self.assertRaisesRegex(
            SnapshotValidationError,
            "application.next_action",
        ):
            TaskSnapshotSerializer.from_dict(self.payload)

    def test_unknown_agent_event_type_is_rejected(self):
        self.payload["state"]["events"][0]["event_type"] = "unknown"

        with self.assertRaisesRegex(
            SnapshotValidationError,
            r"state\.events\[0\]\.event_type",
        ):
            TaskSnapshotSerializer.from_dict(self.payload)

    def test_list_field_with_wrong_type_is_rejected(self):
        self.payload["state"]["modules"] = "订单"

        with self.assertRaisesRegex(
            SnapshotValidationError,
            "state.modules must be a list",
        ):
            TaskSnapshotSerializer.from_dict(self.payload)

    def test_invalid_nested_test_point_field_is_rejected(self):
        self.payload["state"]["test_points"][0]["steps"] = "提交订单"

        with self.assertRaisesRegex(
            SnapshotValidationError,
            "state.test_points is invalid",
        ):
            TaskSnapshotSerializer.from_dict(self.payload)


if __name__ == "__main__":
    unittest.main()
