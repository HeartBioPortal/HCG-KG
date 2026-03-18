from __future__ import annotations

from hcg_kg.extract.factory import create_extractor
from hcg_kg.extract.heuristic import HeuristicBiomedicalExtractor


def test_default_extractor_factory_returns_heuristic(local_settings):
    extractor = create_extractor(local_settings)

    assert isinstance(extractor, HeuristicBiomedicalExtractor)
