"""El título dudoso: el diálogo de seguir, abandonar o elegir otra versión, y
el aviso del panel.

La Fase A deja en `bdinfo_result.avisos_titulo` lo que sabe del título
elegido y no puede resolver sola —un tráiler elegido por falta de algo mejor,
varias versiones de la película, playlists señuelo—. No corrige nada: lo
cuenta, y el usuario decide.

  · al terminar el análisis, un diálogo: **seguir** con el proyecto,
    **abandonarlo**, que lo borra, o —si el disco trae varias versiones de
    la película— **elegir otra**, que rehace el análisis en el mismo
    proyecto (`POST /api/sessions/{id}/version`);
  · en el panel del proyecto, un aviso fijo, porque el diálogo solo sale una
    vez y el proyecto puede ejecutarse días después, con el botón «Cambiar
    de versión», que abre el mismo diálogo con «Cancelar».

Los avisos viajan como DATOS y las frases las escribe el frontend, así que se
mira en las tres lenguas: una clave cruda o un `{hueco}` sin rellenar es lo
que se colaría.

Ejecutar desde la raíz del repo:
    python3 -m unittest app.tests.test_titulo_dudoso_en_pantalla -v
"""
import html as _html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR / "tests"))

from frontend_sources import html, semilla_catalogo  # noqa: E402

_CHROME_CANDIDATOS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]
CHROME = next((c for c in _CHROME_CANDIDATOS if c and Path(c).exists()), None)

# Los tres tipos, con la forma que escribe `phase_a._avisos_del_titulo`.
AVISOS = [
    {"tipo": "titulo_menor", "mpls": "00018.mpls", "segundos_titulo": 595,
     "ref": "00000.mpls", "segundos_ref": 8340},
    {"tipo": "varias_versiones", "mpls": "00018.mpls", "segundos": 595,
     "otras": [{"mpls": "00801.mpls", "segundos": 9240}], "mas": 0},
    {"tipo": "playlists_ofuscados", "mpls": "00018.mpls", "n": 37},
]

# Una sesión de Tab 1 con lo que `openProject` y el panel leen. En inglés,
# como las fixtures de `test_las_tres_lenguas_en_pantalla`: así cualquier
# castellano en la pantalla inglesa viene de la app y no del dato.
SESION = {
    "id": "s2", "mkv_name": "Divergent (2014).mkv", "status": "pending",
    "media_type": "movie", "source_type": "iso", "iso_path": "Divergent.iso",
    "source_path": "Divergent.iso", "included_tracks": [],
    "discarded_tracks": [], "chapters": [], "execution_history": [],
    "updated_at": "2026-10-15T08:00:00Z",
    "bdinfo_result": {"main_mpls": "00018.mpls", "duration_seconds": 594.7,
                      "video_tracks": [], "audio_tracks": [],
                      "subtitle_tracks": [], "avisos_titulo": AVISOS},
}

PALABRA_DE_CADA_LENGUA = {"es": "película", "en": "film", "ca": "pel·lícula", "de": "Film"}

_CUERPO = """
<pre id="__out"></pre>
<script>
(async function () {
  await new Promise(r => setTimeout(r, 700));
  const AV = %s;
  const SES = %s;
  const out = {errores: window.__errores};
  const modal = document.getElementById('titulo-dudoso-modal');
  try {
    out.frases = frasesDeAvisosDelTitulo(AV);
    out.desconocido = frasesDeAvisosDelTitulo([{tipo: 'de_una_version_futura'}]);

    const visible = id => document.getElementById(id).style.display !== 'none';
    const tarjetas = () => [...modal.querySelectorAll('.titulo-version')].map(t => ({
      mpls: t.dataset.mpls, marcada: t.classList.contains('selected'), texto: t.innerText}));

    // ── El diálogo, en sus salidas.
    const p1 = preguntarPorElTitulo(SES);
    pintarTextos(modal);
    out.dialogo = {abierto: modal.classList.contains('open'),
                   texto: modal.innerText,
                   items: [...modal.querySelectorAll('li')].map(li => li.textContent),
                   tarjetas: tarjetas(),
                   notas: visible('titulo-dudoso-notas'),
                   boton: document.getElementById('titulo-dudoso-seguir').textContent,
                   cancelar: visible('titulo-dudoso-cancelar')};
    document.getElementById('titulo-dudoso-abandonar').click();
    out.abandonar = await p1;
    out.cerrado_tras_responder = !modal.classList.contains('open');
    const p2 = preguntarPorElTitulo(SES);
    document.getElementById('titulo-dudoso-seguir').click();
    out.seguir = await p2;

    // ── Elegir la otra versión.
    const p3 = preguntarPorElTitulo(SES);
    modal.querySelector('.titulo-version[data-mpls="00801.mpls"]').click();
    out.otra = {tarjetas: tarjetas(), notas: visible('titulo-dudoso-notas'),
                texto_notas: document.getElementById('titulo-dudoso-notas').textContent,
                boton: document.getElementById('titulo-dudoso-seguir').textContent};
    document.getElementById('titulo-dudoso-seguir').click();
    out.cambiar = await p3;

    // ── Con un rip terminado, la nota avisa de que el MKV se conserva.
    const conRip = Object.assign({}, SES, {execution_history: [
      {status: 'done', output_mkv_path: '/mnt/output/Divergent (2014).mkv'}]});
    const p4 = preguntarPorElTitulo(conRip);
    modal.querySelector('.titulo-version[data-mpls="00801.mpls"]').click();
    out.nota_con_rip = document.getElementById('titulo-dudoso-notas').textContent;
    document.getElementById('titulo-dudoso-abandonar').click();
    await p4;

    // ── El modo del botón del panel: «Cancelar» en vez de «Abandonar».
    const p5 = preguntarPorElTitulo(SES, 'cambiar');
    out.modo_cambiar = {abandonar: visible('titulo-dudoso-abandonar'),
                        cancelar: visible('titulo-dudoso-cancelar'),
                        sin_cambio_deshabilitado: document.getElementById('titulo-dudoso-seguir').disabled,
                        titulo: document.getElementById('titulo-dudoso-titulo').textContent};
    document.getElementById('titulo-dudoso-cancelar').click();
    out.cancelar = await p5;

    // ── El aviso fijo del panel.
    openProjects.push({id: 'p1', sessionId: 'otra', session: SES, name: SES.mkv_name});
    createProjectPanel({id: 'p1'});
    switchSubTab('p1');
    renderAvisosDelTitulo(SES);
    const ban = document.getElementById('p1-titulo-aviso-banner');
    pintarTextos(ban);
    const btnVersion = document.getElementById('p1-titulo-version-btn');
    out.banner = {visible: ban.style.display !== 'none', texto: ban.innerText,
                  boton: btnVersion.style.display !== 'none'};
    renderAvisosDelTitulo(Object.assign({}, SES, {status: 'queued'}));
    out.boton_en_cola = btnVersion.style.display;
    renderAvisosDelTitulo({bdinfo_result: {avisos_titulo: []}});
    out.banner_sin_avisos = ban.style.display;
    out.boton_sin_avisos = btnVersion.style.display;

    // ── El flujo entero: analizar y responder.
    const flujo = async (boton, {otra = false, versionFalla = false} = {}) => {
      const llamadas = [];
      window.apiFetch = async (url, opts) => {
        llamadas.push([(opts && opts.method) || 'GET', url, (opts && opts.body) || '']);
        if (url === '/api/analyze') return JSON.parse(JSON.stringify(SES));
        if (url === '/api/sessions') return {sessions: []};
        if (url.endsWith('/version')) return versionFalla ? null : JSON.parse(JSON.stringify(SES));
        return {};
      };
      const en_curso = _doAnalyzeSource('iso', 'Divergent.iso', 'Divergent.iso', {});
      for (let i = 0; i < 60 && !modal.classList.contains('open'); i++)
        await new Promise(r => setTimeout(r, 100));
      const abierto = modal.classList.contains('open');
      if (otra) modal.querySelector('.titulo-version[data-mpls="00801.mpls"]').click();
      document.getElementById(boton).click();
      await en_curso;
      return {abierto, llamadas};
    };
    out.flujo_abandonar = await flujo('titulo-dudoso-abandonar');
    out.flujo_seguir = await flujo('titulo-dudoso-seguir');
    out.flujo_otra = await flujo('titulo-dudoso-seguir', {otra: true});
    out.flujo_otra_falla = await flujo('titulo-dudoso-seguir', {otra: true, versionFalla: true});

    // ── «Cambiar de versión» desde el panel, de punta a punta: el botón
    // abre el diálogo, se elige la otra y sale el POST.
    {
      const llamadas = [];
      window.apiFetch = async (url, opts) => {
        llamadas.push([(opts && opts.method) || 'GET', url, (opts && opts.body) || '']);
        if (url.endsWith('/version')) return JSON.parse(JSON.stringify(SES));
        if (url === '/api/sessions') return {sessions: []};
        return {};
      };
      const en_curso = cambiarDeVersion('otra');
      for (let i = 0; i < 60 && !modal.classList.contains('open'); i++)
        await new Promise(r => setTimeout(r, 100));
      out.panel_abierto = modal.classList.contains('open');
      out.panel_abandonar = document.getElementById('titulo-dudoso-abandonar').style.display;
      modal.querySelector('.titulo-version[data-mpls="00801.mpls"]').click();
      document.getElementById('titulo-dudoso-seguir').click();
      await en_curso;
      out.panel_llamadas = llamadas;
    }
  } catch (e) { out.error = String(e && e.stack || e); }
  document.getElementById('__out').textContent = JSON.stringify(out);
})();
</script>
"""


def _medir(idioma: str) -> dict:
    sonda = ("<style>*{transition:none!important;animation:none!important}</style>"
             "<script>window.__errores=[];"
             "window.addEventListener('error',e=>window.__errores.push("
             "(e.message||'')+' @ '+(e.filename||'').split('/').pop()));</script>")
    pagina = html().replace("</head>", sonda + semilla_catalogo(idioma) + "</head>")
    pagina = pagina.replace("</body>", _CUERPO % (
        json.dumps(AVISOS), json.dumps(SESION)) + "</body>")
    pagina = (pagina.replace('src="/static/', 'src="')
                    .replace('href="/static/', 'href="'))
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                      encoding="utf-8",
                                      dir=str(APP_DIR / "static"))
    tmp.write(pagina)
    tmp.close()
    try:
        dom = subprocess.run(
            [CHROME, "--headless", "--disable-gpu",
             "--allow-file-access-from-files", "--dump-dom",
             "--window-size=1600,1000", "--virtual-time-budget=30000", tmp.name],
            capture_output=True, text=True, timeout=180).stdout
    finally:
        os.unlink(tmp.name)
    m = re.search(r'<pre id="__out">(.*?)</pre>', dom, re.S)
    if not m:
        raise unittest.SkipTest("Chrome no devolvió el volcado")
    return json.loads(_html.unescape(m.group(1)))


@unittest.skipUnless(CHROME, "Chrome/Chromium no disponible")
class TestElTituloDudoso(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.m = {idioma: _medir(idioma) for idioma in ("es", "en", "ca", "de")}

    def test_sin_errores(self):
        for idioma, m in self.m.items():
            with self.subTest(idioma=idioma):
                self.assertNotIn("error", m, m.get("error"))
                self.assertEqual(m["errores"], [])

    def test_una_frase_por_aviso_en_cada_lengua(self):
        for idioma, m in self.m.items():
            with self.subTest(idioma=idioma):
                self.assertEqual(len(m["frases"]), 3)
                texto = " ".join(m["frases"])
                for crudo in ("tab1.", "{", "}"):
                    self.assertNotIn(crudo, texto)
                for dato in ("00000.mpls", "00801.mpls", "37"):
                    self.assertIn(dato, texto)

    def test_un_tipo_desconocido_no_se_pinta(self):
        """Un aviso de una versión más nueva del servidor no puede salir
        como su id."""
        for idioma, m in self.m.items():
            with self.subTest(idioma=idioma):
                self.assertEqual(m["desconocido"], [])

    def test_el_dialogo_lista_los_avisos_en_su_lengua(self):
        """Los avisos que no son de versión, como frases; el de las versiones
        no se repite: lo dicen las tarjetas, que además dejan elegir."""
        for idioma, m in self.m.items():
            with self.subTest(idioma=idioma):
                d = m["dialogo"]
                self.assertTrue(d["abierto"])
                self.assertEqual(d["items"], [m["frases"][0], m["frases"][2]])
                self.assertIn("00018.mpls", d["texto"])
                self.assertIn(PALABRA_DE_CADA_LENGUA[idioma], d["texto"])
                self.assertNotIn("tab1.", d["texto"])
                for crudo in ("{", "}"):
                    self.assertNotIn(crudo, d["texto"])

    def test_una_tarjeta_por_version_con_la_de_ahora_marcada(self):
        for idioma, m in self.m.items():
            with self.subTest(idioma=idioma):
                t = m["dialogo"]["tarjetas"]
                self.assertEqual([x["mpls"] for x in t], ["00018.mpls", "00801.mpls"])
                self.assertEqual([x["marcada"] for x in t], [True, False])
                self.assertIn("144", t[1]["texto"], "los minutos de diferencia")
                self.assertFalse(m["dialogo"]["notas"], "sin cambiar no hay nada que avisar")
                self.assertFalse(m["dialogo"]["cancelar"])

    def test_elegir_otra_version(self):
        for idioma, m in self.m.items():
            with self.subTest(idioma=idioma):
                o = m["otra"]
                self.assertEqual([x["marcada"] for x in o["tarjetas"]], [False, True])
                self.assertTrue(o["notas"], "las consecuencias de cambiar")
                self.assertNotEqual(o["boton"], m["dialogo"]["boton"])
                self.assertEqual(m["cambiar"], {"accion": "cambiar", "mpls": "00801.mpls"})
                self.assertIn("Divergent (2014).mkv", m["nota_con_rip"])
                self.assertNotIn("Divergent (2014).mkv", o["texto_notas"])

    def test_el_modo_del_boton_del_panel(self):
        for idioma, m in self.m.items():
            with self.subTest(idioma=idioma):
                c = m["modo_cambiar"]
                self.assertFalse(c["abandonar"], "desde el panel no se abandona")
                self.assertTrue(c["cancelar"])
                self.assertTrue(c["sin_cambio_deshabilitado"])
                self.assertNotIn("tab1.", c["titulo"])
                self.assertEqual(m["cancelar"]["accion"], "cancelar")

    def test_las_dos_salidas(self):
        for idioma, m in self.m.items():
            with self.subTest(idioma=idioma):
                self.assertEqual(m["abandonar"]["accion"], "abandonar")
                self.assertEqual(m["seguir"]["accion"], "seguir")
                self.assertTrue(m["cerrado_tras_responder"])

    def test_el_aviso_del_panel(self):
        for idioma, m in self.m.items():
            with self.subTest(idioma=idioma):
                self.assertTrue(m["banner"]["visible"])
                for frase in m["frases"]:
                    self.assertIn(frase, m["banner"]["texto"])
                self.assertTrue(m["banner"]["boton"], "«Cambiar de versión»")
                self.assertEqual(m["boton_en_cola"], "none")
                self.assertEqual(m["banner_sin_avisos"], "none")
                self.assertEqual(m["boton_sin_avisos"], "none")

    def test_abandonar_borra_el_proyecto_recien_analizado(self):
        f = self.m["es"]["flujo_abandonar"]
        self.assertTrue(f["abierto"], f)
        self.assertIn(["DELETE", "/api/sessions/s2"], [l[:2] for l in f["llamadas"]])

    def test_seguir_no_borra_nada(self):
        f = self.m["es"]["flujo_seguir"]
        self.assertTrue(f["abierto"], f)
        self.assertNotIn("DELETE", [metodo for metodo, *_ in f["llamadas"]])
        self.assertFalse([u for _, u, _ in f["llamadas"] if u.endswith("/version")])

    def test_otra_version_rehace_el_analisis_del_mismo_proyecto(self):
        f = self.m["es"]["flujo_otra"]
        self.assertIn(["POST", "/api/sessions/s2/version", '{"mpls":"00801.mpls"}'],
                      f["llamadas"])
        self.assertNotIn("DELETE", [metodo for metodo, *_ in f["llamadas"]])

    def test_el_boton_del_panel_cambia_la_version(self):
        m = self.m["es"]
        self.assertTrue(m["panel_abierto"])
        self.assertEqual(m["panel_abandonar"], "none")
        self.assertIn(["POST", "/api/sessions/s2/version", '{"mpls":"00801.mpls"}'],
                      m["panel_llamadas"])
        self.assertNotIn("DELETE", [metodo for metodo, *_ in m["panel_llamadas"]])

    def test_si_el_cambio_falla_no_se_borra_el_proyecto(self):
        """Un 400/409 o un fallo de red al cambiar de versión no es
        «abandonar» (pregunta abierta de Codex sobre el plan)."""
        f = self.m["es"]["flujo_otra_falla"]
        self.assertIn("POST", [metodo for metodo, u, _ in f["llamadas"] if u.endswith("/version")])
        self.assertNotIn("DELETE", [metodo for metodo, *_ in f["llamadas"]])


if __name__ == "__main__":
    unittest.main()
