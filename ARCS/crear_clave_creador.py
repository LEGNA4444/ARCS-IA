"""Crea o cambia la clave del creador. Uso: python crear_clave_creador.py [carpeta_de_arcs]."""
import getpass
import os
import sys
from seguridad import hash_clave

carpeta = sys.argv[1] if len(sys.argv) > 1 else "/storage/emulated/0/ARCS/test1/"
ruta = os.path.join(carpeta, "clave_creador.txt")
c1 = getpass.getpass("Nueva clave (mínimo 8 caracteres): ")
c2 = getpass.getpass("Repite la clave: ")
if c1 != c2:
    sys.exit("Las claves no coinciden.")
if len(c1) < 8:
    sys.exit("La clave debe tener al menos 8 caracteres.")
os.makedirs(carpeta, exist_ok=True)
with open(ruta, "w", encoding="utf-8") as f:
    f.write(hash_clave(c1) + "\n")
print(f"Clave guardada en {ruta}")
