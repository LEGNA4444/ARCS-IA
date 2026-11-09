# -*- coding: utf-8 -*-
"""
servidor_web.py - Registro local de ARCS (Flask, solo 127.0.0.1).

ARCS lo arranca al iniciar. Sirve la pagina de registro (web/templates/index.html)
y dos endpoints para crear y borrar cuentas.

Seguridad:
  - Solo acepta peticiones cuyo Host sea localhost o 127.0.0.1 (evita ataques de DNS rebinding).
  - Las escrituras exigen el header X-ARCS-Token. El token se genera al iniciar y solo
    se entrega dentro de la pagina local (/), asi un sitio externo no puede leerlo.
"""
import os
import re
import secrets
import threading

import cuentas
from permisos import PERMISOS, VERSION_TERMINOS, EDAD_MINIMA, validar_aceptacion

HOST = "127.0.0.1"
PUERTOS = (8765, 8766, 8767, 8768, 8769)
HOSTS_PERMITIDOS = {"127.0.0.1", "localhost"}
NOMBRES_RESERVADOS = {"legnar", "invitado", "anonimo"}
_RE_NOMBRE = re.compile(r"^[a-z0-9_-]{2,32}$")

# BORRADOR: estos textos deben ser revisados por un abogado antes de publicar ARCS.
TERMINOS = [
    "ARCS es una inteligencia artificial estadística en pruebas. No es un modelo de lenguaje y no tiene conocimiento ni experiencias propias.",
    "Para crear tu cuenta, ARCS guarda una carpeta con tu nombre de usuario, tus permisos y lo que aprende de tus mensajes.",
    "Si activas 'guardar_personas', ARCS guarda en tu carpeta los datos que cuentas sobre otras personas. Antes de guardar datos de terceros, asegúrate de tener su permiso.",
    "Lo que el creador de ARCS decide hacer público puede ser consultado por todos los usuarios, si tienes activo 'consultar_datos_publicos'.",
    "Por ahora ARCS no está diseñado para datos sensibles (salud, creencias, finanzas, orientación sexual, datos biométricos). No los escribas.",
    "Puedes cambiar tus permisos en cualquier momento con /permiso, ver tus datos con /personas y borrar tu cuenta desde esta página.",
]


def _error(mensaje, codigo):
    from flask import jsonify
    return jsonify({"ok": False, "error": mensaje}), codigo


def crear_app(ruta_base):
    from flask import Flask, jsonify, render_template, request

    base = os.path.dirname(os.path.abspath(__file__))
    app = Flask(__name__,
                template_folder=os.path.join(base, "web", "templates"),
                static_folder=os.path.join(base, "web", "static"))
    token = secrets.token_urlsafe(32)
    cerrojo = threading.Lock()

    @app.before_request
    def solo_local():
        host = request.host.split(":")[0].lower()
        if host not in HOSTS_PERMITIDOS:
            return _error("Acceso no permitido.", 403)
        return None

    def token_valido():
        return secrets.compare_digest(request.headers.get("X-ARCS-Token", ""), token)

    @app.get("/")
    def inicio():
        return render_template("index.html", token=token, version=VERSION_TERMINOS)

    @app.get("/api/terminos")
    def terminos():
        return jsonify({
            "version": VERSION_TERMINOS,
            "edad_minima": EDAD_MINIMA,
            "parrafos": TERMINOS,
            "permisos": [{"id": k, "descripcion": v["descripcion"], "requerido": v["requerido"],
                          "por_defecto": v["default"]} for k, v in PERMISOS.items()],
        })

    @app.post("/api/cuenta")
    def crear():
        if not token_valido():
            return _error("Token inválido.", 403)
        datos = request.get_json(silent=True) or {}
        nombre = str(datos.get("nombre", "")).strip().lower()
        if not _RE_NOMBRE.match(nombre):
            return _error("El nombre debe tener de 2 a 32 letras minúsculas, números, _ o -.", 400)
        if nombre in NOMBRES_RESERVADOS:
            return _error("Ese nombre está reservado.", 400)
        ok, error, permisos = validar_aceptacion(datos.get("aceptacion"))
        if not ok:
            return _error(error, 400)
        with cerrojo:
            try:
                cuentas.crear_cuenta(ruta_base, nombre, permisos, VERSION_TERMINOS)
            except cuentas.CuentaExiste:
                return _error("Ya existe una cuenta con ese nombre.", 409)
        return jsonify({"ok": True, "cuenta": nombre, "permisos": permisos}), 201

    @app.delete("/api/cuenta/<nombre>")
    def borrar(nombre):
        if not token_valido():
            return _error("Token inválido.", 403)
        nombre = nombre.strip().lower()
        if nombre in NOMBRES_RESERVADOS:
            return _error("Esa cuenta no se puede borrar desde aquí.", 400)
        datos = request.get_json(silent=True) or {}
        if datos.get("confirmar") != "BORRAR":
            return _error('Para confirmar envía {"confirmar": "BORRAR"}.', 400)
        with cerrojo:
            if not cuentas.borrar_cuenta(ruta_base, nombre):
                return _error("No existe esa cuenta.", 404)
        return jsonify({"ok": True, "borrada": nombre})

    return app


class ServidorRegistro:
    def __init__(self, servidor, puerto):
        self._servidor = servidor
        self.puerto = puerto
        self.url = f"http://{HOST}:{puerto}/"
        self._hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        self._hilo.start()

    def apagar(self):
        self._servidor.shutdown()
        self._servidor.server_close()


def iniciar_registro_web(ruta_base):
    """Arranca el registro local. Si Flask no esta instalado o los puertos estan ocupados, ARCS sigue sin el."""
    try:
        from werkzeug.serving import make_server
        app = crear_app(ruta_base)
    except ImportError:
        print("[sys]: Flask no está instalado; el registro web está desactivado (pip install flask).")
        return None
    for puerto in PUERTOS:
        try:
            servidor = make_server(HOST, puerto, app, threaded=True)
        except OSError:
            continue
        registro = ServidorRegistro(servidor, puerto)
        print(f"[sys]: Registro de cuentas en {registro.url}")
        return registro
    print("[sys]: No hay puertos libres para el registro web.")
    return None
