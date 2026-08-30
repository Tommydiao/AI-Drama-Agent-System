from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def write_evidence_manifest(root: Path, project_id: str, media_path: Path, *, mock_cost_minor: int = 0) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(media_path.read_bytes()).hexdigest()
    manifest = {
        "project_id": project_id,
        "assets": [{"path": str(media_path), "sha256": digest, "is_mock": True}],
        "cost_report": {"currency": "USD", "total_minor": mock_cost_minor, "is_mock": True},
        "checks": ["ffprobe", "mock-qc", "immutable-hash"],
    }
    path = root / f"{project_id}-manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

