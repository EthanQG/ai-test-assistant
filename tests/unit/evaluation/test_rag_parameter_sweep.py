from pathlib import Path
from types import SimpleNamespace

from evaluation.rag import run_rag_parameter_sweep
from evaluation.rag_sweep import _CachedEmbeddingService


DATASET_PATH = Path("evaluation/fixtures/rag_v1.json")
RELEVANT_IDS = (
    "asset-order-inventory",
    "asset-refund-cumulative",
    "asset-login-lock",
    "asset-file-upload",
    "asset-role-permission",
)


class _Retriever:
    def __init__(self, asset_id):
        self.asset_id = asset_id

    def retrieve(self, query_text):
        del query_text
        candidate = SimpleNamespace(asset=SimpleNamespace(asset_id=self.asset_id))
        return SimpleNamespace(candidates=(candidate,))


def test_parameter_sweep_runs_every_top_k_and_threshold_combination():
    calls = []

    def factory(top_k, min_score):
        asset_id = RELEVANT_IDS[len(calls) % len(RELEVANT_IDS)]
        calls.append((top_k, min_score))
        return _Retriever(asset_id)

    report = run_rag_parameter_sweep(
        DATASET_PATH,
        factory,
        top_k_values=(1, 3),
        min_score_values=(0.65, 0.75),
    )

    assert calls == [(1, 0.65), (3, 0.65), (1, 0.75), (3, 0.75)]
    assert report["combination_count"] == 4
    assert [(item["top_k"], item["min_score"]) for item in report["combinations"]] == calls


def test_parameter_sweep_reuses_the_same_query_embedding():
    class Delegate:
        def __init__(self):
            self.calls = []

        def embed_batch(self, texts):
            self.calls.append(list(texts))
            return [[0.1, 0.2]]

    delegate = Delegate()
    cached = _CachedEmbeddingService(delegate)

    assert cached.embed_batch(["same query"]) == [[0.1, 0.2]]
    assert cached.embed_batch(["same query"]) == [[0.1, 0.2]]
    assert delegate.calls == [["same query"]]
