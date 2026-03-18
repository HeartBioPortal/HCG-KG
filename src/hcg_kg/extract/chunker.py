from __future__ import annotations

import re

from hcg_kg.models.documents import SourceSnippet
from hcg_kg.utils import make_id


def chunk_snippets(
    snippets: list[SourceSnippet],
    chunk_size: int,
    overlap: int,
) -> list[SourceSnippet]:
    """Split long snippets while preserving provenance."""
    if chunk_size <= 0:
        return snippets

    chunked: list[SourceSnippet] = []
    for snippet in snippets:
        text = snippet.text
        if len(text) <= chunk_size:
            chunked.append(snippet)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", text)
        start = 0
        current = ""
        window_index = 0
        while start < len(sentences):
            while start < len(sentences) and not current:
                current = sentences[start]
                start += 1
            while start < len(sentences) and len(current) + len(sentences[start]) + 1 <= chunk_size:
                current = f"{current} {sentences[start]}"
                start += 1
            chunked.append(
                snippet.model_copy(
                    update={
                        "snippet_id": make_id(snippet.snippet_id, str(window_index)),
                        "text": current,
                        "raw_fields": {**snippet.raw_fields, "parent_snippet_id": snippet.snippet_id},
                    }
                )
            )
            if overlap <= 0:
                current = ""
                window_index += 1
                continue
            overlap_text = current[-overlap:]
            current = overlap_text
            window_index += 1
    return chunked
