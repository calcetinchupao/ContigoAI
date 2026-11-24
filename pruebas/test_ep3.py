"""Pruebas EP3 sin red: métricas, aislamiento, trazas, API y regresión del agente."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))
TEMPORAL = tempfile.TemporaryDirectory(prefix="contigoai_tests_ep3_")
RAIZ = Path(TEMPORAL.name)
os.environ["CONTIGOAI_EMBEDDINGS"] = "tfidf"
os.environ["CONTIGOAI_INDICE_DIR"] = str(RAIZ / "indice")
os.environ["CONTIGOAI_DB"] = str(RAIZ / "memoria.db")
os.environ["CONTIGOAI_OBS_DB"] = str(RAIZ / "metricas.db")
os.environ["CONTIGOAI_OBS_TOKEN"] = "clave-sintetica-test"

from fastapi.testclient import TestClient  # noqa: E402
import agente as agente_mod  # noqa: E402
import api  # noqa: E402
import llm  # noqa: E402
from ingesta import ingestar  # noqa: E402
from memoria import Memoria  # noqa: E402
from observabilidad import ErrorAgente, Observatorio, percentil, registrar_llm, resumir, tramo  # noqa: E402


def setUpModule():
    ingestar()


def tearDownModule():
    TEMPORAL.cleanup()


class ObservabilidadTests(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory(dir=RAIZ)
        self.base = Path(self.carpeta.name)
        self.obs = Observatorio(self.base / "obs.db")
        self.agente = agente_mod.Agente(Memoria(self.base / "mem.db"), self.obs)
        self.parches = [patch.object(agente_mod, "provider_ok", return_value=True),
                        patch.object(llm, "completar", return_value="Respuesta sintética privada"),
                        patch.object(api, "_AGENTE", self.agente)]
        for p in self.parches:
            p.start()
        self.cliente = TestClient(api.app)
        self.headers = {"X-Observabilidad-Token": "clave-sintetica-test"}

    def tearDown(self):
        self.cliente.close()
        for p in reversed(self.parches):
            p.stop()
        self.carpeta.cleanup()

    def test_sin_datos_no_inventa_precision(self):
        r = resumir([])
        self.assertIsNone(r["precision_pct"])
        self.assertIsNone(r["consistencia_pct"])
        self.assertIsNone(r["tasa_error_pct"])
        self.assertEqual(r["total"], 0)

    def test_percentil_interpolado(self):
        self.assertEqual(percentil([10, 20, 30, 40], .95), 38.5)
        self.assertEqual(percentil([10], .95), 10)

    def test_traza_no_guarda_texto_ni_sesion(self):
        mensaje = "Hola, mi correo es privado@example.com y mi clave es SECRETO-UNICO"
        r = self.agente.procesar(mensaje, "identificador-privado")
        self.assertTrue(r["observabilidad"]["registrada"])
        registro = self.obs.detalle(r["observabilidad"]["trace_id"])
        texto = json.dumps(registro)
        for sensible in (mensaje, "privado@example.com", "SECRETO-UNICO", "identificador-privado", "Respuesta sintética privada"):
            self.assertNotIn(sensible, texto)
        self.assertGreater(registro["latencia_ms"], 0)
        self.assertIn("guardar_memoria", [e["nombre"] for e in registro["eventos"]])
        self.assertTrue(any(e["parent_id"] for e in registro["eventos"]))

    def test_fallo_persiste_span_y_no_filtra_excepcion(self):
        with patch.object(llm, "completar", side_effect=TimeoutError("api-key-secreta texto personal")):
            r = self.cliente.post("/chat", json={"mensaje": "hola"})
        self.assertEqual(r.status_code, 503)
        traza = self.obs.detalle(r.json()["detail"]["trace_id"])
        self.assertEqual(traza["estado"], "error")
        self.assertEqual(traza["error_tipo"], "TimeoutError")
        self.assertTrue(any(e["nombre"] == "generar_respuesta" and e["estado"] == "error" for e in traza["eventos"]))
        self.assertNotIn("api-key-secreta", r.text + json.dumps(traza))

    def test_precision_y_consistencia_con_desaciertos(self):
        for intencion in ("saludo", "saludo", "apoyo"):
            with self.obs.ejecucion(5, {"origen": "evaluacion_simulada", "lote": "lote", "caso": "caso",
                                      "esperado": {"intencion": "saludo"}}) as r:
                r["intencion"] = intencion
        resumen = resumir(self.obs.consultar())
        self.assertEqual(resumen["precision_pct"], 66.67)
        self.assertEqual(resumen["consistencia_pct"], 33.33)
        self.assertEqual(resumen["pares_comparados"], 3)

    def test_error_etiquetado_cuenta_como_desacierto(self):
        try:
            with self.obs.ejecucion(5, {"origen": "evaluacion_real", "esperado": {"intencion": "saludo"}}):
                raise TimeoutError()
        except TimeoutError:
            pass
        resumen = resumir(self.obs.consultar())
        self.assertEqual(resumen["precision_pct"], 0)
        self.assertEqual(resumen["tasa_error_pct"], 100)

    def test_consistencia_separa_lotes_y_casos(self):
        for lote in ("a", "b"):
            with self.obs.ejecucion(5, {"origen": "evaluacion_simulada", "lote": lote, "caso": "igual"}):
                pass
        self.assertIsNone(resumir(self.obs.consultar())["consistencia_pct"])

    def test_concurrencia_no_mezcla_trazas(self):
        def tarea(i):
            with self.obs.ejecucion(i) as r:
                with tramo("etapa_" + str(i)):
                    registrar_llm(entrada=i, salida=2)
            return r["trace_id"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(tarea, range(1, 9)))
        self.assertEqual(len(set(ids)), 8)
        for trace_id in ids:
            r = self.obs.detalle(trace_id)
            self.assertEqual(r["tokens_entrada"], r["caracteres_entrada"])
            self.assertEqual(r["eventos"][0]["nombre"], "etapa_" + str(r["caracteres_entrada"]))

    def test_fallo_monitoreo_no_interrumpe_chat(self):
        with patch.object(self.obs, "guardar", side_effect=sqlite3.OperationalError("cerrado")):
            r = self.agente.procesar("hola")
        self.assertFalse(r["observabilidad"]["registrada"])
        self.assertTrue(r["respuesta"])

    def test_retencion_elimina_registros_antiguos(self):
        with self.obs.ejecucion(1) as r:
            r["fecha"] = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(timespec="milliseconds")
        with self.obs.ejecucion(1):
            pass
        self.assertEqual(len(self.obs.consultar(dias=365)), 1)

    def test_dashboard_export_y_filtros_protegidos(self):
        self.agente.procesar("hola")
        self.assertEqual(self.cliente.get("/observabilidad").status_code, 200)
        for ruta in ("resumen", "trazas", "exportar?formato=csv", "exportar?formato=json"):
            url = "/api/observabilidad/" + ruta
            self.assertEqual(self.cliente.get(url).status_code, 401)
            self.assertEqual(self.cliente.get(url, headers=self.headers).status_code, 200)
        resumen = self.cliente.get("/api/observabilidad/resumen?origen=chat", headers=self.headers).json()
        self.assertEqual(resumen["total"], 1)
        self.assertEqual(self.cliente.get("/api/observabilidad/trazas?dias=0", headers=self.headers).status_code, 422)
        self.assertEqual(self.cliente.get("/api/observabilidad/trazas?origen=invalid", headers=self.headers).status_code, 422)
        self.assertEqual(self.cliente.get("/api/observabilidad/trazas/noexiste", headers=self.headers).status_code, 404)
        self.assertIn("trace_id", self.cliente.get("/api/observabilidad/exportar", headers=self.headers).text)

    def test_sin_clave_solo_loopback(self):
        with patch.dict(os.environ, {"CONTIGOAI_OBS_TOKEN": ""}):
            self.assertEqual(self.cliente.get("/api/observabilidad/resumen").status_code, 403)
            with TestClient(api.app, client=("127.0.0.1", 12345)) as local:
                self.assertEqual(local.get("/api/observabilidad/resumen").status_code, 200)

    def test_memoria_se_puede_borrar_sin_tocar_otras_sesiones(self):
        self.agente.procesar("hola", "sesion-a")
        self.agente.procesar("hola", "sesion-b")
        self.assertEqual(self.cliente.delete("/memoria/sesion-a").status_code, 401)
        self.assertEqual(self.cliente.delete("/memoria/sesion-a", headers=self.headers).status_code, 200)
        self.assertEqual(self.agente.memoria.historial("sesion-a"), [])
        self.assertEqual(self.agente.memoria.notas("sesion-a"), [])
        self.assertTrue(self.agente.memoria.historial("sesion-b"))
        self.assertEqual(len(self.obs.consultar()), 2)

    def test_api_sesiones_omitidas_son_independientes(self):
        a = self.cliente.post("/chat", json={"mensaje": "hola"}).json()
        b = self.cliente.post("/chat", json={"mensaje": "hola"}).json()
        self.assertNotEqual(a["session_id"], b["session_id"])
        self.assertEqual(b["memoria"]["turnos_previos"], 0)

    def test_validacion_entrada_no_ejecuta_agente(self):
        for mensaje in ("", "   ", "x" * 2001):
            self.assertEqual(self.cliente.post("/chat", json={"mensaje": mensaje}).status_code, 422)
        self.assertEqual(self.obs.consultar(), [])

    def test_continuidad_y_escrituras_en_memoria_inyectada(self):
        primero = self.agente.procesar("No quiero seguir viviendo", "continuidad")
        segundo = self.agente.procesar("Gracias por escucharme, sigo aquí", "continuidad")
        self.assertTrue(primero["protocolo_activado"])
        self.assertTrue(segundo["replanificado"])
        self.assertEqual(segundo["memoria"]["turnos_previos"], 1)
        self.assertEqual(len(self.agente.memoria.derivaciones("continuidad")), 2)
        self.assertTrue(self.agente.memoria.notas("continuidad", tipo="resumen_caso"))

    def test_tokens_del_proveedor_y_reintentos_con_span_fallido(self):
        import httpx
        solicitud = httpx.Request("POST", "https://example.invalid/chat/completions")
        respuestas = [httpx.Response(429, request=solicitud, text="dato sensible"),
                      httpx.Response(200, request=solicitud, json={"usage": {"prompt_tokens": 11, "completion_tokens": 7},
                          "choices": [{"message": {"content": "Respuesta privada"}}]})]
        with patch.object(llm.httpx, "post", side_effect=respuestas), patch.object(llm.time, "sleep"):
            with self.obs.ejecucion(4) as registro:
                salida = llm._chat_openai_compatible("https://example.invalid", "clave-test", "modelo", "sistema", "usuario")
        self.assertEqual(salida, "Respuesta privada")
        self.assertEqual(registro["tokens_entrada"], 11)
        self.assertEqual(registro["tokens_salida"], 7)
        self.assertEqual(registro["reintentos_llm"], 1)
        self.assertEqual(registro["eventos"][0]["estado"], "error")
        self.assertNotIn("dato sensible", json.dumps(self.obs.detalle(registro["trace_id"])))

    def test_tokens_desconocidos_no_se_estiman(self):
        self.agente.procesar("hola")
        resumen = resumir(self.obs.consultar())
        self.assertEqual(resumen["ejecuciones_con_tokens"], 0)
        self.assertIsNone(self.obs.consultar()[0]["tokens_entrada"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
