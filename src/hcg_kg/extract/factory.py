from __future__ import annotations

from typing import Protocol

from hcg_kg.config.models import ProjectSettings
from hcg_kg.extract.heuristic import HeuristicBiomedicalExtractor
from hcg_kg.models.documents import GuidelineDocument
from hcg_kg.models.graph import ExtractionResult


class BiomedicalExtractor(Protocol):
    def extract(self, document: GuidelineDocument) -> ExtractionResult: ...


def create_extractor(settings: ProjectSettings) -> BiomedicalExtractor:
    provider = settings.models.provider
    if provider == "llamaindex":
        from hcg_kg.extract.llamaindex_extractor import LlamaIndexBiomedicalExtractor

        return LlamaIndexBiomedicalExtractor(settings)
    if provider == "huggingface":
        from hcg_kg.extract.llamaindex_extractor import LlamaIndexBiomedicalExtractor

        return LlamaIndexBiomedicalExtractor(settings)
    return HeuristicBiomedicalExtractor(settings)
