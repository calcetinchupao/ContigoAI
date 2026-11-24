"""Capas de embeddings para RAG.

Prioriza fastembed (ONNX, liviano). Si no está disponible, usa TF-IDF de
scikit-learn como respaldo (no requiere descarga de modelos grandes).
"""
import os
from pathlib import Path

import numpy as np

try:
    if os.getenv("CONTIGOAI_EMBEDDINGS", "auto").lower() == "tfidf":
        raise ImportError("Modo local TF-IDF solicitado")
    from fastembed import TextEmbedding

    opciones = {}
    if os.getenv("CONTIGOAI_FASTEMBED_CACHE"):
        opciones["cache_dir"] = os.environ["CONTIGOAI_FASTEMBED_CACHE"]
    if os.getenv("CONTIGOAI_MODELOS_SOLO_LOCAL") == "1":
        opciones["local_files_only"] = True
    _EMBEDDER = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2", **opciones)
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
        _iniciar_tfidf()
    return DIM


def embed_textos(textos: list[str]) -> np.ndarray:
    """Devuelve una matriz (n, dim) con el embedding de cada texto."""
    if not textos:
        return np.zeros((0, 384), dtype="float32")
    if _MODE == "fastembed":
        return np.array(list(_EMBEDDER.embed(textos)), dtype="float32")
    if _VECTORIZER is None:
        _iniciar_tfidf()
    return np.asarray(_VECTORIZER.transform(textos).toarray(), dtype="float32")


def embed_consulta(texto: str) -> np.ndarray:
    """Embedding de una consulta, compatible con índices ya creados."""
    if _MODE == "fastembed":
        return np.asarray(next(_EMBEDDER.embed([texto])), dtype="float32").reshape(1, -1)
    if _VECTORIZER is None:
        _iniciar_tfidf()
    return np.asarray(_VECTORIZER.transform([texto]).toarray(), dtype="float32")


def _iniciar_tfidf():
    """Vocabulario estable entre procesos; reconstruir el índice al cambiar el corpus."""
    carpeta = Path(__file__).resolve().parent.parent / "datos"
    corpus = [p.read_text(encoding="utf-8") for p in sorted(carpeta.glob("*.md"))]
    _fit_tfidf(corpus or ["apoyo emocional salud comunidad familia trabajo ansiedad"])
