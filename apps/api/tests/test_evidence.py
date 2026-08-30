import json

from app.evidence import write_evidence_manifest


def test_evidence_manifest_and_mock_cost_ledger_complete(tmp_path):
    media = tmp_path / "rough-cut.mp4"
    media.write_bytes(b"mock-mp4")
    manifest = write_evidence_manifest(tmp_path / "evidence", "project-1", media)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["assets"][0]["sha256"]
    assert payload["cost_report"] == {"currency": "USD", "total_minor": 0, "is_mock": True}

