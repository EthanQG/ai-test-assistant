import time

from fastapi.testclient import TestClient

from agent import (
    AgentStep,
    KnowledgeRetrievalStatus,
    OrchestratorAction,
    OrchestratorDecision,
    HumanFeedbackHandler,
)
from application.background_runner import TaskBackgroundRunner
from application.service import TestAnalysisApplicationService
from api.main import create_app
from repositories import InMemoryTaskRepository


class ScriptedOrchestrator:
    def __init__(self):
        self._steps = [
            (OrchestratorAction.ANALYZE_REQUIREMENT, self._analyze),
            (OrchestratorAction.RETRIEVE_KNOWLEDGE, self._retrieve),
            (OrchestratorAction.GENERATE_TEST_POINTS, self._generate),
            (OrchestratorAction.REVIEW_TEST_POINTS, self._review),
            (OrchestratorAction.FINALIZE, self._finalize),
        ]

    def decide_next(self, _state):
        action = self._steps[0][0] if self._steps else OrchestratorAction.TERMINAL
        return OrchestratorDecision(action, "脚本化接口验收")

    def run_next(self, state):
        action, callback = self._steps.pop(0)
        callback(state)
        return OrchestratorDecision(action, "脚本化接口验收")

    def resume_with_clarifications(self, state, answers):
        state.resume()
        state.user_clarifications.extend(
            {"question": question, "answer": answer or "暂不确定"}
            for question, answer in answers.items()
        )
        state.open_questions = []
        return OrchestratorDecision(
            OrchestratorAction.ANALYZE_REQUIREMENT,
            "补充信息后重新分析",
        )

    def queue_feedback_cycle(self):
        self._steps.extend([
            (OrchestratorAction.REVISE_TEST_POINTS, self._revise_feedback),
            (OrchestratorAction.REVIEW_TEST_POINTS, self._review),
            (OrchestratorAction.FINALIZE, self._finalize),
        ])

    @staticmethod
    def _analyze(state):
        state.start_step(AgentStep.ANALYZE_REQUIREMENT, "开始分析需求")
        state.requirement_summary = "订单库存需求"
        state.complete_step(AgentStep.ANALYZE_REQUIREMENT, "需求分析完成")
        state.wait_for_user(["库存不足时如何处理？"])

    @staticmethod
    def _retrieve(state):
        state.start_step(AgentStep.RETRIEVE_KNOWLEDGE, "开始检索知识")
        state.knowledge_retrieval_status = KnowledgeRetrievalStatus.NO_MATCH
        state.complete_step(AgentStep.RETRIEVE_KNOWLEDGE, "知识检索完成")

    @staticmethod
    def _generate(state):
        state.start_step(AgentStep.GENERATE_TEST_POINTS, "开始生成测试点")
        state.test_points = [{"id": "TP-1", "title": "库存不足时拒绝下单"}]
        state.complete_step(AgentStep.GENERATE_TEST_POINTS, "测试点生成完成")

    @staticmethod
    def _review(state):
        state.start_step(AgentStep.REVIEW_TEST_POINTS, "开始质量评审")
        state.review_result = {"score": 90}
        state.review_passed = True
        state.complete_step(AgentStep.REVIEW_TEST_POINTS, "质量评审完成")

    @staticmethod
    def _revise_feedback(state):
        state.start_step(AgentStep.REVISE_TEST_POINTS, "开始处理人工反馈")
        applied = HumanFeedbackHandler.mark_ready_as_applied(state)
        state.human_revision_count += 1
        state.review_result = None
        state.review_passed = None
        state.complete_step(
            AgentStep.REVISE_TEST_POINTS,
            "人工反馈修正完成",
            {"applied_feedback_count": applied},
        )

    @staticmethod
    def _finalize(state):
        state.start_step(AgentStep.FINALIZE, "开始整理报告")
        state.final_result = {"test_point_count": 1}
        state.complete("# 测试分析报告\n\n库存不足时拒绝下单。")


def _wait_for_status(client, task_id, expected):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/tasks/{task_id}/progress")
        if response.json()["status"] == expected:
            return response.json()
        time.sleep(0.01)
    raise AssertionError(f"task did not reach {expected}")


def test_fastapi_v1_file_background_pause_resume_and_result_flow():
    orchestrator = ScriptedOrchestrator()
    service = TestAnalysisApplicationService(
        InMemoryTaskRepository(),
        orchestrator_factory=lambda: orchestrator,
        knowledge_loader=lambda: "",
    )
    runner = TaskBackgroundRunner(service, max_workers=1)
    client = TestClient(create_app(service, runner))
    try:
        created = client.post(
            "/api/v1/tasks/from-document",
            files={
                "file": (
                    "订单需求.md",
                    "# 订单需求\n\n提交订单前校验库存。".encode(),
                    "text/markdown",
                )
            },
        )
        task_id = created.json()["state"]["task_id"]

        assert client.post(f"/api/v1/tasks/{task_id}/run").status_code == 202
        waiting = _wait_for_status(client, task_id, "waiting_for_user")
        assert waiting["waiting_for_clarifications"] is False

        submitted = client.post(
            f"/api/v1/tasks/{task_id}/clarifications",
            json={"answers": {"库存不足时如何处理？": "拒绝创建订单"}},
        )
        assert submitted.json()["state"]["task_id"] == task_id
        assert client.post(f"/api/v1/tasks/{task_id}/run").status_code == 202

        completed = _wait_for_status(client, task_id, "completed")
        detail = client.get(f"/api/v1/tasks/{task_id}").json()

        assert completed["test_point_count"] == 1
        assert completed["reviewer_score"] == 90
        assert detail["state"]["report"].startswith("# 测试分析报告")
        assert detail["state"]["user_clarifications"][0]["answer"] == "拒绝创建订单"

        orchestrator.queue_feedback_cycle()
        suggestion = client.post(
            f"/api/v1/tasks/{task_id}/feedback",
            json={
                "action": "add",
                "feedback_type": "test_suggestion",
                "target": "新增测试点",
                "content": "补充并发扣减库存场景",
                "reason": "覆盖幂等与超卖风险",
            },
        )
        assert suggestion.json()["state"]["task_id"] == task_id
        assert suggestion.json()["state"]["human_feedback"][-1]["status"] == "ready"
        assert client.post(f"/api/v1/tasks/{task_id}/run").status_code == 202
        _wait_for_status(client, task_id, "completed")
        after_suggestion = client.get(f"/api/v1/tasks/{task_id}").json()
        assert after_suggestion["state"]["human_revision_count"] == 1
        assert after_suggestion["state"]["human_feedback"][-1]["status"] == "applied"

        business = client.post(
            f"/api/v1/tasks/{task_id}/feedback",
            json={
                "action": "add",
                "feedback_type": "business_rule",
                "target": "新增业务规则",
                "content": "库存扣减失败时不得创建订单",
                "reason": "产品补充规则",
            },
        )
        pending = business.json()["state"]["human_feedback"][-1]
        assert business.json()["state"]["status"] == "waiting_for_user"
        assert pending["status"] == "pending_confirmation"

        orchestrator.queue_feedback_cycle()
        confirmed = client.post(
            f"/api/v1/tasks/{task_id}/business-rules/confirmation",
            json={"feedback_id": pending["feedback_id"], "confirmed": True},
        )
        assert confirmed.json()["state"]["task_id"] == task_id
        assert "库存扣减失败时不得创建订单" in confirmed.json()["state"]["business_rules"]
        assert client.post(f"/api/v1/tasks/{task_id}/run").status_code == 202
        _wait_for_status(client, task_id, "completed")
        after_rule = client.get(f"/api/v1/tasks/{task_id}").json()
        assert after_rule["state"]["human_revision_count"] == 2
        assert after_rule["state"]["human_feedback"][-1]["status"] == "applied"

        cancelled = client.post(
            f"/api/v1/tasks/{task_id}/feedback",
            json={
                "action": "add",
                "feedback_type": "business_rule",
                "target": "新增业务规则",
                "content": "无依据的临时规则",
                "reason": "用于验证取消流程",
            },
        ).json()["state"]["human_feedback"][-1]
        rejected = client.post(
            f"/api/v1/tasks/{task_id}/business-rules/confirmation",
            json={"feedback_id": cancelled["feedback_id"], "confirmed": False},
        ).json()
        assert rejected["state"]["human_feedback"][-1]["status"] == "rejected"
        assert "无依据的临时规则" not in rejected["state"]["business_rules"]
    finally:
        runner.shutdown()
