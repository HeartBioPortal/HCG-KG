from __future__ import annotations

from dataclasses import dataclass

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from hcg_kg.config.models import ProjectSettings
from hcg_kg.models.documents import GuidelineDocument
from hcg_kg.models.query import SupportingSnippet
from hcg_kg.utils import ensure_dir


@dataclass
class TfidfArtifact:
    vectorizer: TfidfVectorizer
    matrix: object
    snippets: list[SupportingSnippet]


class TfidfSnippetIndex:
    def __init__(self, settings: ProjectSettings) -> None:
        self.settings = settings
        self.path = settings.tfidf_index_path

    def build(self, documents: list[GuidelineDocument]) -> TfidfArtifact:
        snippets = [
            SupportingSnippet(
                snippet_id=snippet.snippet_id,
                text=snippet.text,
                guideline_title=document.metadata.title,
                section_path=snippet.provenance.section_path,
                page=snippet.provenance.page,
                source_json_path=snippet.provenance.source_json_path,
                source_pdf_path=snippet.provenance.source_pdf_path,
            )
            for document in documents
            for snippet in document.snippets
        ]
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        matrix = vectorizer.fit_transform([snippet.text for snippet in snippets]) if snippets else None
        ensure_dir(self.path.parent)
        joblib.dump({"vectorizer": vectorizer, "matrix": matrix, "snippets": snippets}, self.path)
        return TfidfArtifact(vectorizer=vectorizer, matrix=matrix, snippets=snippets)

    def load(self) -> TfidfArtifact | None:
        if not self.path.exists():
            return None
        payload = joblib.load(self.path)
        return TfidfArtifact(
            vectorizer=payload["vectorizer"],
            matrix=payload["matrix"],
            snippets=payload["snippets"],
        )

    def search(self, query: str, top_k: int) -> list[SupportingSnippet]:
        artifact = self.load()
        if artifact is None or artifact.matrix is None:
            return []
        query_vector = artifact.vectorizer.transform([query])
        scores = (artifact.matrix @ query_vector.T).toarray().ravel()
        if not np.any(scores):
            return []
        ranked = np.argsort(scores)[::-1][:top_k]
        return [artifact.snippets[index] for index in ranked if scores[index] > 0]
