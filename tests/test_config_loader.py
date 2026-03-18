from __future__ import annotations

from hcg_kg.config.loader import load_settings


def test_load_settings_discovers_repo_root_from_nested_directory(project_root):
    nested_path = project_root / "data" / "source_pdfs"
    settings = load_settings(profile="local-dev", project_root=nested_path)

    assert settings.project_root == project_root
