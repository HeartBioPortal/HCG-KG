from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import typer

from hcg_kg.config import load_settings
from hcg_kg.logging_utils import configure_logging
from hcg_kg.pipelines.runner import PipelineRunner
from hcg_kg.query.service import QueryService
from hcg_kg.utils import dump_json, load_json, to_pretty_json

try:
    from rich.console import Console
except ImportError:  # pragma: no cover - optional runtime nicety
    Console = None  # type: ignore[assignment]

app = typer.Typer(help="Build and query a source-grounded biomedical knowledge graph from guideline JSON.")
console = Console() if Console is not None else None


def _settings(profile: str | None, log_file: Path | None) -> Any:
    settings = load_settings(profile=profile, project_root=Path.cwd())
    configure_logging(settings.runtime.log_level, log_file)
    return settings


def _render(data: object, pretty: bool) -> None:
    if pretty and console is not None:
        console.print_json(to_pretty_json(data))
    else:
        typer.echo(to_pretty_json(data))


@app.command()
def ingest(
    profile: Optional[str] = typer.Option(None, help="Configuration profile."),
    input_glob: Optional[str] = typer.Option(None, help="Input JSON glob override."),
    limit: Optional[int] = typer.Option(None, help="Limit discovered files."),
    force: bool = typer.Option(False, help="Rebuild manifest entries."),
    log_file: Optional[Path] = typer.Option(None, help="Optional application log path."),
) -> None:
    settings = _settings(profile, log_file)
    runner = PipelineRunner(settings)
    entries = runner.ingest(input_glob=input_glob, limit=limit, force=force)
    _render({"documents": [entry.model_dump(mode="json") for entry in entries]}, pretty=True)


@app.command()
def normalize(
    profile: Optional[str] = typer.Option(None, help="Configuration profile."),
    input_glob: Optional[str] = typer.Option(None, help="Input JSON glob override."),
    limit: Optional[int] = typer.Option(None, help="Limit input files."),
    force: bool = typer.Option(False, help="Recompute normalized outputs."),
    log_file: Optional[Path] = typer.Option(None, help="Optional application log path."),
) -> None:
    settings = _settings(profile, log_file)
    runner = PipelineRunner(settings)
    documents = runner.normalize(input_glob=input_glob, limit=limit, force=force)
    _render(
        {
            "documents": [
                {
                    "doc_id": document.metadata.guideline_id,
                    "title": document.metadata.title,
                    "snippets": len(document.snippets),
                    "gene_mentions": len(document.gene_mentions),
                }
                for document in documents
            ]
        },
        pretty=True,
    )


@app.command("build-graph")
def build_graph(
    profile: Optional[str] = typer.Option(None, help="Configuration profile."),
    force: bool = typer.Option(False, help="Force loading normalized documents again."),
    log_file: Optional[Path] = typer.Option(None, help="Optional application log path."),
) -> None:
    settings = _settings(profile, log_file)
    runner = PipelineRunner(settings)
    report = runner.build_graph(force=force)
    _render(report.__dict__, pretty=True)


@app.command("build-embeddings")
def build_embeddings(
    profile: Optional[str] = typer.Option(None, help="Configuration profile."),
    force: bool = typer.Option(False, help="Force rebuilding the snippet index."),
    log_file: Optional[Path] = typer.Option(None, help="Optional application log path."),
) -> None:
    settings = _settings(profile, log_file)
    runner = PipelineRunner(settings)
    path = runner.build_embeddings(force=force)
    _render({"tfidf_index": path}, pretty=True)


@app.command()
def query(
    gene: Optional[str] = typer.Option(None, help="Gene symbol to query."),
    question: Optional[str] = typer.Option(None, help="Optional natural-language question."),
    profile: Optional[str] = typer.Option(None, help="Configuration profile."),
    pretty: bool = typer.Option(False, help="Pretty-print JSON output."),
    log_file: Optional[Path] = typer.Option(None, help="Optional application log path."),
) -> None:
    if gene is None and question is None:
        raise typer.BadParameter("Provide --gene or --question.")
    settings = _settings(profile, log_file)
    service = QueryService(settings)
    try:
        resolved_gene = gene or question or ""
        response = service.query_gene(resolved_gene, question=question)
        _render(response.model_dump(mode="json"), pretty=pretty)
    finally:
        service.close()


@app.command("inspect-document")
def inspect_document(
    path: Path = typer.Option(..., exists=True, help="Raw or normalized document path."),
    profile: Optional[str] = typer.Option(None, help="Configuration profile."),
    pretty: bool = typer.Option(True, help="Pretty-print JSON output."),
    log_file: Optional[Path] = typer.Option(None, help="Optional application log path."),
) -> None:
    settings = _settings(profile, log_file)
    runner = PipelineRunner(settings)
    payload = load_json(path)
    if "metadata" in payload and "snippets" in payload:
        _render(payload, pretty=pretty)
        return
    document = runner.normalizer.normalize(
        payload,
        source_json_path=path,
        source_pdf_path=runner.loader.resolve_pdf_path(path),
        doc_id=runner.loader.derive_doc_id(path),
    )
    _render(document.model_dump(mode="json"), pretty=pretty)


@app.command("inspect-gene")
def inspect_gene(
    gene: str = typer.Option(..., help="Gene symbol to inspect."),
    profile: Optional[str] = typer.Option(None, help="Configuration profile."),
    pretty: bool = typer.Option(True, help="Pretty-print JSON output."),
    log_file: Optional[Path] = typer.Option(None, help="Optional application log path."),
) -> None:
    settings = _settings(profile, log_file)
    service = QueryService(settings)
    try:
        response = service.query_gene(gene)
        _render(response.model_dump(mode="json"), pretty=pretty)
    finally:
        service.close()


@app.command("export-subgraph")
def export_subgraph(
    gene: str = typer.Option(..., help="Gene symbol to export."),
    output: Path = typer.Option(..., help="Output JSON path."),
    profile: Optional[str] = typer.Option(None, help="Configuration profile."),
    log_file: Optional[Path] = typer.Option(None, help="Optional application log path."),
) -> None:
    settings = _settings(profile, log_file)
    service = QueryService(settings)
    try:
        subgraph = service.export_subgraph(gene)
        dump_json(subgraph, output)
        _render({"output": str(output)}, pretty=True)
    finally:
        service.close()


@app.command()
def validate(
    profile: Optional[str] = typer.Option(None, help="Configuration profile."),
    input_glob: Optional[str] = typer.Option(None, help="Input JSON glob override."),
    limit: int = typer.Option(2, help="Number of files to sample."),
    log_file: Optional[Path] = typer.Option(None, help="Optional application log path."),
) -> None:
    settings = _settings(profile, log_file)
    runner = PipelineRunner(settings)
    result = runner.validate(input_glob=input_glob, limit=limit)
    _render(result, pretty=True)


@app.command("run-pipeline")
def run_pipeline(
    profile: Optional[str] = typer.Option(None, help="Configuration profile."),
    input_glob: Optional[str] = typer.Option(None, help="Input JSON glob override."),
    limit: Optional[int] = typer.Option(None, help="Optional file limit."),
    force: bool = typer.Option(False, help="Force reprocessing."),
    log_file: Optional[Path] = typer.Option(None, help="Optional application log path."),
) -> None:
    settings = _settings(profile, log_file)
    runner = PipelineRunner(settings)
    result = runner.run_pipeline(input_glob=input_glob, limit=limit, force=force)
    _render(result, pretty=True)


@app.command()
def resume(
    profile: Optional[str] = typer.Option(None, help="Configuration profile."),
    input_glob: Optional[str] = typer.Option(None, help="Input JSON glob override."),
    limit: Optional[int] = typer.Option(None, help="Optional file limit."),
    log_file: Optional[Path] = typer.Option(None, help="Optional application log path."),
) -> None:
    settings = _settings(profile, log_file)
    runner = PipelineRunner(settings)
    result = runner.resume(input_glob=input_glob, limit=limit)
    _render(result, pretty=True)


if __name__ == "__main__":
    app()
