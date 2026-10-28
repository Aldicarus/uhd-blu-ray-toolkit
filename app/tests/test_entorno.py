"""La mudanza de nombre (v1.0) tiene que ser transparente.

Hasta la v1.0 la app se publicaba como hdo-iso-converter —repo, imagen y
contenedor— con variables `HDO_*`. Desde entonces se llama como la app
—repo, imagen, servicio y contenedor `uhd-blu-ray-toolkit`,
variables `UBT_*`— y quien venga de antes no tiene que tocar su `.env`: cada
variable nueva cae a la de antes.

Este módulo fija las dos mitades. Que las variables viejas se sigan leyendo
(la regla vive en `entorno.variable`, y nadie más lee un `HDO_` a pelo), y que
no quede ningún enlace funcional al repo o a la imagen de antes: uno olvidado
no falla, apunta a un sitio donde ya no se publica nada.

Ejecutar desde la raíz del repo:
    python3 -m unittest app.tests.test_entorno -v
"""
import ast
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
APP_DIR = TESTS.parent
RAIZ = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))

import entorno  # noqa: E402

NOMBRE_VIEJO = "hdo-" + "iso-converter"   # compuesto: el guard no se encuentra a sí mismo


class TestLaRegla(unittest.TestCase):

    def setUp(self):
        parche = mock.patch.dict(os.environ, {}, clear=False)
        parche.start()
        self.addCleanup(parche.stop)
        for v in ("UBT_PRUEBA", "HDO_PRUEBA"):
            os.environ.pop(v, None)

    def test_la_nueva(self):
        os.environ["UBT_PRUEBA"] = "a"
        self.assertEqual(entorno.variable("PRUEBA"), "a")

    def test_la_de_antes_de_la_v1_tambien_vale(self):
        os.environ["HDO_PRUEBA"] = "b"
        self.assertEqual(entorno.variable("PRUEBA"), "b")

    def test_si_estan_las_dos_manda_la_nueva(self):
        os.environ["UBT_PRUEBA"] = "a"
        os.environ["HDO_PRUEBA"] = "b"
        self.assertEqual(entorno.variable("PRUEBA"), "a")

    def test_una_vacia_cuenta_como_ausente(self):
        """El compose pasa SIEMPRE la nueva (`UBT_X=${UBT_X:-${HDO_X:-}}`):
        vacía es como llega la que nadie ha puesto."""
        os.environ["UBT_PRUEBA"] = ""
        os.environ["HDO_PRUEBA"] = "b"
        self.assertEqual(entorno.variable("PRUEBA"), "b")

    def test_sin_ninguna_el_valor_por_defecto(self):
        self.assertEqual(entorno.variable("PRUEBA", "x"), "x")
        self.assertEqual(entorno.variable("PRUEBA"), "")


class TestNadieLeeUnaVariableViejaAPelo(unittest.TestCase):
    """Un `os.environ.get("HDO_…")` nuevo se saltaría la variable `UBT_` de
    quien ya haya migrado su `.env`, y uno con `UBT_` a pelo la de quien no."""

    def test_en_la_app(self):
        fuera = {APP_DIR / "entorno.py"}
        sueltos = []
        for py in APP_DIR.rglob("*.py"):
            if "tests" in py.parts or py in fuera or ".venv" in py.parts:
                continue
            arbol = ast.parse(py.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
                        and re.fullmatch(r"(HDO|UBT)_[A-Z_]+", nodo.value)):
                    sueltos.append(f"{py.relative_to(RAIZ)}:{nodo.lineno} {nodo.value}")
        # Se permite la que la regresión real fija para las imágenes viejas,
        # que solo leen HDO_ y no tienen `entorno`.
        sueltos = [s for s in sueltos if not s.startswith("app/tools/regresion_real.py")]
        self.assertEqual(sueltos, [], "léelas con `entorno.variable(...)`")


class TestElComposeCaeALaDeAntes(unittest.TestCase):

    def setUp(self):
        self.compose = (RAIZ / "docker" / "docker-compose.yml").read_text(encoding="utf-8")
        self.ejemplo = (RAIZ / "docker" / ".env.example").read_text(encoding="utf-8")

    def test_el_puerto(self):
        self.assertIn('"${UBT_PORT:-${HDO_PORT:-8090}}:8080"', self.compose)
        self.assertIn("UBT_PORT=8090", self.ejemplo)

    def test_cada_hdo_del_compose_es_el_respaldo_de_una_ubt(self):
        """Ninguna variable vieja se usa sola: siempre dentro del valor por
        defecto de su gemela nueva."""
        for m in re.finditer(r"\$\{HDO_([A-Z_]+)", self.compose):
            nombre = m.group(1)
            self.assertIn(f"${{UBT_{nombre}:-${{HDO_{nombre}", self.compose, nombre)

    def test_cada_variable_que_lee_la_app_llega_al_contenedor(self):
        """Compose solo usa el `.env` para sustituir variables en el propio
        compose: lo que no esté en `environment:` no llega al contenedor.
        `UBT_IDIOMA`, `UBT_TEMA` y `UBT_FIRMA_CLAVE` estaban documentadas como
        configurables desde el `.env` y no se pasaban (ya en la v3.5.0, con
        `HDO_`). Lo encontró la revisión de Codex previa a la v1.0.0."""
        leidas = set()
        for f in (RAIZ / "app").rglob("*.py"):
            if "tests" in f.parts:
                continue
            leidas |= set(re.findall(r'entorno\.variable\("([A-Z_]+)"',
                                     f.read_text(encoding="utf-8")))
        self.assertTrue(leidas, "no se encontró ninguna lectura de entorno.variable")
        for nombre in sorted(leidas):
            with self.subTest(variable=nombre):
                self.assertIn(f"- UBT_{nombre}=${{UBT_{nombre}:-${{HDO_{nombre}:-}}}}",
                              self.compose)

    def test_el_servicio_y_el_contenedor_llevan_el_nombre_nuevo(self):
        self.assertIn("\n  uhd-blu-ray-toolkit:\n", self.compose)
        self.assertIn("container_name: uhd-blu-ray-toolkit", self.compose)
        self.assertIn("image: ghcr.io/aldicarus/uhd-blu-ray-toolkit:latest", self.compose)


class TestNoQuedaNingunEnlaceAlRepoViejo(unittest.TestCase):
    """Un enlace olvidado no falla: apunta a donde ya no se publica nada. El
    aviso de actualizaciones de la app preguntaría a un repo sin releases
    nuevas, y el README mandaría a instalar la imagen de antes.

    Nombrar el repo y la imagen viejos solo se puede en la sección que explica
    la mudanza, que se reconoce porque su título lleva el nombre viejo."""

    #: CLAUDE.md cuenta la historia del proyecto, y `archive/` son specs viejas.
    FUERA = ("CLAUDE.md", "archive/")

    def _quedan(self, rel: str, texto: str) -> list:
        aguja = re.compile(r"aldicarus/" + re.escape(NOMBRE_VIEJO), re.IGNORECASE)
        quedan, en_la_mudanza = [], False
        for n, linea in enumerate(texto.splitlines(), 1):
            if rel.endswith(".md") and linea.startswith("#"):
                en_la_mudanza = NOMBRE_VIEJO in linea
            if aguja.search(linea) and not en_la_mudanza:
                quedan.append(f"{rel}:{n}")
        return quedan

    def test_ni_repo_ni_imagen(self):
        r = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True,
                           text=True, timeout=30)
        if r.returncode != 0:
            self.skipTest("git no disponible")
        quedan = []
        for rel in r.stdout.splitlines():
            if rel.startswith(self.FUERA) or rel.endswith((".png", ".jpg", ".ico")):
                continue
            try:
                texto = (RAIZ / rel).read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
                continue
            quedan += self._quedan(rel, texto)
        self.assertEqual(quedan, [])

    def test_la_excepcion_es_solo_la_seccion_de_la_mudanza(self):
        """El guard no puede pasar en verde por permitir de más: la sección
        siguiente vuelve a contar."""
        viejo = "ghcr.io/aldicarus/" + NOMBRE_VIEJO
        texto = (f"## Coming from {NOMBRE_VIEJO}\n{viejo}\n"
                 f"## Configuration\n{viejo}\n")
        self.assertEqual(self._quedan("README.md", texto), ["README.md:4"])
        self.assertEqual(self._quedan("app/main.py", f"# {NOMBRE_VIEJO}\n{viejo}\n"),
                         ["app/main.py:2"], "fuera del markdown no hay secciones")

    def test_el_aviso_de_actualizaciones_pregunta_al_repo_nuevo(self):
        src = (APP_DIR / "main.py").read_text(encoding="utf-8")
        self.assertIn('repo = "Aldicarus/uhd-blu-ray-toolkit"', src)


if __name__ == "__main__":
    unittest.main()
