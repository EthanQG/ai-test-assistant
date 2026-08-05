import ast
from pathlib import Path


def _imports(path: str) -> set[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_knowledge_asset_domain_does_not_import_infrastructure():
    imports = _imports("knowledge_assets/policy.py") | _imports(
        "knowledge_assets/models.py"
    ) | _imports("knowledge_assets/indexing.py")
    imports |= _imports("knowledge_assets/retrieval.py")

    assert not any(
        module.startswith(
            ("repositories", "application", "services", "utils", "views")
        )
        for module in imports
    )


def test_knowledge_asset_application_service_uses_abstract_boundaries():
    source = Path("application/knowledge_asset_service.py").read_text(
        encoding="utf-8"
    )
    imports = _imports("application/knowledge_asset_service.py")

    assert "repositories" in imports
    assert "MySQL" not in source
    assert "Milvus" not in source
    assert "Embedding" not in source
    assert "LLM" not in source


def test_indexing_application_service_uses_ports_not_concrete_adapters():
    source = Path(
        "application/knowledge_asset_indexing_service.py"
    ).read_text(encoding="utf-8")

    assert "Ollama" not in source
    assert "MilvusClient" not in source
    assert "requests" not in source
    assert "pymilvus" not in source


def test_retrieval_application_service_uses_ports_without_llm_reranking():
    source = Path(
        "application/knowledge_asset_retrieval_service.py"
    ).read_text(encoding="utf-8")

    assert "Ollama" not in source
    assert "MilvusClient" not in source
    assert "requests" not in source
    assert "pymilvus" not in source
    assert "LLM" not in source
