from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from hcg_kg.config.loader import load_settings


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def sample_json_path(project_root: Path) -> Path:
    return project_root / "data" / "sample" / "aha_sample_guideline.json"


@pytest.fixture
def local_settings(tmp_path: Path, project_root: Path, sample_json_path: Path):
    return load_settings(
        profile="local-dev",
        project_root=project_root,
        overrides={
            "paths": {
                "raw_input_glob": str(sample_json_path),
                "processed_dir": str(tmp_path / "processed"),
                "normalized_dir": str(tmp_path / "processed" / "normalized"),
                "graph_dir": str(tmp_path / "processed" / "graph"),
                "vector_dir": str(tmp_path / "processed" / "vector"),
                "state_dir": str(tmp_path / "processed" / "state"),
            },
            "graph": {"backend": "networkx"},
        },
    )
