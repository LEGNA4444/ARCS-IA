
# este archivo es un ejemplo de una función futura 
import os
import json
import math
import shutil
import tempfile
import uuid

from time import strftime
from collections import OrderedDict


PESOS = "arcs_pesos.txt"
CORE = "arcs_v2_core.txt"
DICC = "arcs_v2_dict.txt"

# Idea central: cada rama se compara SIEMPRE contra la misma base
# (el ancestro común). Solo cuenta lo que la rama cambió, así el
# resultado crece de forma lineal y nada se cuenta dos veces.
# Todos los pesos se fuerzan a enteros hacia arriba con math.ceil.


# --------------------------------------------------
# RUTAS
# --------------------------------------------------

def archivo_hermano(ruta_pesos, nombre):
    carpeta = os.path.dirname(os.path.abspath(ruta_pesos))
    return os.path.join(carpeta, nombre)


def registrar_error(informe, archivo, linea, contenido, mensaje):
    informe["lineas_invalidas"].append({
        "archivo": archivo,
        "linea": linea,
        "contenido": contenido,
        "motivo": mensaje
    })


def validar_salida(rutas_origen, carpeta_salida):
    salida = os.path.realpath(os.path.abspath(carpeta_salida))

    for ruta in rutas_origen:
        origen = os.path.realpath(
            os.path.dirname(os.path.abspath(ruta))
        )

        try:
            comun = os.path.commonpath([salida, origen])
        except ValueError:
            comun = None

        if comun == salida or comun == origen:
            raise ValueError(
                "La carpeta de salida se cruza con una carpeta "
                "de origen:\n" + salida + "\n" + origen
            )

    return salida


# --------------------------------------------------
# LECTURA
# --------------------------------------------------

def leer_lineas(ruta, separador, tipo, informe, etiqueta,
                estricto=False):
    """Devuelve OrderedDict, o None si el archivo no existe
    (y no es modo estricto). None = esa rama no aporta datos."""

    datos = OrderedDict()

    if not os.path.isfile(ruta):
        informe["archivos_faltantes"].append({
            "archivo": ruta,
            "origen": etiqueta
        })

        if estricto:
            raise FileNotFoundError(
                f"Falta archivo requerido: {ruta}"
            )

        return None

    # utf-8-sig tolera archivos con BOM (Bloc de notas de Windows).
    with open(ruta, "r", encoding="utf-8-sig") as f:

        for numero, original in enumerate(f, 1):

            linea = original.strip()

            if not linea or linea.startswith("#"):
                continue

            if separador not in linea:
                registrar_error(informe, etiqueta, numero,
                                original.rstrip("\r\n"),
                                "Separador ausente")
                if estricto:
                    raise ValueError(
                        f"Línea inválida: {etiqueta}:{numero}")
                continue

            clave, valor = linea.split(separador, 1)
            clave = clave.strip()
            valor = valor.strip()

            if not clave:
                registrar_error(informe, etiqueta, numero,
                                original.rstrip("\r\n"),
                                "Clave vacía")
                if estricto:
                    raise ValueError(
                        f"Clave vacía: {etiqueta}:{numero}")
                continue

            if tipo == "pesos":

                try:
                    valor = float(valor)
                except ValueError:
                    registrar_error(informe, etiqueta, numero,
                                    original.rstrip("\r\n"),
                                    "Peso no numérico")
                    if estricto:
                        raise ValueError(
                            f"Peso inválido: {etiqueta}:{numero}")
                    continue

                if not math.isfinite(valor):
                    registrar_error(informe, etiqueta, numero,
                                    original.rstrip("\r\n"),
                                    "Peso infinito o NaN")
                    if estricto:
                        raise ValueError(
                            f"Peso no finito: {etiqueta}:{numero}")
                    continue

            elif tipo == "core":

                valor = [
                    x.strip()
                    for x in valor.split(",")
                    if x.strip() and x.strip() != clave
                ]
                valor = list(dict.fromkeys(valor))

            if clave in datos:

                informe["claves_duplicadas"].append({
                    "archivo": etiqueta,
                    "clave": clave,
                    "linea": numero,
                    "valor_anterior": str(datos[clave]),
                    "valor_nuevo": str(valor)
                })

                if estricto:
                    raise ValueError(
                        f"Clave duplicada: {etiqueta}:{numero}: "
                        f"{clave}")

                # En CORE se fusionan las asociaciones repetidas.
                if tipo == "core":
                    for palabra in valor:
                        if palabra not in datos[clave]:
                            datos[clave].append(palabra)
                    continue

            datos[clave] = valor

    return datos


# --------------------------------------------------
# UTILIDADES DE FUSIÓN
# --------------------------------------------------

def _claves_en_orden(base, activas):
    """Claves de la base primero, luego las nuevas de cada rama."""
    claves = dict.fromkeys(base)
    for _, datos in activas:
        claves.update(dict.fromkeys(datos))
    return claves


# --------------------------------------------------
# PESOS (Con redondeo estricto math.ceil)
# --------------------------------------------------

def fusionar_pesos(base, ramas, estrategia, informe):
    activas = [(e, d) for e, d in ramas if d is not None]
    resultado = OrderedDict()
    cambios = {e: 0 for e, _ in activas}

    for clave in _claves_en_orden(base, activas):

        v0 = base.get(clave)
        cambiados = []

        for etiqueta, datos in activas:
            v = datos.get(clave)
            if v != v0:
                cambiados.append((etiqueta, v))
                cambios[etiqueta] += 1

        if not cambiados:
            resultado[clave] = math.ceil(v0) if v0 is not None else 0
            continue

        con_valor = [v for _, v in cambiados if v is not None]

        if not con_valor:
            continue

        if len(con_valor) < len(cambiados):
            informe["borrados_ignorados"].append(clave)

        distintos = list(dict.fromkeys(con_valor))

        if len(distintos) == 1:
            resultado[clave] = math.ceil(distintos[0])
            continue

        punto_partida = v0 if v0 is not None else 0.0

        if estrategia == "promedio":
            deltas = [v - punto_partida for v in con_valor]
            resultado[clave] = math.ceil(
                punto_partida + sum(deltas) / len(deltas)
            )
        else:
            deltas = [v - punto_partida for v in distintos]
            resultado[clave] = math.ceil(punto_partida + sum(deltas))

    return resultado, cambios


# --------------------------------------------------
# CORE
# --------------------------------------------------

def fusionar_core(base, ramas):
    activas = [(e, d) for e, d in ramas if d is not None]
    resultado = OrderedDict()

    for clave in _claves_en_orden(base, activas):

        palabras_base = base.get(clave, [])
        conjunto_base = set(palabras_base)

        agregadas = OrderedDict()
        quitadas = set()

        for _, datos in activas:
            palabras = datos.get(clave, [])
            conjunto = set(palabras)

            for p in palabras:
                if p not in conjunto_base:
                    agregadas[p] = None

            quitadas |= conjunto_base - conjunto

        final = [p for p in palabras_base if p not in quitadas]
        final += list(agregadas)

        if final:
            resultado[clave] = final

    return resultado


# --------------------------------------------------
# DICCIONARIO
# --------------------------------------------------

def fusionar_diccionarios(base, ramas, informe, detener):
    activas = [(e, d) for e, d in ramas if d is not None]
    resultado = OrderedDict()

    for clave in _claves_en_orden(base, activas):

        v0 = base.get(clave)

        cambios = [
            (e, d.get(clave))
            for e, d in activas
            if d.get(clave) != v0
        ]

        if not cambios:
            nuevo = v0
        else:
            distintos = list(dict.fromkeys(v for _, v in cambios))

            if len(distintos) == 1:
                nuevo = distintos[0]
            else:
                informe["conflictos_diccionario"].append({
                    "clave": clave,
                    "valor_base": v0,
                    "propuestas": [
                        {"origen": e, "valor": v}
                        for e, v in cambios
                    ]
                })

                if detener:
                    raise ValueError(
                        f"Conflicto en diccionario: {clave}")

                nuevo = cambios[-1][1]

        if nuevo is not None:
            resultado[clave] = nuevo

    return resultado


# --------------------------------------------------
# CONVERTIR DATOS A TEXTO (Pesos como Enteros)
# --------------------------------------------------

def convertir_pesos(datos):
    return "".join(
        f"{clave} :: {int(valor)}\n"
        for clave, valor in datos.items()
    )


def convertir_core(datos):
    return "".join(
        f"{clave}>{','.join(palabras)}\n"
        for clave, palabras in datos.items()
        if palabras
    )


def convertir_diccionario(datos):
    return "".join(
        f"{clave} :: {valor}\n"
        for clave, valor in datos.items()
    )


# --------------------------------------------------
# PUBLICAR GENERACIÓN
# --------------------------------------------------

def publicar_generacion(carpeta_salida, archivos, informe):

    os.makedirs(carpeta_salida, exist_ok=True)

    temporal = tempfile.mkdtemp(
        prefix=".arcs_temporal_",
        dir=carpeta_salida
    )

    nombre_generacion = (
        "fusion_" + strftime("%Y%m%d_%H%M%S")
        + "_" + uuid.uuid4().hex[:6]
    )

    destino = os.path.join(carpeta_salida, nombre_generacion)

    try:

        for nombre, contenido in archivos.items():

            ruta = os.path.join(temporal, nombre)

            with open(ruta, "w", encoding="utf-8",
                      newline="\n") as f:
                f.write(contenido)
                f.flush()
                os.fsync(f.fileno())

        informe["generacion"] = nombre_generacion

        ruta_informe = os.path.join(
            temporal, "informe_fusion_arcs.json")

        with open(ruta_informe, "w", encoding="utf-8") as f:
            json.dump(informe, f, ensure_ascii=False, indent=4)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        try:
            os.chmod(temporal, 0o755)
        except OSError:
            pass

        os.replace(temporal, destino)
        temporal = None

        return destino

    finally:

        if temporal and os.path.exists(temporal):
            shutil.rmtree(temporal)


# --------------------------------------------------
# FUNCIÓN PRINCIPAL
# --------------------------------------------------

def fusionar_arcs(
    ruta_base,
    rutas_ramas,
    carpeta_salida,
    estrategia_pesos="promedio",
    estricto=False,
    detener_en_conflicto_diccionario=False
):
    if estrategia_pesos not in ("promedio", "suma"):
        raise ValueError("Usa estrategia 'promedio' o 'suma'.")

    if not rutas_ramas:
        raise ValueError("Necesitas al menos una rama.")

    salida = validar_salida([ruta_base, *rutas_ramas],
                            carpeta_salida)

    etiquetas = [f"rama{i}" for i in range(1, len(rutas_ramas) + 1)]
    entradas = [("base", ruta_base)] + list(zip(etiquetas,
                                                rutas_ramas))

    informe = {
        "estrategia_pesos": estrategia_pesos,
        "estricto": estricto,
        "detener_en_conflicto_diccionario":
            detener_en_conflicto_diccionario,
        "origenes": {
            etiqueta: os.path.realpath(ruta)
            for etiqueta, ruta in entradas
        },
        "archivos_faltantes": [],
        "lineas_invalidas": [],
        "claves_duplicadas": [],
        "conflictos_diccionario": [],
        "borrados_ignorados": [],
        "resumen": {}
    }

    def cargar(nombre, separador, tipo):
        cargados = []
        for etiqueta, ruta in entradas:
            r = ruta if tipo == "pesos" \
                else archivo_hermano(ruta, nombre)
            cargados.append((
                etiqueta,
                leer_lineas(r, separador, tipo, informe,
                            etiqueta, estricto)
            ))
        return cargados

    def separar(cargados):
        base = cargados[0][1]
        if base is None:
            base = OrderedDict()
        return base, cargados[1:]

    # Pesos
    base_p, ramas_p = separar(cargar(PESOS, "::", "pesos"))
    pesos, cambios = fusionar_pesos(base_p, ramas_p,
                                    estrategia_pesos, informe)

    # Core
    base_c, ramas_c = separar(cargar(CORE, ">", "core"))
    core_final = fusionar_core(base_c, ramas_c)

    # Diccionario
    base_d, ramas_d = separar(cargar(DICC, "::", "dicc"))
    diccionario_final = fusionar_diccionarios(
        base_d, ramas_d, informe, detener_en_conflicto_diccionario)

    informe["resumen"] = {
        "ramas": len(rutas_ramas),
        "pesos": len(pesos),
        "pesos_cambiados_por_rama": cambios,
        "claves_core": len(core_final),
        "asociaciones_core": sum(
            len(v) for v in core_final.values()),
        "entradas_diccionario": len(diccionario_final),
        "conflictos_diccionario": len(
            informe["conflictos_diccionario"]),
        "lineas_invalidas": len(informe["lineas_invalidas"]),
        "archivos_faltantes": len(informe["archivos_faltantes"]),
        "claves_duplicadas": len(informe["claves_duplicadas"])
    }

    archivos = {
        PESOS: convertir_pesos(pesos),
        CORE: convertir_core(core_final),
        DICC: convertir_diccionario(diccionario_final)
    }

    generacion = publicar_generacion(salida, archivos, informe)
    informe["ruta_generacion"] = generacion

    return informe


# --------------------------------------------------
# EJECUCIÓN
# --------------------------------------------------

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description="Fusionador de versiones ARCS (N ramas)")

    parser.add_argument(
        "--base",
        default="/storage/emulated/0/arcs_base/arcs_pesos.txt")

    parser.add_argument(
        "--rama", action="append", default=None,
        help="arcs_pesos.txt de una versión; repite --rama "
             "por cada versión.")

    parser.add_argument(
        "--salida",
        default="/storage/emulated/0/arcs_fusionado/")

    parser.add_argument(
        "--estrategia", choices=["promedio", "suma"],
        default="promedio")

    parser.add_argument("--estricto", action="store_true")
    parser.add_argument("--detener-en-conflicto",
                        action="store_true")

    args = parser.parse_args()

    ramas = args.rama or [
        "/storage/emulated/0/arcs_v1/arcs_pesos.txt",
        "/storage/emulated/0/arcs_v2/arcs_pesos.txt",
    ]

    try:

        resultado = fusionar_arcs(
            args.base, ramas, args.salida,
            estrategia_pesos=args.estrategia,
            estricto=args.estricto,
            detener_en_conflicto_diccionario=args.detener_en_conflicto
        )

        print("\nFUSIÓN COMPLETADA")
        print("Resumen:", resultado["resumen"])
        print("Generación:", resultado["ruta_generacion"])

        r = resultado["resumen"]

        if r["conflictos_diccionario"]:
            print("ADVERTENCIA: conflictos en el diccionario.")
        if r["archivos_faltantes"]:
            print("ADVERTENCIA: faltan archivos (ver informe).")
        if r["lineas_invalidas"]:
            print("ADVERTENCIA: hay líneas inválidas (ver informe).")

        print("Tip: usa la carpeta generada como nueva base y "
              "crea las nuevas ramas a partir de ella.")

    except Exception as error:

        print("\nFALLO EN LA FUSIÓN:")
        print(error)
