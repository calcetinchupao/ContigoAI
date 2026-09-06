"""Capas de embeddings para RAG.

Prioriza fastembed (ONNX, liviano). Si no está disponible, usa TF-IDF de
scikit-learn como respaldo (no requiere descarga de modelos grandes).
"""
import numpy as np

try:
    from fastembed import TextEmbedding

    _EMBEDDER = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
    _MODE = "fastembed"
except Exception:  # noqa: BLE001 - respaldo si fastembed no instala en esta máquina
    from sklearn.feature_extraction.text import TfidfVectorizer

    _EMBEDDER = None
    _MODE = "tfidf"
    _VECTORIZER = None

DIM = None


def _fit_tfidf(corpus):
    global _VECTORIZER, DIM
    _VECTORIZER = TfidfVectorizer()
    _VECTORIZER.fit(corpus)
    DIM = len(_VECTORIZER.vocabulary_)


def modo() -> str:
    return _MODE


def dimension() -> int:
    if _MODE == "fastembed":
        return _EMBEDDER.dimension
    if DIM is None:
        _fit_tfidf(["placeholder"])
    return DIM


def embed_textos(textos: list[str]) -> np.ndarray:
    """Devuelve una matriz (n, dim) con el embedding de cada texto."""
    if not textos:
        return np.zeros((0, 384), dtype="float32")
    if _MODE == "fastembed":
        return np.array(list(_EMBEDDER.embed(textos)), dtype="float32")
    if _VECTORIZER is None:
        _fit_tfidf(textos)
    return np.asarray(_VECTORIZER.transform(textos).toarray(), dtype="float32")


def embed_consulta(texto: str) -> np.ndarray:
    """Embedding de una consulta, compatible con índices ya creados."""
    if _MODE == "fastembed":
        return np.asarray(next(_EMBEDDER.embed([texto])), dtype="float32").reshape(1, -1)
    return np.asarray(_VECTORIZER.transform([texto]).toarray(), dtype="float32")