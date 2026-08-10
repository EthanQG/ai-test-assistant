import json
from pathlib import Path

from documents import (
    DocumentUiElement,
    DocumentVisualAnalysis,
    DocumentVisualKind,
    DocumentVisualNode,
    DocumentVisualRelation,
)
from evaluation.document_parsing import (
    run_document_parsing_evaluation,
    score_visual_analysis,
)


MANIFEST_PATH = (
    Path(__file__).parents[3] / "evaluation" / "fixtures" / "gold_v1.json"
)


def _fixture(target: str) -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return next(
        item
        for item in manifest["fixtures"]
        if item["evaluation_target"] == target
    )


def _flow_analysis(*, include_failure_branch: bool = True) -> DocumentVisualAnalysis:
    nodes = (
        DocumentVisualNode("submit", "提交订单", "action"),
        DocumentVisualNode("check", "校验库存", "decision"),
        DocumentVisualNode("create", "创建订单", "action"),
        DocumentVisualNode("reject", "提示库存不足", "action"),
    )
    relations = [
        DocumentVisualRelation("submit", "check"),
        DocumentVisualRelation("check", "create", condition="库存充足"),
    ]
    if include_failure_branch:
        relations.append(
            DocumentVisualRelation("check", "reject", condition="库存不足")
        )
    return DocumentVisualAnalysis(
        image_id="flow-image",
        kind=DocumentVisualKind.FLOWCHART,
        summary="订单库存校验流程",
        confidence=0.95,
        nodes=nodes,
        relations=tuple(relations),
    )


def _ui_analysis(*, include_extra: bool = False) -> DocumentVisualAnalysis:
    elements = [
        DocumentUiElement("拖拽文件到此处", "upload_area"),
        DocumentUiElement("选择文件", "button"),
        DocumentUiElement("上传成功", "status"),
        DocumentUiElement("格式不支持", "status"),
    ]
    if include_extra:
        elements.append(DocumentUiElement("删除文件", "button"))
    return DocumentVisualAnalysis(
        image_id="ui-image",
        kind=DocumentVisualKind.UI_MOCKUP,
        summary="发票上传页面",
        confidence=0.95,
        ui_elements=tuple(elements),
    )


def test_flow_score_matches_nodes_relations_and_conditions():
    score = score_visual_analysis(
        _fixture("flow_semantics"),
        _flow_analysis(),
    )

    assert score.metrics == {
        "flow_node_recall": 1.0,
        "flow_relation_accuracy": 1.0,
    }
    assert score.missing_items == ()


def test_flow_score_reports_missing_branch_relation():
    score = score_visual_analysis(
        _fixture("flow_semantics"),
        _flow_analysis(include_failure_branch=False),
    )

    assert score.metrics["flow_node_recall"] == 1.0
    assert score.metrics["flow_relation_accuracy"] == 0.6667
    assert score.missing_items == (
        "关系：校验库存->提示库存不足（库存不足）",
    )


def test_ui_score_penalizes_unexpected_elements():
    score = score_visual_analysis(
        _fixture("ui_semantics"),
        _ui_analysis(include_extra=True),
    )

    assert score.metrics == {"ui_element_accuracy": 0.8}
    assert score.missing_items == ()


def test_runner_accepts_injected_visual_results_without_calling_parser(tmp_path):
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source["fixtures"] = [
        item
        for item in source["fixtures"]
        if item["evaluation_target"] in {"flow_semantics", "ui_semantics"}
    ]
    manifest_path = tmp_path / "gold.json"
    manifest_path.write_text(
        json.dumps(source, ensure_ascii=False),
        encoding="utf-8",
    )

    report = run_document_parsing_evaluation(
        manifest_path,
        parser=lambda uploaded: (_ for _ in ()).throw(
            AssertionError("text parser must not run")
        ),
        visual_results={
            "flow-image-001": _flow_analysis(),
            "ui-image-001": _ui_analysis(),
        },
    )

    assert report["evaluated_fixture_count"] == 2
    assert report["skipped_fixture_ids"] == []
    assert [item["evaluation_target"] for item in report["results"]] == [
        "flow_semantics",
        "ui_semantics",
    ]
