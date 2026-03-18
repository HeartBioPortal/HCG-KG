from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from hcg_kg.cli import app


def test_validate_command_runs(sample_json_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "validate",
            "--profile",
            "local-dev",
            "--input-glob",
            str(sample_json_path),
            "--limit",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "\"valid\": true" in result.stdout.lower()
