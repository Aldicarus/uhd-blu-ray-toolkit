"""La salida de `mkvmerge --gui-mode`: los errores y los avisos se ven.

Con `--gui-mode` mkvmerge escribe sus errores como `#GUI#error …` y sus avisos
como `#GUI#warning …`, por stdout (comprobado con la v102). Los cuatro sitios
que lo leen —las fases D y E de Tab 1, el `_run_streaming` de CMv4.0 y la
Fase B de Multiplexar— tiraban toda línea `#GUI#` que no fuera de progreso, y
un mkvmerge que fallaba dejaba en el log «código 2» sin el motivo. Caso real
(octubre de 2026): Hobbs & Shaw, un playlist de dos m2ts que fallaba antes de
abrir la salida. Nadie lo vio porque el mkvmerge falso escribía `Error: …`
también en modo GUI.

Aquí: la traducción, pura; el runner de CMv4.0 ejecutado con el binario falso
(los de Tab 1 y Tab 4 están en `test_fases_de_tab1` y `test_mux_endpoints`), y
el guard de que ningún lector vuelva a filtrar `#GUI#` por su cuenta.

Ejecutar desde la raíz del repo:
    python3 -m unittest app.tests.test_salida_mkvmerge -v
"""
import ast
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(APP_DIR / "tests"))

from cmv40_harness import CollectingLog, FakeToolbox  # noqa: E402
from phases import salida_mkvmerge  # noqa: E402


class TestLaTraduccion(unittest.TestCase):

    def test_el_progreso_sigue_siendo_el_contrato_del_panel(self):
        self.assertEqual(salida_mkvmerge.traducir("#GUI#progress 45%"), "Progress: 45%")

    def test_un_error_sale_como_sin_el_modo_gui(self):
        self.assertEqual(
            salida_mkvmerge.traducir("#GUI#error The file 'x' could not be opened."),
            "Error: The file 'x' could not be opened.")

    def test_un_aviso_sale_como_sin_el_modo_gui(self):
        self.assertEqual(
            salida_mkvmerge.traducir("#GUI#warning 'a.mka': A track was skipped."),
            "Warning: 'a.mka': A track was skipped.")

    def test_el_resto_de_lineas_de_control_no_se_ensena(self):
        for linea in ("#GUI#begin_scanning_playlists", "#GUI#end_scanning_playlists",
                      "#GUI#progress_scanning 3"):
            self.assertIsNone(salida_mkvmerge.traducir(linea), linea)

    def test_lo_que_no_es_de_control_sale_tal_cual(self):
        linea = "'00294.m2ts' track 0: Using the output module for the format 'HEVC'."
        self.assertEqual(salida_mkvmerge.traducir(linea), linea)

    def test_el_error_se_reconoce_y_lo_demas_no(self):
        self.assertEqual(salida_mkvmerge.error_de("#GUI#error  boom "), "boom")
        for linea in ("#GUI#warning boom", "Error: boom", "#GUI#progress 1%",
                      "#GUI#error "):
            self.assertIsNone(salida_mkvmerge.error_de(linea), linea)


class TestElRunnerDeCMv40(unittest.IsolatedAsyncioTestCase):
    """El `_run_streaming` que usa la Fase G para el remux final."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="salida_mkvmerge_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tb = FakeToolbox(self.tmp)
        self.tb.install()
        self.addCleanup(self.tb.uninstall)
        self.entrada = self.tmp / "BL.hevc"
        self.entrada.write_bytes(b"\x00" * 64)

    async def _remux(self):
        from phases import cmv40_pipeline
        log = CollectingLog()
        rc = await cmv40_pipeline._run_streaming(
            ["mkvmerge", "--gui-mode", "-o", str(self.tmp / "out.mkv"), str(self.entrada)],
            log_callback=log)
        return rc, log

    async def test_el_error_de_mkvmerge_llega_al_log(self):
        error = "The file 'source.mkv' could not be opened for reading: open file error."
        self.tb.fail_when_arg("mkvmerge", "--gui-mode", rc=2, stderr="",
                              error_mkvmerge=error)
        rc, log = await self._remux()
        self.assertEqual(rc, 2)
        self.assertIn("Error: " + error, log.lines)

    async def test_los_avisos_de_mkvmerge_llegan_al_log(self):
        self.tb.avisos_de_mkvmerge("'BL.hevc': A track was skipped.")
        rc, log = await self._remux()
        self.assertEqual(rc, 1)
        self.assertIn("Warning: 'BL.hevc': A track was skipped.", log.lines)
        self.assertEqual([l for l in log.lines if l.startswith("#GUI#")], [])


class TestElMkvmergeFalsoEscribeComoElReal(unittest.TestCase):
    """Comprobado con la v102: el error va por STDOUT, con `#GUI#error` en
    modo GUI y `Error:` sin él. Con el fake escribiendo `Error:` también en
    modo GUI, ningún test veía que los lectores tiraban el error."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="salida_mkvmerge_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tb = FakeToolbox(self.tmp)
        self.tb.install()
        self.addCleanup(self.tb.uninstall)

    def _correr(self, *args):
        import os
        import subprocess
        return subprocess.run(["mkvmerge", *args], capture_output=True, text=True,
                              env={**os.environ, "PATH": f"{self.tb.bin_dir}{os.pathsep}"
                                   f"{os.environ.get('PATH', '')}"})

    def test_un_fichero_que_no_existe(self):
        falta = str(self.tmp / "no_existe.m2ts")
        out = str(self.tmp / "out.mkv")
        con = self._correr("--gui-mode", "-o", out, falta)
        sin = self._correr("-o", out, falta)
        self.assertEqual((con.returncode, sin.returncode), (2, 2))
        self.assertIn(f"#GUI#error The file '{falta}' could not be opened", con.stdout)
        self.assertIn(f"Error: The file '{falta}' could not be opened", sin.stdout)
        self.assertNotIn("Error:", con.stdout)


class TestNadieFiltraLasLineasDeControlPorSuCuenta(unittest.TestCase):
    """Los cuatro lectores tenían cada uno su `elif text.startswith("#GUI#"):
    continue`, y los cuatro se tragaban el error. Un quinto escrito igual
    volvería a hacerlo: toda decisión sobre una línea `#GUI#` va por
    `salida_mkvmerge`. La única excepción es leer el porcentaje de
    `#GUI#progress`, que no descarta nada."""

    PERMITIDOS = {"#GUI#progress "}

    def test_ningun_literal_gui_fuera_de_salida_mkvmerge(self):
        hallados = []
        for ruta in sorted(APP_DIR.rglob("*.py")):
            rel = ruta.relative_to(APP_DIR)
            if rel.parts[0] == "tests" or rel.name == "salida_mkvmerge.py":
                continue
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
                        and nodo.value.startswith("#GUI#")
                        and nodo.value not in self.PERMITIDOS):
                    hallados.append(f"{rel}:{nodo.lineno} {nodo.value!r}")
        self.assertEqual(hallados, [])

    def test_el_guard_mira_codigo_que_existe(self):
        """Sin lectores que recorrer, el guard pasaría en verde vigilando el
        vacío: los cuatro tienen que usar `salida_mkvmerge`."""
        for rel in ("phases/phase_d.py", "phases/phase_e.py",
                    "phases/mux_pipeline.py", "phases/cmv40_pipeline.py"):
            texto = (APP_DIR / rel).read_text(encoding="utf-8")
            self.assertIn("salida_mkvmerge.traducir(", texto, rel)


if __name__ == "__main__":
    unittest.main()
