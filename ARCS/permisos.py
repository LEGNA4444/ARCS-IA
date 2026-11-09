# -*- coding: utf-8 -*-
"""
permisos.py - Permisos de cada cuenta de ARCS y su archivo permisos.json.

Cada cuenta guarda sus permisos dentro de su carpeta:
  usuarios/<nombre>_<id>/permisos.json
Se cambian con comandos desde ARCS (/permiso ...). Las cuentas creadas antes de
este registro se marcan como "legacy" y conservan el comportamiento anterior.
"""
import datetime
import json
import os

VERSION_TERMINOS = "borrador-1"   # Cambiar cuando los términos oficiales estén revisados
ARCHIVO_PERMISOS = "permisos.json"
EDAD_MINIMA = 18

PERMISOS = {
    "aprender_mensajes": {
        "descripcion": "ARCS aprende de lo que escribes para poder responder. Sin esto no hay cuenta.",
        "requerido": True, "default": True},
    "guardar_personas": {
        "descripcion": "ARCS guarda en tu carpeta los datos que cuentas sobre personas.",
        "requerido": False, "default": False},
    "consultar_datos_publicos": {
        "descripcion": "Puedes consultar los datos que el creador de ARCS decidió hacer públicos.",
        "requerido": False, "default": True},
    "guardar_trazas": {
        "descripcion": "ARCS guarda registros técnicos de tus conversaciones para depuración.",
        "requerido": False, "default": False},
}


def permisos_por_defecto():
    return {k: v["default"] for k, v in PERMISOS.items()}


def validar_aceptacion(aceptacion):
    """
    aceptacion = {"edad_confirmada": true, "permisos": {"guardar_personas": true, ...}}
    Devuelve (ok, error, permisos_normalizados).
    """
    if not isinstance(aceptacion, dict):
        return False, "Faltan los datos de aceptación.", None
    if aceptacion.get("edad_confirmada") is not True:
        return False, f"Debes confirmar que tienes {EDAD_MINIMA} años o más.", None
    entrada = aceptacion.get("permisos")
    if not isinstance(entrada, dict):
        return False, "Faltan las respuestas de permisos.", None
    permisos = {}
    for clave, cfg in PERMISOS.items():
        valor = entrada.get(clave, False)
        if not isinstance(valor, bool):
            return False, f"Respuesta inválida para {clave}.", None
        if cfg["requerido"] and valor is not True:
            return False, f"Necesitas aceptar '{clave}' para usar ARCS.", None
        permisos[clave] = valor
    return True, None, permisos


def _escribir_json(ruta, datos):
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, ruta)


def escribir_permisos(carpeta, datos):
    _escribir_json(os.path.join(carpeta, ARCHIVO_PERMISOS), datos)


def leer_permisos(carpeta):
    """Devuelve {"legacy": bool, "permisos": {...}, ...}. Si falta el archivo, es una cuenta anterior."""
    ruta = os.path.join(carpeta, ARCHIVO_PERMISOS)
    if not os.path.exists(ruta):
        legado = permisos_por_defecto()
        legado["guardar_personas"] = True   # lo que ya hacia ARCS para cuentas anteriores
        legado["guardar_trazas"] = True
        return {"legacy": True, "permisos": legado}
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        if isinstance(datos, dict) and isinstance(datos.get("permisos"), dict):
            base = permisos_por_defecto()
            base.update({k: v for k, v in datos["permisos"].items() if k in PERMISOS and isinstance(v, bool)})
            base["aprender_mensajes"] = True   # requerido: no se puede quitar
            datos["permisos"] = base
            return datos
    except (OSError, ValueError):
        pass
    return {"legacy": False, "error_lectura": True, "permisos": permisos_por_defecto()}


def cambiar_permiso(carpeta, nombre, valor):
    """Devuelve (ok, mensaje). Guarda en permisos.json."""
    if nombre not in PERMISOS:
        return False, f"No existe el permiso '{nombre}'. Usa /permisos para ver la lista."
    if PERMISOS[nombre]["requerido"] and not valor:
        return False, f"'{nombre}' es necesario para usar ARCS; no se puede desactivar."
    datos = leer_permisos(carpeta)
    datos["permisos"][nombre] = valor
    datos["legacy"] = False
    datos["actualizado_en"] = datetime.datetime.now().isoformat(timespec="seconds")
    escribir_permisos(carpeta, datos)
    estado = "activado" if valor else "desactivado"
    return True, f"Permiso '{nombre}' {estado}."
