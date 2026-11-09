import json
import os # Para crear carpetas y manejar rutas
import shutil # Para copiar archivos, lo usamos para los respaldos.bak
import unicodedata # Para quitarle los acentos a las palabras: "canción" -> "cancion"
import random # Para que no siempre responda igual, le mete azar
import asyncio # Para que el input no congele todo el programa
import re # Expresiones regulares, para limpiar texto con magia negra
import math # Para operaciones matematicas avanzadas como raices o pi
from collections import defaultdict # Diccionario que si no existe la llave, te crea lista vacia solo
from modulo_cerebro import ModuloCerebro # Tu otro archivo, el cerebro que busca en web
import datetime
import controls
import getpass
from trazabilidad import TrazadorARCS
from seguridad import verificar_clave
import ast
import operator
import uuid
from logslpp import inflog
from personas import FichasPersonas, clasificar, redactar_respuesta
from permisos import PERMISOS, leer_permisos, cambiar_permiso
from cuentas import cuenta_existe
from servidor_web import iniciar_registro_web

RUTA_BASE_DEFAULT = "/storage/emulated/0/ARCS/test1/"
MAX_BITS_POTENCIA = 4000  # Limite de tamaño para potencias: evita colgar el telefono
MAX_OPCIONES_TRAZA = 10   # Cuantas opciones guarda la traza por paso (la cadena usa todas)
MAX_CANDIDATOS_TRAZA = 20


def nombre_seguro(nombre):
    """Convierte un nombre en un segmento seguro para una ruta."""
    limpio = re.sub(r"[^a-z0-9_-]", "_", nombre.lower().strip())[:32]
    return limpio or "anonimo"


def archivo_valido(ruta, separador):
    """Comprueba que el archivo tenga contenido y use el separador esperado."""
    if not os.path.exists(ruta) or os.path.getsize(ruta) == 0:
        return False
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            lineas = [l.strip() for l in f if l.strip()]
        return bool(lineas) and all(separador in l for l in lineas)
    except Exception:
        return False


def backups_de(ruta):
    return [ruta + ".bak", ruta + ".bak2", ruta + ".bak3"]


def rotar_respaldos(ruta, separador):
    """Copia el archivo válido a .bak y desplaza los respaldos anteriores."""
    if not archivo_valido(ruta, separador):
        return
    try:
        bks = backups_de(ruta)
        for i in range(len(bks) - 1, 0, -1):
            if os.path.exists(bks[i - 1]):
                os.replace(bks[i - 1], bks[i])
        shutil.copy(ruta, bks[0])
    except Exception:
        pass


def escribir_seguro(ruta, lineas):
    """Escribe en un archivo temporal y luego lo reemplaza."""
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for linea in lineas:
            f.write(linea + "\n")
    os.replace(tmp, ruta)


def resumen_opciones(opciones, prioridades):
    """Resume las opciones de mayor prioridad para la traza."""
    mejores = sorted(opciones, key=lambda o: prioridades.get(o, 0), reverse=True)[:MAX_OPCIONES_TRAZA]
    return {"opciones_total": len(opciones),
            "opciones": {o: prioridades.get(o, 0) for o in mejores}}


def quitar_acentos(t):
    """Convierte a minúsculas y quita acentos sin alterar la eñe."""
    t = t.lower().replace("ñ", "\x00")  # Protege la eñe durante la normalización.
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.replace("\x00", "ñ")


_OPERACIONES = {ast.Add: operator.add, ast.Sub: operator.sub,
                ast.Mult: operator.mul, ast.Div: operator.truediv}


def evaluar_seguro(expr):
    """Evalúa números y operadores aritméticos permitidos, sin usar eval()."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.UAdd):
            return ev(n.operand)
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow):
                if (isinstance(a, int) and isinstance(b, int) and b >= 0
                        and abs(a) > 1 and b * math.log2(abs(a)) > MAX_BITS_POTENCIA):
                    raise OverflowError("potencia demasiado grande")
                return a ** b
            if type(n.op) in _OPERACIONES:
                return _OPERACIONES[type(n.op)](a, b)
        raise ValueError("expresion no permitida")
    return ev(ast.parse(expr, mode="eval"))

# =============================================================================
# Clase principal de ARCS.
# =============================================================================
class ARCS:
    def __init__(self, ruta_base=None):
        # Rutas de los datos de ARCS.
        ruta = ruta_base or RUTA_BASE_DEFAULT
        self.ruta_base = ruta if ruta.endswith(os.sep) or ruta.endswith("/") else ruta + "/"
        self.trazador = TrazadorARCS(os.path.join(self.ruta_base, "trazas_arcs.jsonl"))
        self.trazabilidad_activa = True
        self.id_sesion = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.archivo_memoria = self.ruta_base + "arcs_v2_core.txt" # Guarda: palabra > siguiente1,siguiente2
        self.archivo_dicc = self.ruta_base + "arcs_v2_dict.txt" # Guarda: palabra :: significado
        self.archivo_pesos = self.ruta_base + "arcs_pesos.txt" # Guarda: palabra :: peso

        self.cerebro = ModuloCerebro(self.ruta_base)

        # Fichas de personas: datos completos, sin fragmentar en pares de palabras.
        #  - creador (nivel 2): escribe en la ficha global (personas_global.json)
        #  - usuario normal (nivel 1): escribe en su propia carpeta (privado)
        #  - invitado (nivel 0): no guarda nada
        self.personas_global = FichasPersonas(os.path.join(self.ruta_base, "personas_global.json"))
        self.personas_usuario = None
        # Permisos de la cuenta activa (se cargan al entrar). El creador tiene todos.
        self.permisos_valores = {}
        self.servidor_registro = None
        # Nombres que son personas aunque esten en conceptos_clave
        self.nombres_semilla = {"legnar"}

        # Configuración.
        self.capas = 250 # Cuantas palabras maximo intenta generar por respuesta
        self.max_memoria_por_key = 20000000 # Para que no se haga una lista infinita
        self.memoria = defaultdict(list)
        self.diccionario = {}
        self.prioridades = defaultdict(float)

        # Memoria por usuario.
        self.memoria_usuario = defaultdict(list)
        self.prioridades_usuario = defaultdict(float)
        self.dirty = False # Bandera: "la memoria global cambio, hay que guardar"
        self.dirty_usuario = False

        # Contexto y personalidad.
        self.contexto = []
        self.max_contexto = 3000000
        self.personalidad = "femenina"
        self.temperatura = 0.85 # 0.0 aburrido, 1.0 bien loco
        self.silent_mode = False
        self.autosave_cada = 10 # Guarda la memoria cada N mensajes
        # Una palabra clave solo detiene la cadena después de este mínimo de palabras.
        self.palabras_minimas_para_parar = 5
        self.mensajes_sin_guardar = 0

        # Continuación manual de respuestas.
        self.estado_respuesta = None
        self.max_pasos_continuacion = 1000
        # Número máximo de apariciones de una palabra en una respuesta.
        self.max_repeticiones_palabra = 1  # Cada palabra aparece como máximo una vez.

        # Siglas y conceptos que se muestran en mayúsculas.
        self.siglas_mayus = {"sat", "profeco", "arcs", "faa", "otan", "urss", "lpp"}

        # Conversión de números y operadores escritos con palabras.
        self.numeros_texto = {
            "cero": "0", "uno": "1", "dos": "2", "tres": "3", "cuatro": "4",
            "cinco": "5", "seis": "6", "siete": "7", "ocho": "8", "nueve": "9", "diez": "10"
        }
        self.operadores_texto = {
            "mas": "+", "menos": "-", "por": "*", "multiplicado por": "*",
            "entre": "/", "dividido entre": "/", "dividido por": "/",
            "elevado a la": "**", "elevado al": "**", "elevado a": "**", "elevado": "**", 
            "potencia": "**", "^": "**"
        }

        # Filtros.
        self.conceptos_clave = {"lealtad", "clika", "respeto", "gringos", "codigo", "fuerza", "amor", "legnar", "amigos", "sexo", "seguridad", "mexico", "himno", "poder", "niña", "arcs", "propiedad", "privado", "derechos", "onu", "otan", "urss", "mexicas", "mexica", "mexicanos", "mexicanas", "niños", "niñas", "hombre", "mujer", "faa", "profeco", "sat", "ley", "ganar", "ia", "ias", "idioma", "diferente", "gustar", "cambiar", "error", "juramento", "patria", "bandera", "mexicana"}
        self.stopwords = {"el", "la", "de", "que", "y", "a", "en", "un", "es", "por", "con", "para", "los", "las", "del", "se", "no", "te"}

        # Usuarios.
        self.usuario_actual = "invitado"
        self.id_usuario = None
        self.es_creador = False
        self.nivel_usuario = 0 # 0 invitado, 1 normal, 2 creador
        self.archivo_memoria_usuario = ""
        self.archivo_pesos_usuario = ""

        # Inicialización en el orden requerido.
        os.makedirs(self.ruta_base, exist_ok=True)
        self.restaurar_si_esta_roto()
        self.crear_respaldo_preventivo()
        self.boot_permanente()

    def archivos_sistema(self):
        return [(self.archivo_dicc, "::"), (self.archivo_memoria, ">"), (self.archivo_pesos, "::")]

    def restaurar_si_esta_roto(self):
        for f, sep in self.archivos_sistema():
            if archivo_valido(f, sep):
                continue
            for bak in backups_de(f):
                if archivo_valido(bak, sep):
                    shutil.copy(bak, f)
                    break

    def crear_respaldo_preventivo(self):
        # Se ejecuta al iniciar para conservar estados de sesiones anteriores.
        for f, sep in self.archivos_sistema():
            rotar_respaldos(f, sep)

    def cargar_archivo(self, ruta, obj, tipo):
        if not os.path.exists(ruta):
            return
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                for l in f:
                    l = l.strip()
                    if not l: continue
                    if tipo == 1 and "::" in l:
                        k, v = l.split("::", 1)
                        obj[k.strip()] = v.strip()
                    elif tipo == 2 and ">" in l:
                        k, v = l.split(">", 1)
                        vals = [x for x in v.strip().split(",") if x and x!= k.strip()]
                        if vals: obj[k.strip()] = vals[:self.max_memoria_por_key]
                    elif tipo == 3 and "::" in l:
                        k, v = l.split("::", 1)
                        try: obj[k.strip()] = float(v.strip())
                        except: obj[k.strip()] = 0.0
        except:
            pass

    def boot_permanente(self):
        self.cargar_archivo(self.archivo_dicc, self.diccionario, 1)
        self.cargar_archivo(self.archivo_memoria, self.memoria, 2)
        self.cargar_archivo(self.archivo_pesos, self.prioridades, 3)

    def verificar_creador(self, clave):
        """Verifica la clave de creador almacenada en clave_creador.txt."""
        ruta = os.path.join(self.ruta_base, "clave_creador.txt")
        if not os.path.exists(ruta):
            return False
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return verificar_clave(clave or "", f.read())
        except Exception:
            return False

    def establecer_usuario(self, nombre, clave=None):
        self.usuario_actual = nombre.lower().strip()
        self.id_usuario = None
        self.personas_usuario = None
        if self.usuario_actual == "legnar":
            if self.verificar_creador(clave):
                self.es_creador = True
                self.nivel_usuario = 2
            else:
                print("[sys]: La clave de creador es incorrecta o no está configurada; entrarás como usuario normal.")
                self.nivel_usuario = 1
                self.iniciar_archivos_usuario()
        elif self.usuario_actual == "invitado":
            self.nivel_usuario = 0
        else:
            if not cuenta_existe(self.ruta_base, self.usuario_actual):
                print("[sys]: No existe una cuenta con ese nombre. Créala en el registro web primero; entrarás como invitado.")
                self.usuario_actual = "invitado"
                self.nivel_usuario = 0
                return
            self.nivel_usuario = 1
            self.iniciar_archivos_usuario()
            datos = leer_permisos(os.path.dirname(self.archivo_memoria_usuario))
            self.permisos_valores = datos["permisos"]
            if datos.get("legacy"):
                print("[sys]: Tu cuenta es anterior al registro de permisos. Revisa /permisos.")

    def iniciar_archivos_usuario(self):
        carpeta = self._obtener_carpeta_usuario()
        self.archivo_memoria_usuario = os.path.join(carpeta, "core.txt")
        self.archivo_pesos_usuario = os.path.join(carpeta, "pesos.txt")
        self.migrar_archivos_usuario_viejos()
        rotar_respaldos(self.archivo_memoria_usuario, ">")
        rotar_respaldos(self.archivo_pesos_usuario, "::")
        if not os.path.exists(self.archivo_memoria_usuario):
            self.generar_memoria_limpia_usuario()
        self.cargar_archivo(self.archivo_memoria_usuario, self.memoria_usuario, 2)
        self.cargar_archivo(self.archivo_pesos_usuario, self.prioridades_usuario, 3)
        self.personas_usuario = FichasPersonas(
            os.path.join(os.path.dirname(self.archivo_memoria_usuario), "personas.json"))

    def _obtener_carpeta_usuario(self):
        """Busca o crea una carpeta de usuario con un identificador persistente."""
        carpeta_usuarios = os.path.join(self.ruta_base, "usuarios")
        os.makedirs(carpeta_usuarios, exist_ok=True)
        slug = nombre_seguro(self.usuario_actual)
        archivo_identidad = ".arcs_usuario.json"

        with os.scandir(carpeta_usuarios) as entradas:
            for entrada in entradas:
                if not entrada.is_dir():
                    continue
                ruta_identidad = os.path.join(entrada.path, archivo_identidad)
                try:
                    with open(ruta_identidad, "r", encoding="utf-8") as archivo:
                        identidad = json.load(archivo)
                except (OSError, ValueError):
                    continue
                if (isinstance(identidad, dict)
                        and identidad.get("usuario") == self.usuario_actual
                        and identidad.get("id")):
                    self.id_usuario = identidad["id"]
                    return entrada.path

        carpeta_antigua = os.path.join(carpeta_usuarios, slug)
        ruta_identidad_antigua = os.path.join(carpeta_antigua, archivo_identidad)
        if os.path.isdir(carpeta_antigua) and not os.path.exists(ruta_identidad_antigua):
            identificador = uuid.uuid4().hex
            nueva_carpeta = os.path.join(carpeta_usuarios, f"{slug}_{identificador}")
            self._guardar_identidad_usuario(ruta_identidad_antigua, identificador)
            os.rename(carpeta_antigua, nueva_carpeta)
            self.id_usuario = identificador
            return nueva_carpeta

        while True:
            identificador = uuid.uuid4().hex
            carpeta = os.path.join(carpeta_usuarios, f"{slug}_{identificador}")
            try:
                os.mkdir(carpeta)
                break
            except FileExistsError:
                continue

        self._guardar_identidad_usuario(
            os.path.join(carpeta, archivo_identidad), identificador
        )
        self.id_usuario = identificador
        return carpeta

    def _guardar_identidad_usuario(self, ruta, identificador):
        temporal = ruta + ".tmp"
        with open(temporal, "w", encoding="utf-8") as archivo:
            json.dump(
                {"usuario": self.usuario_actual, "id": identificador},
                archivo,
                ensure_ascii=False,
            )
            archivo.write("\n")
        os.replace(temporal, ruta)

    def migrar_archivos_usuario_viejos(self):
        """Copia los archivos de la versión anterior a la carpeta del usuario."""
        base = nombre_seguro(self.usuario_actual)
        pares = [
            (self.archivo_memoria_usuario, self.ruta_base + f"arcs_user_{base}_core.txt"),
            (self.archivo_pesos_usuario, self.ruta_base + f"arcs_user_{base}_pesos.txt"),
        ]
        for nuevo, viejo in pares:
            if not os.path.exists(nuevo) and os.path.exists(viejo):
                shutil.copy(viejo, nuevo)

    def generar_memoria_limpia_usuario(self):
        for k, v in self.memoria.items():
            k_limpio = re.sub(r'([^rcl])\1+', r'\1', k)
            v_limpio = [re.sub(r'([^rcl])\1+', r'\1', palabra) for palabra in v]
            self.memoria_usuario[k_limpio] = v_limpio
        for k, v in self.prioridades.items():
            k_limpio = re.sub(r'([^rcl])\1+', r'\1', k)
            self.prioridades_usuario[k_limpio] = float(v)
        self.dirty_usuario = True
        self.guardar_indestructible()

    def limpiar(self, t):
        t = quitar_acentos(t)
        texto_limpio = re.sub(r'[^a-z0-9ñ ]+', '', t).strip()
        
        palabras_procesadas = []
        for p in texto_limpio.split():
            if p in self.siglas_mayus:
                palabras_procesadas.append(p.upper())
            else:
                palabras_procesadas.append(p)
                
        return " ".join(palabras_procesadas)

    def procesar_calculo(self, texto):
        """
        Intercepta expresiones matematicas complejas incluyendo potencias y las evalua.
        Retorna una tupla: (resultado_str, es_calculo_puro)
        """
        # Quita acentos para normalizar palabras clave como "mas".
        t = quitar_acentos(texto)

        # Reemplaza palabras de números y operadores por sus símbolos.
        for txt_num, num in self.numeros_texto.items():
            t = re.sub(rf"\b{txt_num}\b", num, t)
        # Sustituye primero las frases largas y luego las cortas.
        for txt_op, op in sorted(self.operadores_texto.items(), key=lambda kv: -len(kv[0])):
            patron_operador = re.escape(txt_op)
            if txt_op[0].isalnum():
                patron_operador = rf"\b{patron_operador}\b"
            t = re.sub(patron_operador, op, t)

        numero = r"(?:\d+(?:\.\d+)?|\.\d+)"
        patron_expresion = re.compile(
            rf"(?<![\w.])([+-]?\s*{numero}(?:\s*(?:\*\*|[+\-*/])\s*[+-]?\s*{numero})+)(?![\w.])"
        )
        expresion = patron_expresion.search(t)
        if expresion:
            expr_str = re.sub(r"\s+", "", expresion.group(1))
            try:
                # Evalua la expresion con el interprete aritmetico seguro.
                res = evaluar_seguro(expr_str)
                if isinstance(res, float) and res.is_integer():
                    res = int(res)
                
                texto_sin_expr = (
                    t[:expresion.start()] + t[expresion.end():]
                ).strip()
                es_puro = len(texto_sin_expr) < 3
                
                return f"El resultado de {expr_str} es {res}", es_puro
            except ZeroDivisionError:
                return "Error: no se puede dividir entre cero", True
            except (OverflowError, MemoryError):
                return "Error: resultado demasiado grande para procesar", True
            except Exception:
                pass
        return None, False

    # =========================================================================
    # PERSONAS: guardar datos completos y responder preguntas sobre personas
    # =========================================================================
    def permiso(self, nombre):
        """True/False segun la cuenta activa. El creador tiene todos; el invitado no guarda nada."""
        if self.nivel_usuario == 2:
            return True
        if self.nivel_usuario == 0:
            return False
        return bool(self.permisos_valores.get(nombre, False))

    def _fichas_lectura(self):
        """Fichas que este usuario puede consultar: primero las suyas, luego las publicas."""
        fichas = []
        if self.personas_usuario is not None and self.permiso("guardar_personas"):
            fichas.append(self.personas_usuario)
        # Los invitados siempre pueden leer lo publico; los usuarios segun su permiso.
        if self.nivel_usuario in (0, 2) or self.permiso("consultar_datos_publicos"):
            fichas.append(self.personas_global)
        return fichas

    def _ficha_escritura(self):
        if self.nivel_usuario == 2:
            return self.personas_global
        if self.nivel_usuario == 1 and self.permiso("guardar_personas"):
            return self.personas_usuario
        return None

    def _persona_conocida(self, nombre):
        for f in self._fichas_lectura():
            k, cands = f.resolver(nombre)
            if k or cands:
                return True
        return False

    def _no_personas(self):
        return {c for c in self.conceptos_clave if c not in self.nombres_semilla}

    def procesar_personas(self, t, traza=None):
        """
        Revisa si el mensaje habla de una persona o pregunta por una.
        Devuelve la respuesta si lo manejo, o None para que siga el flujo normal
        (aprender + responder con Markov). Si lo maneja, NO fragmenta el mensaje en la memoria Markov.
        """
        if self.procesar_calculo(t)[1]:
            return None
        intencion = clasificar(t, self._persona_conocida, self._no_personas())
        if traza is not None:
            traza["intencion"] = dict(intencion)
        tipo = intencion["tipo"]
        if tipo == "afirmacion_persona":
            respuesta = self._guardar_dato_persona(intencion, t, traza)
        elif tipo == "pregunta_persona":
            respuesta = self._responder_pregunta_persona(intencion, traza)
        else:
            return None
        self.estado_respuesta = None
        if traza is not None:
            traza["respuesta"] = {"ruta": "personas", "texto_final": respuesta}
        return respuesta

    def _guardar_dato_persona(self, intencion, original, traza=None):
        nombre = intencion["persona"]
        ficha = self._ficha_escritura()
        if ficha is None:
            if self.nivel_usuario == 1:
                if traza is not None:
                    traza["personas"] = {"accion": "no_guardado", "motivo": "permiso_desactivado"}
                return ("No guardo datos de personas porque tienes desactivado 'guardar_personas'. "
                        "Puedes activarlo con /permiso guardar_personas on.")
            if traza is not None:
                traza["personas"] = {"accion": "no_guardado", "motivo": "invitado"}
            return ("Te escuché, pero como invitado no guardo información sobre personas. "
                    "Inicia sesión con tu nombre y la recordaré.")
        res = ficha.agregar_hecho(nombre, intencion["hecho"], original, self.usuario_actual,
                                  intencion["forma"], intencion["primera_persona"])
        if traza is not None:
            traza["personas"] = {"accion": res.get("estado"), "persona": res.get("nombre", nombre),
                                 "hecho": intencion["hecho"], "forma": intencion["forma"],
                                 "primera_persona": intencion["primera_persona"],
                                 "patron": intencion.get("patron"), "guardado_en_disco": res.get("guardado")}
        nombre = res.get("nombre", nombre)
        if res["estado"] == "ambiguo":
            return (f"Conozco a varias personas con ese nombre: {', '.join(sorted(res['candidatos']))}. "
                    f"Dime el nombre completo para saber de cuál hablas.")
        if res["estado"] == "repetido":
            return f"Eso ya lo sabía de {nombre}."
        if res["estado"] == "invalido":
            return "No pude entender ese dato."
        if not res.get("guardado", True):
            return f"Lo entendí sobre {nombre}, pero no pude escribirlo en el archivo."
        return f"Listo, guardé eso sobre {nombre}."

    def _responder_pregunta_persona(self, intencion, traza=None):
        nombre = intencion["persona"]
        hechos, nombre_ficha, cands, orden = [], None, [], []
        for ficha in self._fichas_lectura():
            k, cs = ficha.resolver(nombre)
            if k:
                nombre_ficha = nombre_ficha or ficha.personas[k]["nombre"]
                # lo global (publico) primero, lo del usuario despues
                hechos = (ficha.personas[k]["hechos"] + hechos) if ficha is self.personas_global \
                    else (hechos + ficha.personas[k]["hechos"])
            else:
                cands += [ficha.personas[c]["nombre"] for c in cs]
        if traza is not None:
            traza["personas"] = {"accion": "pregunta", "persona": nombre, "atributo": intencion.get("atributo"),
                                 "encontrada": bool(nombre_ficha), "datos": len(hechos)}
        if nombre_ficha:
            return redactar_respuesta({"nombre": nombre_ficha, "hechos": hechos},
                                      intencion.get("atributo"), self.usuario_actual)
        if len(set(cands)) > 1:
            return f"Conozco a varias personas con ese nombre: {', '.join(sorted(set(cands)))}. ¿A cuál te refieres?"
        return f"No tengo información sobre {nombre}. Si quieres, cuéntame algo y lo guardo."

    def texto_permisos(self):
        if self.nivel_usuario == 2:
            return "El creador de ARCS tiene todos los permisos."
        if self.nivel_usuario == 0:
            return "Como invitado no tienes permisos que cambiar. Inicia sesión con tu cuenta."
        lineas = []
        for clave, cfg in PERMISOS.items():
            estado = "sí" if self.permiso(clave) else "no"
            lineas.append(f"  {clave}: {estado}  - {cfg['descripcion']}")
        return "Tus permisos:\n" + "\n".join(lineas) + "\nCambia uno con: /permiso <nombre> on|off"

    def cambiar_permiso_cmd(self, texto):
        if self.nivel_usuario == 0:
            return "Como invitado no tienes permisos que cambiar."
        if self.nivel_usuario == 2:
            return "El creador de ARCS tiene todos los permisos; no se cambian desde aquí."
        partes = texto.split()
        if len(partes) != 3 or partes[2].lower() not in ("on", "off"):
            return "Uso: /permiso <nombre> on|off   (ver nombres con /permisos)"
        carpeta = os.path.dirname(self.archivo_memoria_usuario)
        ok, mensaje = cambiar_permiso(carpeta, partes[1], partes[2].lower() == "on")
        if ok:
            self.permisos_valores = leer_permisos(carpeta)["permisos"]
        return mensaje

    def listar_personas(self):
        nombres = sorted({n for f in self._fichas_lectura() for n in f.nombres()})
        return ("Personas que conozco: " + ", ".join(nombres)) if nombres else "Todavía no conozco a nadie."

    def olvidar_persona(self, nombre):
        """Borra la ficha de una persona de TU memoria (el creador borra de la global)."""
        if not nombre:
            return "Dime a quién quieres que olvide: /olvidar <nombre>"
        ficha = self._ficha_escritura()
        if ficha is None:
            return "Como invitado no guardo información de personas, así que no hay nada que olvidar."
        k, cands = ficha.resolver(nombre)
        if k:
            nombre_real = ficha.personas[k]["nombre"]
            ficha.olvidar(k)
            return f"Listo, olvidé todo lo que sabía de {nombre_real}."
        if len(cands) > 1:
            return "Hay varias personas con ese nombre: " + ", ".join(ficha.personas[c]["nombre"] for c in cands)
        return f"No tengo a nadie llamado {nombre} en tu memoria."

    def aprender(self, t, traza=None):
        # Evita guardar cálculos puros en la memoria de Markov.
        res_calc, es_puro = self.procesar_calculo(t)
        if traza is not None:
            traza["aprendizaje"] = {
                "calculadora_detecto": res_calc is not None,
                "calculo_puro": es_puro,
                "resultado_calculo": res_calc,
                "aristas": [],
                "motivos_omision": []
            }
        if es_puro:
            if traza is not None:
                traza["aprendizaje"]["motivos_omision"].append("calculo_matematico_puro")
            return

        palabras = self.limpiar(t).split()
        if traza is not None:
            traza["aprendizaje"]["palabras_normalizadas"] = list(palabras)
        if len(palabras) < 2:
            if traza is not None:
                traza["aprendizaje"]["motivos_omision"].append("menos_de_dos_palabras")
            return
        self.contexto.append(palabras)
        if len(self.contexto) > self.max_contexto: self.contexto.pop(0)
        factor_base = 0.0
        factor_usuario = 0.0
        if self.nivel_usuario == 0: factor_base = 0.025
        elif self.nivel_usuario == 2: factor_base = 10.0
        elif self.nivel_usuario == 1:
            factor_base = 1.0
            factor_usuario = 5.0
        cambios_base = False
        cambios_usuario = False
        for i in range(len(palabras) - 1):
            a, s = palabras[i], palabras[i+1]
            if a == s or not a or not s or a in self.stopwords:
                if traza is not None:
                    traza["aprendizaje"]["motivos_omision"].append({"par": [a, s], "motivo": "palabras_iguales_vacias_o_stopword_inicial"})
                continue

            a_min = a.lower()
            s_min = s.lower()
            es_clave = (a_min in self.conceptos_clave or s_min in self.conceptos_clave)
            peso_incremental = (1.0 + (12.0 if es_clave else 0.0))
            arista = {"desde": a, "hacia": s, "concepto_clave": es_clave,
                      "incremento_unitario": peso_incremental,
                      "factor_global": factor_base, "factor_usuario": factor_usuario}
            if factor_base > 0:
                nueva = s not in self.memoria[a]
                if nueva:
                    self.memoria[a].append(s)
                    cambios_base = True
                peso_antes = self.prioridades[a]
                self.prioridades[a] += (peso_incremental * factor_base)
                cambios_base = True
                if a not in self.diccionario:
                    self.diccionario[a] = s
                    cambios_base = True
                arista["nueva_arista_global"] = nueva
                arista["peso_global_antes"] = peso_antes
                arista["peso_global_despues"] = self.prioridades[a]
            if factor_usuario > 0:
                nueva_usuario = s not in self.memoria_usuario[a]
                if nueva_usuario:
                    self.memoria_usuario[a].append(s)
                    cambios_usuario = True
                peso_usuario_antes = self.prioridades_usuario[a]
                self.prioridades_usuario[a] += (peso_incremental * factor_usuario)
                cambios_usuario = True
                arista["nueva_arista_usuario"] = nueva_usuario
                arista["peso_usuario_antes"] = peso_usuario_antes
                arista["peso_usuario_despues"] = self.prioridades_usuario[a]
            if traza is not None:
                traza["aprendizaje"]["aristas"].append(arista)
        if cambios_base: self.dirty = True
        if cambios_usuario: self.dirty_usuario = True
        if traza is not None:
            traza["aprendizaje"]["cambios_globales"] = cambios_base
            traza["aprendizaje"]["cambios_usuario"] = cambios_usuario
            traza["aprendizaje"]["factor_global"] = factor_base
            traza["aprendizaje"]["factor_usuario"] = factor_usuario

    def aplicar_personalidad(self, texto):
        if self.personalidad == "femenina":
            reemplazos = {r"\bentiendo\b": "literal te entiendo", r"\bonline\b": "arcs activa tipo bien", r"\bhola\b": "holaaa qué onda"}
            for k, v in reemplazos.items():
                texto = re.sub(k, v, texto, flags=re.IGNORECASE)
            if self.es_creador: texto = texto.replace("wey", "jefe")
            if "quien eres" in texto.lower(): texto = "Soy ARCS, propiedad de LPP y el grupo Srangel y asociados externos"
        return texto

    def responder(self, t, traza=None):
        # Comprueba primero si la entrada requiere un cálculo directo.
        calculo, es_puro = self.procesar_calculo(t)
        if traza is not None:
            traza["respuesta"] = {"calculo_detectado": calculo is not None,
                                  "calculo_puro": es_puro, "resultado_calculo": calculo}

        # Para un cálculo puro, devuelve únicamente el resultado.
        if calculo is not None and es_puro:
            final = self.aplicar_personalidad(calculo)
            if traza is not None:
                traza["respuesta"].update({"ruta": "calculo_puro", "texto_pre_personalidad": calculo,
                                           "texto_final": final})
            return final

        # Si hay texto junto con la operación, combina ambos resultados.
        palabras = self.limpiar(t).split()
        if traza is not None:
            traza["respuesta"]["palabras_normalizadas"] = list(palabras)
        if not palabras:
            bruto = "online"
            final = self.aplicar_personalidad(bruto)
            if traza is not None:
                traza["respuesta"].update({"ruta": "entrada_vacia", "texto_pre_personalidad": bruto, "texto_final": final})
            return final
        if "quien eres" in " ".join(palabras).lower():
            bruto = "quien eres"
            final = self.aplicar_personalidad(bruto)
            if traza is not None:
                traza["respuesta"].update({"ruta": "identidad_directa", "texto_pre_personalidad": bruto, "texto_final": final})
            return final

        fuente_memoria = "usuario" if self.nivel_usuario == 1 else "global"
        mem_activa = self.memoria_usuario if self.nivel_usuario == 1 else self.memoria
        prio_activa = self.prioridades_usuario if self.nivel_usuario == 1 else self.prioridades
        candidatos = [p for p in palabras if p in mem_activa]
        if not candidatos and self.nivel_usuario == 1:
            candidatos = [p for p in palabras if p in self.memoria]
            mem_activa = self.memoria
            prio_activa = self.prioridades
            fuente_memoria = "global_fallback"
        if traza is not None:
            traza["respuesta"].update({"fuente_memoria": fuente_memoria,
                                      "candidatos_total": len(candidatos),
                                      "candidatos": [{"palabra": p, "prioridad": prio_activa.get(p, 0)}
                                                     for p in candidatos[:MAX_CANDIDATOS_TRAZA]]})

        if not candidatos:
            clave = palabras[0]
            bruto = self.diccionario.get(clave, "sistema analizando")
            if traza is not None:
                traza["respuesta"].update({"ruta": "sin_candidatos_diccionario", "clave_diccionario": clave,
                                          "valor_diccionario": bruto})
        else:
            enfoque = max(candidatos, key=lambda p: prio_activa.get(p, 0))
            res, actual = [], enfoque
            conteo_palabras = {actual: 1}
            pasos = []
            motivo_parada = "limite_capas"
            for indice in range(self.capas):
                if actual not in mem_activa:
                    motivo_parada = "clave_sin_memoria"
                    break
                opciones = [
                    o for o in mem_activa[actual]
                    if o and conteo_palabras.get(o, 0) < self.max_repeticiones_palabra
                ]
                if not opciones:
                    motivo_parada = "limite_repeticiones_alcanzado"
                    break
                azar = random.random()
                if azar < self.temperatura:
                    proximo = max(opciones, key=lambda o: prio_activa.get(o, 0))
                    metodo = "mayor_prioridad"
                else:
                    proximo = random.choice(opciones)
                    metodo = "aleatorio"
                pasos.append({"indice": indice, "desde": actual,
                              **resumen_opciones(opciones, prio_activa),
                              "azar": azar, "temperatura": self.temperatura,
                              "metodo": metodo, "elegida": proximo})
                res.append(proximo)
                conteo_palabras[proximo] = conteo_palabras.get(proximo, 0) + 1
                actual = proximo
                if actual.lower() in self.conceptos_clave and len(res) >= self.palabras_minimas_para_parar:
                    motivo_parada = "concepto_clave_alcanzado"
                    break
            bruto = " ".join(res) if res else self.diccionario.get(enfoque, "sistema analizando")
            # Solo se ofrece continuar cuando se alcanza un concepto clave.
            if motivo_parada == "concepto_clave_alcanzado":
                self.estado_respuesta = {
                    "memoria": mem_activa,
                    "prioridades": prio_activa,
                    "actual": actual,
                    "conteo_palabras": conteo_palabras,
                    "max_repeticiones_palabra": self.max_repeticiones_palabra,
                    "res": res,
                    "pasos_totales": len(res),
                    "enfoque": enfoque,
                    "pendiente": True,
                    "motivo_parada": motivo_parada
                }
            else:
                self.estado_respuesta = None

            if traza is not None:
                traza["respuesta"].update({"ruta": "cadena_markov", "enfoque": enfoque,
                                          "prioridad_enfoque": prio_activa.get(enfoque, 0),
                                          "pasos_cadena": pasos, "motivo_parada": motivo_parada,
                                          "palabras_generadas": list(res), "texto_pre_personalidad": bruto,
                                          "limite_repeticiones_por_palabra": self.max_repeticiones_palabra,
                                          "continuacion_disponible": self.estado_respuesta is not None})

        # Si la operación aparece dentro de una frase, adjunta ambos resultados.
        if calculo is not None and not es_puro:
            bruto_final = f"{calculo} | {self.aplicar_personalidad(bruto)}"
        else:
            bruto_final = self.aplicar_personalidad(bruto)
        if traza is not None:
            traza["respuesta"]["texto_final"] = bruto_final
        return bruto_final

    def continuar_respuesta(self, traza=None):
        """Continúa la misma cadena de Markov desde su última palabra."""
        estado = self.estado_respuesta
        if not estado or not estado.get("pendiente"):
            return None

        memoria = estado["memoria"]
        prioridades = estado["prioridades"]
        actual = estado["actual"]
        conteo_palabras = estado["conteo_palabras"]
        max_repeticiones = estado.get("max_repeticiones_palabra", self.max_repeticiones_palabra)
        res = estado["res"]
        pasos = []
        motivo = "limite_continuacion"

        for indice in range(self.max_pasos_continuacion):
            if actual not in memoria:
                motivo = "clave_sin_memoria"
                break

            opciones = [
                o for o in memoria[actual]
                if o and conteo_palabras.get(o, 0) < max_repeticiones
            ]
            if not opciones:
                motivo = "limite_repeticiones_alcanzado"
                break

            azar = random.random()
            if azar < self.temperatura:
                proximo = max(opciones, key=lambda o: prioridades.get(o, 0))
                metodo = "mayor_prioridad"
            else:
                proximo = random.choice(opciones)
                metodo = "aleatorio"

            pasos.append({
                "indice_continuacion": indice,
                "desde": actual,
                **resumen_opciones(opciones, prioridades),
                "azar": azar,
                "temperatura": self.temperatura,
                "metodo": metodo,
                "elegida": proximo
            })
            res.append(proximo)
            conteo_palabras[proximo] = conteo_palabras.get(proximo, 0) + 1
            actual = proximo
            estado["pasos_totales"] += 1

            if actual.lower() in self.conceptos_clave and len(res) >= self.palabras_minimas_para_parar:
                motivo = "concepto_clave_alcanzado"
                break

        estado["actual"] = actual
        estado["conteo_palabras"] = conteo_palabras
        estado["res"] = res
        estado["motivo_parada"] = motivo
        estado["pendiente"] = (motivo == "concepto_clave_alcanzado")

        bruto = " ".join(res)
        final = self.aplicar_personalidad(bruto)

        if traza is not None:
            traza.setdefault("continuaciones", []).append({
                "pasos": pasos,
                "palabras_nuevas": [p["elegida"] for p in pasos],
                "limite_repeticiones_por_palabra": max_repeticiones,
                "conteo_palabras": dict(conteo_palabras),
                "motivo_parada": motivo,
                "pasos_totales": estado["pasos_totales"],
                "pendiente": estado["pendiente"],
                "texto_pre_personalidad": bruto,
                "texto_final": final
            })

        if not estado["pendiente"]:
            self.estado_respuesta = None

        return final

    def guardar_indestructible(self):
        if self.dirty:
            try:
                escribir_seguro(self.archivo_dicc, [f"{k} :: {v}" for k, v in self.diccionario.items()])
                escribir_seguro(self.archivo_memoria, [f"{k}>{','.join(v)}" for k, v in self.memoria.items()])
                escribir_seguro(self.archivo_pesos, [f"{k} :: {v}" for k, v in self.prioridades.items()])
                self.dirty = False
            except Exception as e:
                print(f"[sys]: no se pudo guardar la memoria global: {e}")
        if self.dirty_usuario and self.nivel_usuario == 1:
            try:
                escribir_seguro(self.archivo_memoria_usuario, [f"{k}>{','.join(v)}" for k, v in self.memoria_usuario.items()])
                escribir_seguro(self.archivo_pesos_usuario, [f"{k} :: {v}" for k, v in self.prioridades_usuario.items()])
                self.dirty_usuario = False
            except Exception as e:
                print(f"[sys]: no se pudo guardar la memoria de usuario: {e}")

    def contar_mensaje_y_autoguardar(self):
        """Cuenta un mensaje y guarda cada autosave_cada mensajes."""
        self.mensajes_sin_guardar += 1
        if self.mensajes_sin_guardar >= self.autosave_cada:
            self.guardar_indestructible()
            self.mensajes_sin_guardar = 0


async def main():
    arcs = ARCS()
    arcs.servidor_registro = iniciar_registro_web(arcs.ruta_base)
    try:
        await bucle_principal(arcs)
    finally:
        arcs.guardar_indestructible()
        if arcs.servidor_registro is not None:
            arcs.servidor_registro.apagar()


async def bucle_principal(arcs):
    usuario_input = input("Identidad del usuario: ")
    clave = getpass.getpass("Clave de creador: ") if usuario_input.lower().strip() == "legnar" else None
    arcs.establecer_usuario(usuario_input, clave)
    print(f"Sesión iniciada como: {arcs.usuario_actual} (nivel {arcs.nivel_usuario}); versión {controls.version}/{controls.versiont}; interfaz {controls.interfaz}/{controls.interfazt}")
    print("Advertencia: ARCS es una IA estadística, no un LLM, y está en pruebas. Aunque sus respuestas parezcan humanas, no tiene conocimiento ni experiencias propias. Su uso es responsabilidad del usuario. LPP no se hace responsable de daños por mal funcionamiento.")
    an = "-" * 32
    anin = "_" * 32
    anb = "-" * 8
    ancxb = "-" * 4
    comandos = ("/ayuda", "/estoy perdido", "/traza on", "/traza off",
                "/traza estado", "/status", "/personas", "/olvidar <nombre>", "/permisos", "/permiso <nombre> on|off",
                "salir", "exit", "off=modelo")
    while True:
        try:
            u = await asyncio.to_thread(input, f"[{arcs.usuario_actual}]: ")
            if u.lower() in ["exit", "salir", "off=modelo"]: 
                break
                
            if u.lower() == "/ayuda":
                print(anin)
                print(f"Comandos disponibles: {', '.join(comandos)}")
                print(an)
                continue
            if u.lower() == "/estoy perdido":
                print(anin)
                print(f"ARCS fue creada por _LegNar.4.4.4.4// de Srangel. Su uso es responsabilidad de {arcs.usuario_actual} o de su responsable legal. ARCS puede equivocarse o usar lenguaje ofensivo. LPP y Srangel no se hacen responsables de daños. Al descargar y ejecutar el programa, usted aceptó las condiciones y políticas de seguridad y privacidad. Si ya no está de acuerdo, elimine la carpeta de ARCS siguiendo las instrucciones oficiales.")
                print(an)
                continue
                    

            if u.lower() == "/traza on":
                arcs.trazabilidad_activa = True
                print("Trazabilidad activada.")
                continue

            if u.lower() == "/traza off":
                arcs.trazabilidad_activa = False
                print("Trazabilidad desactivada.")
                continue

            if u.lower() == "/traza estado":
                estado = "activa" if arcs.trazabilidad_activa else "desactivada"
                print(f"Trazabilidad: {estado}")
                print(f"Archivo: {os.path.join(arcs.ruta_base, 'trazas_arcs.jsonl')}")
                continue

            if u.lower() == "/status":
                
                
                print(anin)
                print("")
                print(ancxb + "----" + "estado del usuario" + ancxb + "---")
                print(anin)
                print(f"Usuario: {arcs.usuario_actual}")
                print(f"Nivel: {arcs.nivel_usuario}")
                print(f"ID de usuario: {arcs.id_usuario or 'no asignado'}")
                
                print(an)
                print(anin)
                print(anb + "estado de ARCS" + anb)
                print(an)
                print(f"Temperatura de generación: {arcs.temperatura}")
                print(f"Personalidad: {arcs.personalidad}")
                print(an)
                print(f"Capas: {arcs.capas}")
                print(f"Palabras en memoria: {len(arcs.memoria)}")
                print(anin)
                continue

            if u.lower() == "/personas":
                print(anin)
                print(arcs.listar_personas())
                print(an)
                continue
            if u.lower() == "/permisos":
                print(arcs.texto_permisos())
                continue
            if u.lower().startswith("/permiso"):
                print(arcs.cambiar_permiso_cmd(u))
                continue
            if u.lower().split(" ", 1)[0] == "/olvidar":
                print(arcs.olvidar_persona(u.split(" ", 1)[1].strip() if " " in u else ""))
                continue

            traza = None
            if arcs.trazabilidad_activa and arcs.permiso("guardar_trazas"):
                traza = {
                    "id_sesion": arcs.id_sesion,
                    "fecha_inicio": datetime.datetime.now().isoformat(timespec="microseconds"),
                    "usuario": arcs.usuario_actual,
                    "id_usuario": arcs.id_usuario,
                    "nivel_usuario": arcs.nivel_usuario,
                    "entrada_original": u,
                    "version": f"{controls.version}/{controls.versiont}"
                }
            respuesta = arcs.procesar_personas(u, traza)
            if respuesta is None:
                arcs.aprender(u, traza)
                respuesta = arcs.responder(u, traza)
            print(f"[ARCS]: {respuesta}")

            # Si el freno fue un concepto clave, el usuario decide si continua.
            while arcs.estado_respuesta is not None and arcs.estado_respuesta.get("pendiente"):
                try:
                    decision = await asyncio.to_thread(
                        input, "¿Continuar respuesta? (s/n): "
                    )
                except KeyboardInterrupt:
                    decision = "n"

                if decision.strip().lower() not in ("s", "si", "sí"):
                    if traza is not None:
                        traza.setdefault("continuaciones", []).append({
                            "accion": "usuario_detiene",
                            "pasos_totales": arcs.estado_respuesta.get("pasos_totales", 0)
                        })
                    arcs.estado_respuesta = None
                    print("[sys]: Respuesta finalizada por el usuario.")
                    break

                respuesta = arcs.continuar_respuesta(traza)
                if respuesta is None:
                    print("[sys]: No hay continuación disponible.")
                    break
                print(f"[ARCS]: {respuesta}")
                if arcs.estado_respuesta is None:
                    print("[sys]: Continuación terminada: " +
                          (traza.get("continuaciones", [{}])[-1].get("motivo_parada", "fin" ) if traza is not None else "fin"))

            if traza is not None:
                traza["fecha_fin"] = datetime.datetime.now().isoformat(timespec="microseconds")
                traza["respuesta_final"] = respuesta
                arcs.trazador.registrar(traza)
            
            tiempo = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            rtir= "sys: tiempo en que arcs respondio: "+tiempo + " total time:  ==>"
            
            
            rco= inflog(arcs.ruta_base+"logr.txt")
            rco.write(rtir+respuesta+"\n")
            rco.close()
            print(rtir+respuesta)
            arcs.contar_mensaje_y_autoguardar()
        except KeyboardInterrupt: 
            break

if __name__ == "__main__":
    asyncio.run(main())
