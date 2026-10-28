"""La recomendación de un título que la hoja de DoviTools no tiene.

`_cmv40RenderRecommendation` compone la frase en dos piezas: «El título
**X** (2020)» en una plantilla y «no aparece en la hoja de DoviTools…» con
`tr()`, añadida con `html +=`. La segunda iba pegada a la primera, sin
espacio, así que el modal decía «(2020)no aparece» en las tres lenguas.
Lo vio una de las traducciones al alemán (2026-10-28), que tenía que encajar
su frase detrás de esa.

Ningún guard lo podía ver: `TestLosFragmentosSeCosenBien` busca dos `tr()`
pegados, y aquí lo que va delante es una plantilla. Se comprueba pintando la
recomendación en node y leyendo el texto que sale, con y sin el título de
TMDb, que son los dos sitios que acaban justo antes de la frase.

Ejecutar desde la raíz del repo:
    python3 -m unittest app.tests.test_recomendacion_sin_coincidencia -v
"""
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(APP_DIR / "tests"))

from frontend_sources import argv_node, catalogo_es, js_en_disco, pintar_en  # noqa: E402

NODE = shutil.which("node")

_DRIVER = r"""
const fs = require('fs'), vm = require('vm');
const nodo = () => ({style:{}, dataset:{}, classList:{toggle(){},add(){},remove(){},contains(){return false}},
  appendChild(){}, addEventListener(){}, setAttribute(){}, querySelectorAll: () => [],
  querySelector: () => null, innerHTML:'', textContent:'', className:''});
const banner = nodo();
global.window = global;
global.document = {getElementById: id => id === 'banner-test' ? banner : null,
  querySelectorAll: () => [], querySelector: () => null, createElement: nodo,
  addEventListener(){}, head: nodo(), body: nodo(), documentElement: nodo(),
  readyState: 'complete'};
global.localStorage = {getItem: () => null, setItem(){}};
global.fetch = () => new Promise(() => {});
global.__I18N = {idioma: 'es',
                 catalogo: JSON.parse(fs.readFileSync(process.env.CATALOGO, 'utf8'))};
vm.runInThisContext(fs.readFileSync(process.env.JS_CONCAT, 'utf8'));

let entrada = '';
process.stdin.on('data', d => entrada += d);
process.stdin.on('end', () => {
  const salida = JSON.parse(entrada).map(datos => {
    banner.innerHTML = '';
    _cmv40RenderRecommendation(datos, 'banner-test');
    return banner.innerHTML;
  });
  process.stdout.write(JSON.stringify(salida));
  process.exit(0);
});
"""

SIN_COINCIDENCIA = {"status": "unknown", "input_title": "Peli de prueba",
                    "input_year": 2020, "sheet_rows_loaded": 828,
                    "tmdb_configured": True}


def _texto(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


@unittest.skipIf(NODE is None, "node no está instalado")
class TestLaFraseNoVaPegada(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        casos = [SIN_COINCIDENCIA,
                 {**SIN_COINCIDENCIA, "title_en": "Test Movie"}]
        proc = subprocess.run(
            argv_node(_DRIVER),
            env={**os.environ, "JS_CONCAT": js_en_disco(),
                 "CATALOGO": str(APP_DIR / "static" / "i18n" / "es.json")},
            input=json.dumps(casos), capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-2000:])
        cls.sin_tmdb, cls.con_tmdb = pintar_en(json.loads(proc.stdout))
        # El principio de la frase, del catálogo: un cambio de redacción no
        # tiene que poner en rojo un test de comportamiento.
        frase = catalogo_es()["tab3.no_aparece_en_la_hoja_de"]
        cls.inicio = " ".join(frase.split()[:3])

    def test_se_pinto_la_rama_sin_coincidencia(self):
        """Sin la frase, el test no estaría mirando nada."""
        self.assertIn(self.inicio, _texto(self.sin_tmdb))
        self.assertIn("Peli de prueba", _texto(self.sin_tmdb))

    def test_detras_del_año_va_un_espacio(self):
        texto = re.sub(r"<[^>]+>", "", self.sin_tmdb)
        self.assertIn(f"(2020) {self.inicio}", " ".join(texto.split()))

    def test_detras_del_titulo_de_tmdb_tambien(self):
        texto = re.sub(r"<[^>]+>", "", self.con_tmdb)
        self.assertIn(f"(TMDb: Test Movie) {self.inicio}", " ".join(texto.split()))


if __name__ == "__main__":
    unittest.main()
