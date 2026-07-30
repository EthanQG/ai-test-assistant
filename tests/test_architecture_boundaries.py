import ast
import unittest
from pathlib import Path


class StreamlitArchitectureBoundaryTests(unittest.TestCase):
    def test_page_does_not_reference_agent_execution_components(self):
        source_path = Path("views/tab_test_points.py")
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_names = {
            "AgentOrchestrator",
            "RequirementAnalyzer",
            "KnowledgeRetriever",
            "TestPointGenerator",
            "TestPointReviewer",
            "TestPointReviser",
            "Finalizer",
            "HumanFeedbackHandler",
            "TestAnalysisState",
        }
        referenced_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }

        self.assertFalse(
            forbidden_names & referenced_names,
            forbidden_names & referenced_names,
        )
        self.assertNotIn("_task_store", source)
        self.assertNotIn("_execute_next_orchestrator_node", source)

    def test_page_only_imports_agent_display_enums(self):
        tree = ast.parse(
            Path("views/tab_test_points.py").read_text(encoding="utf-8")
        )
        imported_from_agent = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "agent"
            for alias in node.names
        }

        self.assertEqual(
            imported_from_agent,
            {
                "AgentStatus",
                "OrchestratorAction",
                "OrchestratorDecision",
            },
        )

    def test_page_does_not_import_repository_or_external_services(self):
        tree = ast.parse(
            Path("views/tab_test_points.py").read_text(encoding="utf-8")
        )
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        forbidden_roots = {
            "repositories",
            "services",
            "utils",
        }
        violations = {
            module
            for module in imported_modules
            if module.split(".", 1)[0] in forbidden_roots
        }

        self.assertFalse(violations, violations)

    def test_application_service_does_not_reference_requirement_analyzer(self):
        source = Path("application/service.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_from_agent = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "agent"
            for alias in node.names
        }
        referenced_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }

        self.assertNotIn("RequirementAnalyzer", imported_from_agent)
        self.assertNotIn("RequirementAnalyzer", referenced_names)
        self.assertNotIn("requirement_analyzer_factory", source)


if __name__ == "__main__":
    unittest.main()
