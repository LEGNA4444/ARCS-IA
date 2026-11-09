# -*- coding: utf-8 -*-
"""
cuentas.py - Crear, buscar y borrar cuentas (carpetas de usuario) de ARCS.

Formato compatible con ARCS: usuarios/<nombre>_<id>/.arcs_usuario.json
"""
import datetime
import json
import os
import re
import shutil
import uuid

from permisos import ARCHIVO_PERMISOS, escribir_permisos

CARPETA_USUARIOS = "usuarios"
ARCHIVO_IDENTIDAD = ".arcs_usuario.json"


class CuentaExiste(Exception):
    pass


def _slug(nombre):
    return re.sub(r"[^a-z0-9_-]", "_", nombre.lower().strip())[:32] or "anonimo"


def _leer_identidad(carpeta):
    try:
        with open(os.path.join(carpeta, ARCHIVO_IDENTIDAD), "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


def buscar_cuenta(ruta_base, nombre):
    """Devuelve la carpeta de la cuenta con ese nombre, o None."""
    base = os.path.join(ruta_base, CARPETA_USUARIOS)
    if not os.path.isdir(base):
        return None
    for entrada in os.scandir(base):
        if not entrada.is_dir():
            continue
        ident = _leer_identidad(entrada.path)
        if ident and ident.get("usuario") == nombre and ident.get("id"):
            return entrada.path
    return None


def _carpeta_legacy(ruta_base, nombre):
    ruta = os.path.join(ruta_base, CARPETA_USUARIOS, _slug(nombre))
    return ruta if os.path.isdir(ruta) else None


def cuenta_existe(ruta_base, nombre):
    """True si hay cuenta nueva o una carpeta anterior al registro con ese nombre."""
    return buscar_cuenta(ruta_base, nombre) is not None or _carpeta_legacy(ruta_base, nombre) is not None


def crear_cuenta(ruta_base, nombre, permisos, version_terminos):
    if cuenta_existe(ruta_base, nombre):
        raise CuentaExiste(nombre)
    base = os.path.join(ruta_base, CARPETA_USUARIOS)
    os.makedirs(base, exist_ok=True)
    ident = uuid.uuid4().hex
    carpeta = os.path.join(base, f"{_slug(nombre)}_{ident}")
    os.mkdir(carpeta)
    tmp = os.path.join(carpeta, ARCHIVO_IDENTIDAD + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"usuario": nombre, "id": ident}, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(carpeta, ARCHIVO_IDENTIDAD))
    escribir_permisos(carpeta, {
        "legacy": False,
        "version_terminos": version_terminos,
        "aceptado_en": datetime.datetime.now().isoformat(timespec="seconds"),
        "permisos": permisos,
    })
    return carpeta


def borrar_cuenta(ruta_base, nombre):
    """Borra la carpeta completa de la cuenta (incluye sus fichas de personas). True si borró algo."""
    carpeta = buscar_cuenta(ruta_base, nombre) or _carpeta_legacy(ruta_base, nombre)
    if not carpeta:
        return False
    shutil.rmtree(carpeta)
    return True
