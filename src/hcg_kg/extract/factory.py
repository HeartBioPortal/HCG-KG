from __future__ import annotations

from hcg_kg.config.models import ProjectSettings
from hcg_kg.extract.heuristic import HeuristicBiomedicalExtractor


def create_extractor(settings: ProjectSettings) -> object:
    provider = settings.models.provider
    if provider == "llamaindex":
        from hcg_kg.extract.llamaindex_extractor import LlamaIndexBiomedicalExtractor

        return LlamaIndexBiomedicalExtractor(settings)
    if provider == "huggingface":
        from hcg_kg.extract.llamaindex_extractor import LlamaIndexBiomedicalExtractor

        return LlamaIndexBiomedicalExtractor(settings)
    return HeuristicBiomedicalExtractor(settings)
