"""Memoria de ContigoAI: corto plazo (historial) y largo plazo (notas
semánticas y derivaciones), persistida en SQLite.

- Corto plazo: últimos turnos de la conversación por `session_id`.
- Largo plazo: notas/resúmenes con embedding para recuperación semántica.
- Derivaciones: registro anónimo escrito por la herramienta de escritura.

La base vive en `datos/memoria/contigoai.db` por defecto. Puede cambiarse
con la variable de entorno CONTIGOAI_DB (útil en pruebas).
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from config import BASE_DIR

DB_POR_DEFECTO = BASE_DIR / "datos" / "memoria" / "contigoai.db"
ORDEN_RIESGO = {"ninguno": 0, "moderado": 1, "alto": 2}


def ruta_db() -> Path:
    personalizada = os.getenv("CONTIGOAI_DB", "").strip()
    return Path(personalizada) if personalizada else DB_POR_DEFECTO


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Memoria:
    """Almacén de memoria del agente respaldado por SQLite."""

    def __init__(self, ruta: str | Path | None = None):
        self.ruta = Path(ruta) if ruta else ruta_db()
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self._crear_esquema()

    @contextmanager
    def _conexion(self):
        con = sqlite3.connect(self.ruta, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _crear_esquema(self) -> None:
        with self._conexion() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS sesiones (
                    session_id TEXT PRIMARY KEY,
                    creada TEXT NOT NULL,
                    actualizada TEXT NOT NULL,
                    riesgo_max TEXT NOT NULL DEFAULT 'ninguno',
                    protocolo_activo INTEGER NOT NULL DEFAULT 0,
                    herramientas TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS turnos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turno INTEGER NOT NULL,
                    rol TEXT NOT NULL,
                    texto TEXT NOT NULL,
                    intencion TEXT,
                    nivel_riesgo TEXT,
                    creado TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memorias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    texto TEXT NOT NULL,
                    tipo TEXT NOT NULL DEFAULT 'nota',
                    vector BLOB NOT NULL,
                    dim INTEGER NOT NULL,
                    creado TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS derivaciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    nivel_riesgo TEXT NOT NULL,
                    recursos TEXT NOT NULL,
                    resumen TEXT NOT NULL,
                    creado TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_turnos_sesion ON turnos(session_id);
                CREATE INDEX IF NOT EXISTS idx_memorias_sesion ON memorias(session_id);
                CREATE INDEX IF NOT EXISTS idx_derivaciones_sesion ON derivaciones(session_id);
                """
            )

    # ------------------------------------------------------------------
    # Sesión y memoria de corto plazo
    # ------------------------------------------------------------------
    def asegurar_sesion(self, session_id: str) -> None:
        ahora = _ahora()
        with self._conexion() as con:
            con.execute(
                "INSERT OR IGNORE INTO sesiones (session_id, creada, actualizada) VALUES (?, ?, ?)",
                (session_id, ahora, ahora),
            )

    def estado_sesion(self, session_id: str) -> dict:
        self.asegurar_sesion(session_id)
        with self._conexion() as con:
            fila = con.execute(
                "SELECT * FROM sesiones WHERE session_id = ?", (session_id,)
            ).fetchone()
            turnos = con.execute(
                "SELECT COUNT(*) AS n FROM turnos WHERE session_id = ? AND rol = 'usuario'",
                (session_id,),
            ).fetchone()["n"]
        herramientas = []
        try:
            herramientas = json.loads(fila["herramientas"] or "[]")
        except json.JSONDecodeError:
            pass
        return {
            "session_id": fila["session_id"],
            "creada": fila["creada"],
            "actualizada": fila["actualizada"],
            "riesgo_max": fila["riesgo_max"],
            "protocolo_activo": bool(fila["protocolo_activo"]),
            "herramientas_ultimo_turno": herramientas,
            "turnos": int(turnos),
        }

    def registrar_turno(
        self,
        session_id: str,
        turno: int,
        rol: str,
        texto: str,
        intencion: str | None = None,
        nivel_riesgo: str | None = None,
    ) -> None:
        self.asegurar_sesion(session_id)
        with self._conexion() as con:
            con.execute(
                "INSERT INTO turnos (session_id, turno, rol, texto, intencion, nivel_riesgo, creado) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, turno, rol, texto, intencion, nivel_riesgo, _ahora()),
            )

    def actualizar_estado(
        self,
        session_id: str,
        intencion: str,
        nivel_riesgo: str,
        protocolo_activo: bool,
        herramientas: list[str],
    ) -> None:
        estado = self.estado_sesion(session_id)
        riesgo_max = nivel_riesgo
        if ORDEN_RIESGO.get(estado["riesgo_max"], 0) > ORDEN_RIESGO.get(nivel_riesgo, 0):
            riesgo_max = estado["riesgo_max"]
        with self._conexion() as con:
            con.execute(
                "UPDATE sesiones SET actualizada = ?, riesgo_max = ?, protocolo_activo = ?, "
                "herramientas = ? WHERE session_id = ?",
                (
                    _ahora(),
                    riesgo_max,
                    int(protocolo_activo or estado["protocolo_activo"]),
                    json.dumps(herramientas, ensure_ascii=False),
                    session_id,
                ),
            )

    def historial(self, session_id: str, limite: int = 8) -> list[dict]:
        """Últimos turnos (usuario/asistente) en orden cronológico."""
        with self._conexion() as con:
            filas = con.execute(
                "SELECT turno, rol, texto, intencion, nivel_riesgo FROM turnos "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limite),
            ).fetchall()
        return [dict(f) for f in reversed(filas)]

    # ------------------------------------------------------------------
    # Memoria de largo plazo y recuperación semántica
    # ------------------------------------------------------------------
    def guardar_nota(self, session_id: str, texto: str, tipo: str = "nota") -> int:
        """Guarda una nota con su embedding para recuperación semántica."""
        import embeddings

        vector = np.asarray(embeddings.embed_textos([texto])[0], dtype="float32")
        with self._conexion() as con:
            cur = con.execute(
                "INSERT INTO memorias (session_id, texto, tipo, vector, dim, creado) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, texto, tipo, vector.tobytes(), int(vector.size), _ahora()),
            )
            return int(cur.lastrowid)

    def buscar_contexto(
        self, session_id: str, consulta: str, k: int = 3, umbral: float = 0.20,
        limite: int = 200,
    ) -> list[dict]:
        """Recupera las notas más similares a la consulta (similitud coseno)."""
        import embeddings

        with self._conexion() as con:
            filas = con.execute(
                "SELECT id, texto, tipo, vector, dim, creado FROM memorias "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limite),
            ).fetchall()
        if not filas:
            return []

        q = np.asarray(embeddings.embed_consulta(consulta)[0], dtype="float32")
        vectores, validas = [], []
        for fila in filas:
            if int(fila["dim"]) != q.size:
                continue
            vectores.append(np.frombuffer(fila["vector"], dtype="float32"))
            validas.append(fila)
        if not vectores:
            return []

        matriz = np.vstack(vectores)
        normas = np.linalg.norm(matriz, axis=1)
        normas[normas == 0] = 1.0
        similitudes = (matriz @ q) / (normas * (np.linalg.norm(q) or 1.0))
        orden = np.argsort(-similitudes)
        resultados = []
        for i in orden[:k]:
            sim = float(similitudes[i])
            if sim < umbral:
                continue
            fila = validas[int(i)]
            resultados.append(
                {
                    "id": int(fila["id"]),
                    "texto": fila["texto"],
                    "tipo": fila["tipo"],
                    "similitud": round(sim, 4),
                    "creado": fila["creado"],
                }
            )
        return resultados

    def notas(self, session_id: str, tipo: str | None = None, limite: int = 50) -> list[dict]:
        sql = "SELECT id, texto, tipo, creado FROM memorias WHERE session_id = ?"
        params: list = [session_id]
        if tipo:
            sql += " AND tipo = ?"
            params.append(tipo)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limite)
        with self._conexion() as con:
            return [dict(f) for f in con.execute(sql, params).fetchall()]

    # ------------------------------------------------------------------
    # Derivaciones (escritura)
    # ------------------------------------------------------------------
    def registrar_derivacion(
        self, session_id: str, nivel_riesgo: str, recursos: str, resumen: str
    ) -> int:
        with self._conexion() as con:
            cur = con.execute(
                "INSERT INTO derivaciones (session_id, nivel_riesgo, recursos, resumen, creado) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, nivel_riesgo, recursos, resumen, _ahora()),
            )
            return int(cur.lastrowid)

    def derivaciones(self, session_id: str | None = None, limite: int = 50) -> list[dict]:
        sql = "SELECT * FROM derivaciones"
        params: list = []
        if session_id:
            sql += " WHERE session_id = ?"
            params.append(session_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limite)
        with self._conexion() as con:
            return [dict(f) for f in con.execute(sql, params).fetchall()]
