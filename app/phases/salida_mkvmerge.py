"""La salida de ``mkvmerge --gui-mode``, como se escribe sin él.

Con ``--gui-mode`` mkvmerge marca con ``#GUI#`` sus líneas de control —el
progreso (``#GUI#progress 45%``), el escaneo de los playlists…— y también sus
ERRORES y AVISOS: ``#GUI#error …`` y ``#GUI#warning …`` en vez de ``Error:`` y
``Warning:``. Los cuatro sitios que lo leen descartaban toda línea ``#GUI#``
que no fuera de progreso, así que un mkvmerge que fallaba dejaba en el log
«código 2» sin el motivo, y los avisos no salían nunca. Caso real (octubre de
2026): Hobbs & Shaw, un playlist de dos m2ts que fallaba antes de abrir la
salida, sin una línea que dijera por qué.
"""

from __future__ import annotations

_PROGRESO = "#GUI#progress "
_ERROR = "#GUI#error "
_AVISO = "#GUI#warning "


def traducir(linea: str) -> str | None:
    """La línea como la escribiría mkvmerge sin ``--gui-mode``, o ``None`` si
    es una línea de control que no se enseña.

    ``#GUI#progress 45%`` pasa a ``Progress: 45%``, que es el contrato del
    parser del panel de cola de Tab 1; ``#GUI#error X`` a ``Error: X`` y
    ``#GUI#warning X`` a ``Warning: X``, el prefijo que mkvmerge usa sin el
    modo GUI. Lo que no lleva ``#GUI#`` sale tal cual.
    """
    if linea.startswith(_PROGRESO):
        return "Progress: " + linea.removeprefix(_PROGRESO)
    if linea.startswith(_ERROR):
        return "Error: " + linea.removeprefix(_ERROR)
    if linea.startswith(_AVISO):
        return "Warning: " + linea.removeprefix(_AVISO)
    if linea.startswith("#GUI#"):
        return None
    return linea


def error_de(linea: str) -> str | None:
    """El texto de un error de mkvmerge, o ``None`` si la línea no lo es."""
    if linea.startswith(_ERROR):
        return linea.removeprefix(_ERROR).strip() or None
    return None
