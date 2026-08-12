import json
from io import BytesIO
from pathlib import Path

from documents import DocumentImageElement, DocumentTableElement
from services.document_service import DocumentService


FIXTURE_DIR = Path(__file__).parents[3] / "evaluation" / "fixtures"
MANIFEST_PATH = FIXTURE_DIR / "realistic_prd_v1.json"


class UploadedFixture(BytesIO):
    def __init__(self, path: Path):
        super().__init__(path.read_bytes())
        self.name = path.name


def test_realistic_prd_manifest_and_assets_are_valid():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert len(manifest["fixtures"]) == 2
    assert {item["domain"] for item in manifest["fixtures"]} == {
        "iot_security",
        "ecommerce",
    }
    for fixture in manifest["fixtures"]:
        assert (FIXTURE_DIR / fixture["path"]).stat().st_size > 0


def test_realistic_prds_pass_through_real_document_parser():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    for fixture in manifest["fixtures"]:
        content = DocumentService.parse(
            UploadedFixture(FIXTURE_DIR / fixture["path"])
        )
        normalized_text = "".join(content.to_plain_text().split())
        for line in fixture["expected"]["text_lines"]:
            assert "".join(line.split()) in normalized_text
        assert sum(
            isinstance(item, DocumentTableElement) for item in content.elements
        ) == fixture["expected"]["table_count"]
        assert sum(
            isinstance(item, DocumentImageElement) for item in content.elements
        ) == fixture["expected"]["image_count"]
