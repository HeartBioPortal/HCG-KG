from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hcg_kg.config.models import ProjectSettings

DEFAULT_PROFILE = "hpc-large"


def _find_project_root(start: Path) -> Path | None:
    candidate = start.resolve()
    search_roots = [candidate, *candidate.parents]
    for root in search_roots:
        if (root / "configs" / "profiles" / "base.yaml").exists():
            return root
    return None


def _resolve_project_root(project_root: Path | None) -> Path:
    env_root = os.getenv("HCG_KG_PROJECT_ROOT")
    if env_root:
        discovered = _find_project_root(Path(env_root))
        if discovered is not None:
            return discovered
        return Path(env_root).resolve()

    if project_root is not None:
        discovered = _find_project_root(project_root)
        if discovered is not None:
            return discovered

    cwd_root = _find_project_root(Path.cwd())
    if cwd_root is not None:
        return cwd_root

    package_root = _find_project_root(Path(__file__).resolve())
    if package_root is not None:
        return package_root

    if project_root is not None:
        return project_root.resolve()
    return Path.cwd().resolve()


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    overrides: dict[str, tuple[str, ...]] = {
        "HCG_KG_INPUT_GLOB": ("paths", "raw_input_glob"),
        "HCG_KG_SOURCE_PDF_DIR": ("paths", "source_pdf_dir"),
        "HCG_KG_LOG_LEVEL": ("runtime", "log_level"),
        "NEO4J_URI": ("graph", "neo4j_uri"),
        "NEO4J_USERNAME": ("graph", "neo4j_username"),
    }
    merged = dict(data)
    for env_name, path in overrides.items():
        value = os.getenv(env_name)
        if value is None:
            continue
        cursor: dict[str, Any] = merged
        for key in path[:-1]:
            next_cursor = cursor.get(key)
            if not isinstance(next_cursor, dict):
                next_cursor = {}
                cursor[key] = next_cursor
            cursor = next_cursor
        cursor[path[-1]] = value
    return merged


def load_settings(
    profile: str | None = None,
    project_root: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> ProjectSettings:
    root = _resolve_project_root(project_root)
    profile_name = profile or os.getenv("HCG_KG_PROFILE", DEFAULT_PROFILE)
    profiles_dir = root / "configs" / "profiles"
    base_data = _load_yaml(profiles_dir / "base.yaml")
    if profile_name == "base":
        merged = base_data
    else:
        profile_path = profiles_dir / f"{profile_name}.yaml"
        if not profile_path.exists():
            raise FileNotFoundError(f"Unknown profile: {profile_name}")
        merged = _deep_merge(base_data, _load_yaml(profile_path))

    merged = _apply_env_overrides(merged)
    if overrides is not None:
        merged = _deep_merge(merged, overrides)
    merged["project_root"] = root
    return ProjectSettings.model_validate(merged)
