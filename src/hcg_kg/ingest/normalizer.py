from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hcg_kg.config.models import ProjectSettings
from hcg_kg.models.documents import GeneMention, GuidelineDocument, GuidelineMetadata, Provenance, SourceSnippet
from hcg_kg.utils import make_id, slugify

TITLE_KEYS = {"title", "Title", "guideline_title"}
SECTION_KEYS = {"section", "Section"}
PAGE_KEYS = {"page", "Page"}
REFERENCE_KEYS = {"reference", "references", "References"}
SOURCE_KEYS = {"source", "Source"}
RECOMMENDATION_KEYS = {
    "Recommendation",
    "recommendation",
    "Recommendations",
    "recommendations",
    "Recommendation-Specific Supportive Text",
}
TEXT_SKIP_KEYS = PAGE_KEYS | REFERENCE_KEYS | SOURCE_KEYS


@dataclass
class WalkContext:
    content_index: int
    section_path: list[str]
    page: str | None
    pointer: list[str]
    field_name: str | None = None


class GuidelineJSONNormalizer:
    """Normalize heterogeneous parsed guideline JSON into a stable document model."""

    def __init__(self, settings: ProjectSettings) -> None:
        self.settings = settings

    def normalize(
        self,
        raw: dict[str, Any],
        source_json_path: Path,
        source_pdf_path: Path | None,
        doc_id: str | None = None,
    ) -> GuidelineDocument:
        document_id = doc_id or slugify(source_json_path.stem.removesuffix("_aggregated"))
        metadata = self._extract_metadata(raw, source_json_path, source_pdf_path, document_id)
        snippets: list[SourceSnippet] = []
        gene_mentions: list[GeneMention] = []
        seen_snippets: set[tuple[str, str]] = set()

        top_level_genes = raw.get("genes", [])
        if isinstance(top_level_genes, list):
            gene_mentions.extend(
                self._parse_gene_entries(
                    top_level_genes,
                    metadata,
                    content_index=None,
                )
            )

        for index, item in enumerate(raw.get("content", [])):
            if not isinstance(item, dict):
                continue
            item_content = item.get("content", item)
            item_genes = item.get("genes", [])
            gene_mentions.extend(
                self._parse_gene_entries(
                    item_genes if isinstance(item_genes, list) else [],
                    metadata,
                    content_index=index,
                )
            )
            context = WalkContext(
                content_index=index,
                section_path=[],
                page=self._coerce_page(self._pick_scalar(item_content, PAGE_KEYS)),
                pointer=["content", str(index), "content"],
            )
            self._walk_value(
                value=item_content,
                metadata=metadata,
                context=context,
                snippets=snippets,
                seen=seen_snippets,
            )

        deduped_genes = self._dedupe_gene_mentions(gene_mentions)
        raw_summary = {
            "top_level_keys": sorted(raw.keys()),
            "content_items": len(raw.get("content", [])) if isinstance(raw.get("content", []), list) else 0,
            "raw_gene_mentions": len(deduped_genes),
            "snippet_count": len(snippets),
            "schema_hints": metadata.schema_hints,
        }
        return GuidelineDocument(metadata=metadata, snippets=snippets, gene_mentions=deduped_genes, raw_summary=raw_summary)

    def _extract_metadata(
        self,
        raw: dict[str, Any],
        source_json_path: Path,
        source_pdf_path: Path | None,
        doc_id: str,
    ) -> GuidelineMetadata:
        title = self._find_first_scalar(raw, list(TITLE_KEYS)) or source_json_path.stem.removesuffix("_aggregated")
        organization = self._find_first_scalar(raw, ["organization"])
        publication_date = self._find_first_scalar(raw, ["Date", "publication", "Publication"])
        journal = self._find_first_scalar(raw, ["Journal", "journal"])
        pages = self._find_first_scalar(raw, ["Pages", "pages"])
        schema_hints = sorted(self._collect_schema_hints(raw))
        return GuidelineMetadata(
            guideline_id=doc_id,
            family=self.settings.guideline_family,
            title=title,
            organization=organization,
            publication_date=publication_date,
            journal=journal,
            pages=pages,
            source_json_path=str(source_json_path),
            source_pdf_path=str(source_pdf_path) if source_pdf_path is not None else None,
            schema_hints=schema_hints,
        )

    def _walk_value(
        self,
        value: Any,
        metadata: GuidelineMetadata,
        context: WalkContext,
        snippets: list[SourceSnippet],
        seen: set[tuple[str, str]],
    ) -> None:
        if isinstance(value, dict):
            local_section_path = list(context.section_path)
            section_name = self._pick_scalar(value, SECTION_KEYS)
            title_name = self._pick_scalar(value, TITLE_KEYS)
            if section_name:
                local_section_path = self._extend_section_path(local_section_path, section_name)
            elif title_name and self._is_section_title(title_name):
                local_section_path = self._extend_section_path(local_section_path, title_name)
            local_page = self._coerce_page(self._pick_scalar(value, PAGE_KEYS)) or context.page

            recommendation_text = self._coalesce_recommendation_text(value)
            if recommendation_text:
                self._emit_snippet(
                    text=recommendation_text,
                    snippet_type="recommendation",
                    metadata=metadata,
                    context=WalkContext(
                        content_index=context.content_index,
                        section_path=local_section_path,
                        page=local_page,
                        pointer=context.pointer,
                        field_name="Recommendation",
                    ),
                    snippets=snippets,
                    seen=seen,
                    raw_fields=self._metadata_fields(value),
                )

            for key, child in value.items():
                next_context = WalkContext(
                    content_index=context.content_index,
                    section_path=local_section_path,
                    page=local_page,
                    pointer=[*context.pointer, str(key)],
                    field_name=str(key),
                )
                if isinstance(child, str):
                    if self._should_emit_text(key, child):
                        snippet_type = "recommendation" if key in RECOMMENDATION_KEYS else "text"
                        self._emit_snippet(
                            text=child,
                            snippet_type=snippet_type,
                            metadata=metadata,
                            context=next_context,
                            snippets=snippets,
                            seen=seen,
                            raw_fields=self._metadata_fields(value),
                        )
                elif isinstance(child, list) and child and all(isinstance(item, str) for item in child):
                    joined = "\n".join(item.strip() for item in child if item.strip())
                    if joined and self._should_emit_text(key, joined):
                        self._emit_snippet(
                            text=joined,
                            snippet_type="text",
                            metadata=metadata,
                            context=next_context,
                            snippets=snippets,
                            seen=seen,
                            raw_fields=self._metadata_fields(value),
                        )
                else:
                    self._walk_value(child, metadata, next_context, snippets, seen)
            return

        if isinstance(value, list):
            for index, child in enumerate(value):
                next_context = WalkContext(
                    content_index=context.content_index,
                    section_path=context.section_path,
                    page=context.page,
                    pointer=[*context.pointer, str(index)],
                    field_name=context.field_name,
                )
                self._walk_value(child, metadata, next_context, snippets, seen)

    def _emit_snippet(
        self,
        text: str,
        snippet_type: str,
        metadata: GuidelineMetadata,
        context: WalkContext,
        snippets: list[SourceSnippet],
        seen: set[tuple[str, str]],
        raw_fields: dict[str, Any],
    ) -> None:
        normalized_text = " ".join(text.split())
        if len(normalized_text) < 25:
            return
        dedupe_key = ("|".join(context.section_path), normalized_text)
        if dedupe_key in seen:
            return
        seen.add(dedupe_key)
        snippet_id = make_id(
            "snippet",
            metadata.guideline_id,
            str(context.content_index),
            context.page or "",
            normalized_text[:200],
        )
        provenance = Provenance(
            guideline_id=metadata.guideline_id,
            guideline_title=metadata.title,
            source_json_path=metadata.source_json_path,
            source_pdf_path=metadata.source_pdf_path,
            section_path=context.section_path,
            page=context.page,
            json_pointer="/" + "/".join(context.pointer),
            field_name=context.field_name,
            content_index=context.content_index,
        )
        snippets.append(
            SourceSnippet(
                snippet_id=snippet_id,
                text=normalized_text,
                snippet_type=snippet_type,
                provenance=provenance,
                raw_fields=raw_fields,
            )
        )

    def _parse_gene_entries(
        self,
        entries: list[dict[str, Any]],
        metadata: GuidelineMetadata,
        content_index: int | None,
    ) -> list[GeneMention]:
        mentions: list[GeneMention] = []
        provenance = Provenance(
            guideline_id=metadata.guideline_id,
            guideline_title=metadata.title,
            source_json_path=metadata.source_json_path,
            source_pdf_path=metadata.source_pdf_path,
            content_index=content_index,
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            symbol = entry.get("Gene")
            if not isinstance(symbol, str) or not symbol.strip():
                continue
            associated = entry.get("Associated Conditions", [])
            if isinstance(associated, str):
                associated_conditions = [associated]
            elif isinstance(associated, list):
                associated_conditions = [item for item in associated if isinstance(item, str)]
            else:
                associated_conditions = []
            occurrences = entry.get("Occurrences")
            mentions.append(
                GeneMention(
                    gene_symbol=symbol.strip().upper(),
                    associated_conditions=associated_conditions,
                    occurrences=occurrences if isinstance(occurrences, int) else None,
                    context=entry.get("context") if isinstance(entry.get("context"), str) else None,
                    provenance=provenance,
                )
            )
        return mentions

    def _dedupe_gene_mentions(self, mentions: list[GeneMention]) -> list[GeneMention]:
        deduped: dict[tuple[str, str | None, int | None], GeneMention] = {}
        for mention in mentions:
            provenance_index = mention.provenance.content_index if mention.provenance else None
            key = (mention.gene_symbol, mention.context, provenance_index)
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = mention
                continue
            combined_conditions = sorted(set(existing.associated_conditions) | set(mention.associated_conditions))
            deduped[key] = existing.model_copy(
                update={
                    "associated_conditions": combined_conditions,
                    "occurrences": max(existing.occurrences or 0, mention.occurrences or 0) or None,
                }
            )
        return list(deduped.values())

    def _find_first_scalar(self, value: Any, keys: list[str]) -> str | None:
        if isinstance(value, dict):
            for key in keys:
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
            for child in value.values():
                found = self._find_first_scalar(child, keys)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = self._find_first_scalar(child, keys)
                if found:
                    return found
        return None

    def _collect_schema_hints(self, raw: dict[str, Any]) -> set[str]:
        counter: Counter[str] = Counter()

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                counter.update(value.keys())
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(raw)
        return {key for key, count in counter.items() if count >= 2}

    def _pick_scalar(self, value: Any, keys: set[str]) -> str | None:
        if not isinstance(value, dict):
            return None
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
            if isinstance(candidate, int):
                return str(candidate)
        return None

    def _coerce_page(self, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    def _is_section_title(self, value: str) -> bool:
        return len(value) <= 140

    def _extend_section_path(self, section_path: list[str], section_name: str) -> list[str]:
        cleaned = section_name.strip()
        if not cleaned:
            return section_path
        if section_path and section_path[-1] == cleaned:
            return section_path
        return [*section_path, cleaned]

    def _should_emit_text(self, key: str, text: str) -> bool:
        if key in TEXT_SKIP_KEYS:
            return False
        stripped = text.strip()
        if not stripped:
            return False
        if key in TITLE_KEYS | SECTION_KEYS and len(stripped) < 120:
            return False
        return len(stripped) >= 25

    def _coalesce_recommendation_text(self, value: dict[str, Any]) -> str | None:
        collected: list[str] = []
        for key in RECOMMENDATION_KEYS:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                collected.append(candidate.strip())
            elif isinstance(candidate, list):
                for item in candidate:
                    if isinstance(item, dict):
                        recommendation = item.get("Recommendation") or item.get("recommendation")
                        if isinstance(recommendation, str) and recommendation.strip():
                            collected.append(recommendation.strip())
                    elif isinstance(item, str) and item.strip():
                        collected.append(item.strip())
            elif isinstance(candidate, dict):
                nested = candidate.get("Recommendation") or candidate.get("recommendation")
                if isinstance(nested, str) and nested.strip():
                    collected.append(nested.strip())
        if not collected:
            return None
        return "\n".join(dict.fromkeys(collected))

    def _metadata_fields(self, value: dict[str, Any]) -> dict[str, Any]:
        keep: dict[str, Any] = {}
        for key in ("Class of Recommendation", "Level of Evidence", "section", "Section", "Page", "page"):
            if key in value:
                keep[key] = value[key]
        return keep
