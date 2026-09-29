"""
Embedding comparison and similarity search. Implemented in Phase 8-9.

Planned interface:
    compare_embeddings(a, b) -> float          # cosine similarity
    search_similar_faces(query, top_k) -> list  # ranked candidates, scores only

This module never returns a "match" verdict — only ranked candidates
with similarity scores. Human verification decides the outcome
(see backend /api/v1/verification).
"""


def compare_embeddings(embedding_a, embedding_b):
    raise NotImplementedError("Implemented in Phase 8")


def search_similar_faces(query_embedding, top_k: int = 10):
    raise NotImplementedError("Implemented in Phase 8-9")
