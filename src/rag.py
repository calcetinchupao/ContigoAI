"""Módulo de recuperación aumentada (RAG): carga el índice y recupera los
trozos más relevantes a una consulta mediante similitud coseno."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import embeddings  # noqa: E402
from config import INDICE_DIR  # noqa: E402


class Recuperador:
    def __init__(self, k: int = 4):
        self.k = k
        self._cargar()

    def _cargar(self):
        archivo_vectores = INDICE_DIR / "vectores.npy"
        archivo_trozos = INDICE_DIR / "trozos.json"
        if not archivo_vectores.exists() or not archivo_trozos.exists():
            raise FileNotFoundError(
                "Índice RAG no encontrado. Ejecuta primero: python src/ingesta.py"
            )
        self.vectores = np.load(archivo_vectores)
        with open(archivo_trozos, encoding="utf-8") as fh:
            self.trozos = json.load(fh)
        if embeddings.modo() == "tfidf" and self.vectores.size and self.vectores.ndim == 1:
            self.vectores = self.vectores.reshape(1, -1)

    def recuperar(self, consulta: str, k: int | None = None) -> list[dict]:
        """Devuelve los k trozos más similares con su puntaje de similitud coseno."""
        k = k or self.k
        q = embeddings.embed_consulta(consulta)
        if q.shape[1] != self.vectores.shape[1]:
            raise ValueError("Dimensión del índice no coincide; re-ejecuta python src/ingesta.py")
        normas = np.linalg.norm(self.vectores, axis=1, keepdims=True)
        normas[normas == 0] = 1.0
        sim = (self.vectores @ q.T).flatten() / normas.flatten()
        top = np.argsort(-sim)[:k]
        return [
            {
                "fuente": self.trozos[i]["fuente"],
                "seccion": self.trozos[i]["id"].split("#")[-1],
                "texto": self.trozos[i]["texto"],
                "similitud": round(float(sim[i]), 4),
            }
            for i in top
        ]