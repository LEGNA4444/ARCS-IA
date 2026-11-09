import hashlib
import hmac
import os

ITERACIONES_CLAVE = 200000  # PBKDF2 dificulta los intentos de fuerza bruta.


def hash_clave(clave, salt=None):
    """Devuelve 'salt_hex:hash_hex'. Nunca guarda la clave en texto."""
    salt = salt or os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), salt, ITERACIONES_CLAVE)
    return salt.hex() + ":" + h.hex()


def verificar_clave(clave, guardado):
    try:
        salt_hex, hash_guardado = guardado.strip().split(":")
        calculado = hash_clave(clave, bytes.fromhex(salt_hex)).split(":")[1]
        return hmac.compare_digest(calculado, hash_guardado)
    except Exception:
        return False
