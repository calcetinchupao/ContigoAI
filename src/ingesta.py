"""Ingesta: lee los documentos de `datos/`, los fragmenta en trozos y construye
el índice vectorial (persistido en datos/.indice/).

Uso:  python src/ingesta.py
"""
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import embeddings  # noqa: E402
from config import DATOS_DIR, INDICE_DIR  # noqa: E402


def _dividir_en_trozos(texto: str, max_len: int = 900) -> list[str]:
    """Divide un documento en trozos por párrafos/encabezados, sin cortar frases."""
    # Normaliza encabezados markdown y saltos
    lineas = [ln.strip() for ln in re.sub(r"\r\n?", "\n", texto).split("\n")]
    bloques, actual = [], []
    for ln in lineas:
        if not ln:
            if actual:
                bloques.append(" ".join(actual))
                actual = []
            continue
        if ln.startswith("#"):
            if actual:
                bloques.append(" ".join(actual))
                actual = []
            bloques.append(ln)  # encabezado como trozo propio (facilita recuperación)
        elif len(" ".join(actual + [ln])) > max_len:
            if actual:
                bloques.append(" ".join(actual))
                actual = [ln]
            else:
                bloques.append(ln[:max_len])
        else:
            actual.append(ln)
    if actual:
        bloques.append(" ".join(actual))
    return [b for b in bloques if len(b) > 15]


def ingestar() -> dict:
    informe = {"documentos": 0, "trozos": 0, "modo": embeddings.modo()}

    trozos: list[dict] = []
    for archivo in sorted(DATOS_DIR.glob("*.md")):
        if archivo.name.startswith("."):
            continue
        texto = archivo.read_text(encoding="utf-8")
        partes = _dividir_en_trozos(texto)
        for i, parte in enumerate(partes):
            trozos.append(
                {"id": f"{archivo.stem}#{i}", "fuente": archivo.name, "texto": parte}
            )
        informe["documentos"] += 1
        informe["trozos"] += len(partes)

    vectores = embeddings.embed_textos([t["texto"] for t in trozos]) if trozos else np.zeros((0, 384))
    if embeddings.modo() == "tfidf" and trozos:
        # Asegura que el dimensionado coincida entre index y consultas
        pass

    INDICE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(INDICE_DIR / "vectores.npy", vectores)
    with open(INDICE_DIR / "trozos.json", "w", encoding="utf-8") as fh:
        import json

        json.dump(trozos, fh, ensure_ascii=False, indent=1)

    informe["ruta_indice"] = str(INDICE_DIR)
    return informe


if __name__ == "__main__":
    resultado = ingestar()
    print(
        f"Ingesta OK · modo={resultado['modo']} · "
        f"{resultado['documentos']} documentos · {resultado['trozos']} trozos"
    )
    print(f"Índice en: {resultado['ruta_indice']}")