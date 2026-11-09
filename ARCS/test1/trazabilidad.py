import json
import os
import threading


class TrazadorARCS:
    """Guarda una traza JSON por interacción sin intervenir en ARCS."""

    def __init__(self, ruta_archivo, max_bytes=5 * 1024 * 1024):
        self.ruta_archivo = ruta_archivo
        self.max_bytes = max_bytes  # Al alcanzar el límite, rota el archivo y crea uno nuevo.
        self._lock = threading.Lock()
        carpeta = os.path.dirname(ruta_archivo)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)

    def registrar(self, datos):
        """Agrega una línea JSON sin permitir que un fallo detenga ARCS."""
        try:
            linea = json.dumps(
                datos,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str
            )

            with self._lock:
                self._rotar_si_hace_falta()
                with open(self.ruta_archivo, "a", encoding="utf-8") as archivo:
                    archivo.write(linea + "\n")

            return True

        except Exception:
            # La observabilidad nunca debe tumbar el programa principal.
            return False

    def _rotar_si_hace_falta(self):
        """Guarda la traza anterior como .1 para limitar el crecimiento del archivo."""
        try:
            if os.path.exists(self.ruta_archivo) and os.path.getsize(self.ruta_archivo) >= self.max_bytes:
                os.replace(self.ruta_archivo, self.ruta_archivo + ".1")
        except Exception:
            pass
