"""Las variables de entorno de la app, con su nombre de ahora y el de antes.

Hasta la v1.0 la app se publicaba como «hdo-iso-converter» y sus variables
empezaban por `HDO_`; desde entonces empiezan por `UBT_` (UHD Blu-ray
Toolkit). Las de antes se siguen leyendo para que el `.env` de quien venga
del nombre viejo funcione sin tocarlo: la mudanza tiene que ser transparente.

Si están las dos, manda la nueva. Una vacía cuenta como ausente, porque el
compose pasa siempre `UBT_X=${UBT_X:-${HDO_X:-}}`, y vacía es como llega la
que nadie ha puesto.
"""
import os

PREFIJO = "UBT_"
#: El de antes de la v1.0, que se sigue aceptando.
PREFIJO_ANTERIOR = "HDO_"


def variable(nombre: str, defecto: str = "") -> str:
    """`UBT_<nombre>`, o `HDO_<nombre>` si la nueva no está o está vacía."""
    return (os.environ.get(PREFIJO + nombre)
            or os.environ.get(PREFIJO_ANTERIOR + nombre)
            or defecto)
