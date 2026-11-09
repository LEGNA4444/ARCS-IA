# -*- coding: utf-8 -*-
"""
personas.py - Fichas de personas para ARCS (sin librerias externas).

Idea central: cuando alguien habla de una persona, ARCS guarda el dato COMPLETO
(la frase tal cual la dijeron) en la ficha de esa persona, en vez de romperlo en
pares de palabras como hace la cadena de Markov. Asi, al preguntar por la
persona, la respuesta sale entera y no mezclada con otras frases.

Este modulo no depende de ARCS.py para poder probarse solo:
  - FichasPersonas: guarda y lee las fichas en un archivo JSON.
  - clasificar(): decide si un mensaje es una afirmacion sobre una persona,
    una pregunta sobre una persona, una pregunta normal u otra cosa.
  - redactar_respuesta(): arma la respuesta a partir de una ficha.

Todo funciona con reglas (no adivina): ante la duda NO trata el mensaje como
persona, y entonces ARCS sigue su flujo de siempre.
"""
import datetime
import json
import os
import re
import shutil
import unicodedata

MAX_CHARS_HECHO = 1000     # Largo maximo de un dato guardado
MAX_HECHOS_PERSONA = 100   # Si una persona pasa de aqui se descartan los mas viejos
MAX_HECHOS_RESPUESTA = 5   # Cuantos datos se muestran en una respuesta

_PUNT = " .,;:!?¿¡\"'()"


# =============================================================================
# TEXTO: normalizar sin cambiar el largo (asi podemos recortar el original)
# =============================================================================
def _base(c):
    """Una letra -> minuscula sin acento (conserva la enie). Siempre devuelve 1 caracter."""
    if c in "ñÑ":
        return "ñ"
    d = "".join(x for x in unicodedata.normalize("NFD", c.lower())
                if unicodedata.category(x) != "Mn")
    return d if len(d) == 1 else (c.lower()[:1] or c)


def normalizar(texto):
    """Minusculas y sin acentos, con el MISMO largo que el original."""
    return "".join(_base(c) for c in texto)


def clave(texto):
    """Clave para comparar nombres y datos: sin acentos, sin signos, espacios simples."""
    t = re.sub(r"[^a-z0-9ñ ]+", "", normalizar(texto))
    return re.sub(r"\s+", " ", t).strip()


# =============================================================================
# LISTAS DE PALABRAS (ajustables)
# =============================================================================
def _alt(palabras):
    """Alternancia regex con las frases mas largas primero."""
    return "|".join(re.sub(r"\s+", r"\\s+", p) for p in sorted(palabras, key=len, reverse=True))


_RELACIONES = set("""mama madre papa padre hermano hermana hijo hija esposo esposa marido novio novia pareja
abuelo abuela tio tia primo prima sobrino sobrina cuñado cuñada suegro suegra yerno nuera amigo amiga compadre
comadre vecino vecina jefe jefa compañero compañera socio socia maestro maestra profesor profesora""".split())

# Palabras que describen a una persona ("Garli es la encargada...", "Pedro es mi amigo")
_ROLES = _RELACIONES | set("""encargado encargada dueño dueña director directora gerente presidente presidenta doctor
doctora ingeniero ingeniera abogado abogada contador contadora programador programadora empleado empleada trabajador
trabajadora fundador fundadora creador creadora persona alumno alumna estudiante medico medica enfermero enfermera
piloto artista cantante jugador jugadora mecanico mecanica cocinero cocinera chofer policia soldado militar lider
candidato candidata senador senadora diputado diputada secretario secretaria asistente administrador administradora
supervisor supervisora vendedor vendedora hombre mujer chico chica muchacho muchacha joven señor señora licenciado
licenciada niño niña""".split())

_TITULOS = set("""don doña doctor doctora dr dra licenciado licenciada lic ingeniero ingeniera ing profesor profesora
profe maestro maestra señor señora sr sra""".split())

_COPULAS = ["es", "era", "fue", "sera"]
# Verbos que solo se usan con personas: si aparecen, el sujeto es una persona
_ANIMADOS = ["se llama", "se llamaba", "trabaja", "trabajaba", "nacio", "murio", "fallecio", "estudia", "estudiaba",
             "se caso", "cumple", "vive", "vivia", "le gusta", "le gustan", "le encanta", "le encantan", "odia",
             "ama", "quiere", "prefiere", "juega", "jugaba", "canta", "toca", "escribe", "se dedica", "se dedicaba",
             "se encarga", "sabe", "conoce", "cuida", "ayuda", "dice", "piensa", "cree", "siente"]
_ANIMADOS_SET = set(_ANIMADOS)
_COPULAS_SET = set(_COPULAS)

# Primera palabra de un "nombre" que en realidad no puede serlo
_NO_NOMBRE = set("""el la los las un una unos unas este esta estos estas ese esa esos esas eso esto aquel aquella
yo tu usted ella ellos ellas nosotros nosotras mi mis su sus me te se lo le les nos
quien quienes que como cuando donde cual cuales cuanto cuanta cuantos cuantas
y e o u ni pero si no ya muy mas menos mucho mucha muchos muchas poco poca pocos pocas todo toda todos todas
nadie alguien algo nada cada otro otra otros otras mismo misma varios varias algunos algunas
hola hey oye aqui alli ahi hoy ayer mañana ahora luego despues antes siempre nunca tambien
porque aunque mientras entonces bueno claro gracias arcs""".split())

# Palabras que terminan un nombre ("Garli en la oficina" -> "Garli")
_STOP_NOMBRE = set("""y e o que en con es era fue trabaja vive tiene tambien pero ya porque cuando donde pues
entonces por para a al desde hasta sobre entre""".split())

_PARTICULAS = {"de", "del", "la", "las", "los", "van", "von"}

_RE_PRIMERA = re.compile(r"\b(?:mi|mis|mio|mia|mios|mias|me|yo|conmigo|nuestro|nuestra|nuestros|nuestras|nos)\b")

_RE_ROL_PRED = re.compile(
    r"^(?:(?:el|la|un|una|mi|su|tu)\s+)?(?:(?:muy|bien|buen|buena|gran|mejor|nuevo|nueva|ex)\s+)*(?:"
    + "|".join(sorted(_ROLES, key=len, reverse=True)) + r")\b")

# "Mexico es un pais", "LPP es una empresa": cosas que no son personas
_RE_NO_PERSONA = re.compile(
    r"^(?:un|una|el|la)\s+(?:pais|ciudad|estado|municipio|empresa|compañia|marca|lugar|pueblo|region|continente|rio|"
    r"montaña|isla|capital|republica|organizacion|institucion|escuela|universidad|banco|tienda|restaurante|equipo|"
    r"partido|grupo|banda|pelicula|serie|libro|cancion|juego|app|aplicacion|sistema|programa|idioma|lengua|palabra|"
    r"concepto|dia|fecha|animal|perro|gato|cosa|objeto)\b")

_RE_PREFIJO = re.compile(
    r"^(?:(?:" + _alt(["hola", "hey", "oye", "ey", "que onda", "buenas", "buen dia", "buenos dias",
                       "buenas tardes", "buenas noches"]) + r")[,.!]?\s+)?"
    r"(?:arcs[,:.]?\s+)?"
    r"(?:(?:" + _alt(["sabias que", "sabes que", "te cuento que", "te digo que", "quiero que sepas que",
                      "ten en cuenta que", "recuerda que", "fijate que", "dato curioso", "por cierto",
                      "mira", "dato"]) + r")[,:]?\s+)?")

_VERBOS_ALT = _alt(_COPULAS + _ANIMADOS) + r"|tiene(?=\s+\d{1,3}\s+años)"
_RE_VERBO = re.compile(r"^(?P<suj>.+?)\s+(?P<v>" + _VERBOS_ALT + r")\b\s*(?P<resto>.*)$")
_RE_SE_LLAMA = re.compile(
    r"^(?:mi|mis|el|la)\s+(?:" + "|".join(sorted(_ROLES, key=len, reverse=True)) + r")"
    r"(?:\s+\S+){0,2}?\s+(?P<v>se\s+llama|es|era|fue)\s+(?P<resto>.+)$")

_RE_INTERROG = re.compile(
    r"^(?:" + _alt(["quien", "quienes", "que", "como", "cuando", "donde", "adonde", "cual", "cuales", "cuanto",
                    "cuanta", "cuantos", "cuantas", "por que", "para que", "en que", "a que", "de que",
                    "con quien", "de quien", "a quien", "conoces", "hablame", "cuentame", "dime",
                    "platicame"]) + r")\b")

# Preguntas sobre personas: (regex, atributo, fuerte)
#  - fuerte: el verbo implica una persona ("donde vive X"), se acepta aunque X este en minusculas
#  - debil: ("que sabes de X") solo se acepta si X ya se conoce o esta en mayuscula
_DE = r"(?:de|sobre|acerca\s+de)"
_PREGUNTAS = [
    (r"^(?:quien|quienes)\s+(?:es|era|fue|sera|son)\s+(?P<n>.+)$", None, True),
    (r"^(?:sabes|sabias|sabe)\s+(?:quien|quienes)\s+(?:es|era|fue|son)\s+(?P<n>.+)$", None, True),
    (r"^(?:conoces|conoce|conocias)\s+(?:a\s+)?(?P<n>.+)$", None, True),
    (r"^(?:a\s+que\s+se\s+dedica|a\s+que\s+se\s+dedicaba|que\s+hace|en\s+que\s+trabaja|de\s+que\s+trabaja|"
     r"donde\s+trabaja)\s+(?P<n>.+)$", "trabajo", True),
    (r"^(?:donde\s+vive|donde\s+vivia|en\s+donde\s+vive)\s+(?P<n>.+)$", "vivienda", True),
    (r"^(?:cuantos\s+años\s+tiene|que\s+edad\s+tiene|cuando\s+nacio|cuando\s+cumple\s+años|cuando\s+cumple)"
     r"\s+(?P<n>.+)$", "edad", True),
    (r"^(?:que\s+le\s+gusta\s+a|a\s+que\s+le\s+gusta|que\s+le\s+gusta\s+hacer\s+a)\s+(?P<n>.+)$", "gustos", True),
    (r"^(?:que|cuanto)\s+(?:sabes|sabe|sabias|me\s+puedes\s+decir|puedes\s+decirme|me\s+dices|me\s+cuentas|"
     r"puedes\s+contarme)\s+" + _DE + r"\s+(?P<n>.+)$", None, False),
    (r"^(?:hablame|cuentame|dime|platicame|informame|describeme)\s+(?:algo\s+|todo\s+|lo\s+que\s+sabes\s+)?"
     + _DE + r"\s+(?P<n>.+)$", None, False),
    (r"^(?:me\s+)?(?:puedes|podrias)\s+(?:hablar|contarme|decirme|platicarme)\s+(?:algo\s+)?" + _DE
     + r"\s+(?P<n>.+)$", None, False),
]
_PREGUNTAS = [(re.compile(p), a, f) for p, a, f in _PREGUNTAS]

# Para filtrar datos cuando preguntan algo puntual ("donde vive X")
ATRIBUTOS = {
    "trabajo": r"trabaj|encarg|dedic|jefe|jefa|puesto|cargo|empresa|profesion|ingenier|doctor|maestr|director|gerente|dueñ",
    "vivienda": r"\bviv|casa|ciudad|direccion|colonia|barrio|radica",
    "edad": r"\b\d{1,3}\s+años|edad|nacio|cumple|nacimiento",
    "gustos": r"gusta|encanta|odia|\bama\b|prefier|favorit|aficion",
}


# =============================================================================
# FICHAS: guardado en JSON
# =============================================================================
class FichasPersonas:
    """
    Una ficha por persona:
      {"garli": {"nombre": "Garli", "hechos": [{"texto": ..., "forma": "predicado"|"oracion",
                  "primera_persona": bool, "original": ..., "dijo": ..., "fecha": ...}], ...}}
    """

    def __init__(self, ruta, max_hechos=MAX_HECHOS_PERSONA, max_chars=MAX_CHARS_HECHO):
        self.ruta = ruta
        self.max_hechos = max_hechos
        self.max_chars = max_chars
        self.personas = {}
        self.cargar()

    # ---- disco ----
    def cargar(self):
        for r in (self.ruta, self.ruta + ".bak"):
            try:
                with open(r, "r", encoding="utf-8") as f:
                    datos = json.load(f)
            except (OSError, ValueError):
                continue
            if isinstance(datos, dict):
                self.personas = {k: v for k, v in datos.items()
                                 if isinstance(v, dict) and isinstance(v.get("hechos"), list)}
                return
        self.personas = {}

    def guardar(self, respaldar=True):
        """Escribe en un .tmp y luego reemplaza; el respaldo solo se hace si el actual es JSON valido."""
        carpeta = os.path.dirname(self.ruta)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        tmp = self.ruta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.personas, f, ensure_ascii=False, indent=1)
        if respaldar and os.path.exists(self.ruta):
            try:
                with open(self.ruta, "r", encoding="utf-8") as f:
                    json.load(f)
                shutil.copy(self.ruta, self.ruta + ".bak")
            except (OSError, ValueError):
                pass
        os.replace(tmp, self.ruta)

    # ---- busqueda ----
    def resolver(self, nombre):
        """
        Devuelve (clave, candidatos). 'garli' encuentra a 'garli perez' si es la unica.
        Si hay varias coincidencias, clave es None y candidatos las lista.
        """
        k = clave(nombre)
        if not k:
            return None, []
        if k in self.personas:
            return k, [k]
        palabras = set(k.split())
        cands = [c for c in self.personas if palabras <= set(c.split())]
        return (cands[0], cands) if len(cands) == 1 else (None, cands)

    def nombres(self):
        return sorted(p.get("nombre", k) for k, p in self.personas.items())

    # ---- cambios ----
    def agregar_hecho(self, nombre, texto, original, dijo, forma="predicado", primera_persona=False):
        k = clave(nombre)
        texto = (texto or "").strip()[:self.max_chars]
        if not k or not texto:
            return {"estado": "invalido"}
        ahora = datetime.datetime.now().isoformat(timespec="seconds")
        persona = self.personas.get(k)
        if persona is None:
            # Si 'garli' ya existe como 'garli perez' (unica coincidencia), se agrega a esa ficha
            k2, cands = self.resolver(nombre)
            if k2:
                k, persona = k2, self.personas[k2]
            elif len(cands) > 1:
                return {"estado": "ambiguo", "candidatos": [self.personas[c]["nombre"] for c in cands]}
        nueva_persona = persona is None
        if persona is not None:
            nuevo = clave(texto)
            if any(clave(h.get("texto", "")) == nuevo for h in persona["hechos"]):
                return {"estado": "repetido", "clave": k, "nombre": persona["nombre"], "guardado": True}
        else:
            persona = {"nombre": nombre.strip(), "hechos": [], "creado": ahora}
            self.personas[k] = persona
        persona["hechos"].append({
            "texto": texto, "forma": forma, "primera_persona": bool(primera_persona),
            "original": (original or "").strip()[:self.max_chars], "dijo": dijo, "fecha": ahora})
        if len(persona["hechos"]) > self.max_hechos:
            del persona["hechos"][:len(persona["hechos"]) - self.max_hechos]
        persona["actualizado"] = ahora
        guardado = True
        try:
            self.guardar()
        except OSError:
            guardado = False
        return {"estado": "persona_nueva" if nueva_persona else "dato_nuevo", "clave": k,
                "nombre": persona["nombre"], "guardado": guardado}

    def olvidar(self, k):
        """Borra una ficha completa. Tambien borra el respaldo para que el dato no quede escondido ahi."""
        if k not in self.personas:
            return False
        del self.personas[k]
        try:
            self.guardar(respaldar=False)
            if os.path.exists(self.ruta + ".bak"):
                os.remove(self.ruta + ".bak")
        except OSError:
            pass
        return True


# =============================================================================
# CLASIFICADOR DE MENSAJES
# =============================================================================
def _es_token_nombre(t):
    return bool(re.fullmatch(r"[a-zñ][a-zñ\-']*", t)) and t not in _NO_NOMBRE and t not in _STOP_NOMBRE


def _nombre_bonito(tokens_raw):
    """'garli' -> 'Garli'. Si ya venia con mayusculas se respeta tal cual."""
    if all(t == t.lower() for t in tokens_raw):
        return " ".join(t if clave(t) in _PARTICULAS else t.capitalize() for t in tokens_raw)
    return " ".join(tokens_raw)


def _recortar(r, n):
    """Quita espacios y puntuacion de los extremos en el original (r) y el normalizado (n) a la vez."""
    ini = len(n) - len(n.lstrip())
    fin = len(n.rstrip(" \t\n.,;!"))
    return r[ini:fin], n[ini:fin]


def _extraer_nombre(raw, n, ini=0, max_tokens=3):
    """Toma el nombre que empieza en 'ini'. Devuelve la lista de palabras del original ([] si no hay nombre)."""
    toks = [(m.start(), m.end()) for m in re.finditer(r"\S+", n) if m.start() >= ini]
    nombre, normas = [], []
    for i, (a, b) in enumerate(toks):
        t = n[a:b].strip(_PUNT)
        if t in _PARTICULAS and nombre:
            j = i + 1
            while j < len(toks) and n[toks[j][0]:toks[j][1]].strip(_PUNT) in _PARTICULAS:
                j += 1
            if j < len(toks) and _es_token_nombre(n[toks[j][0]:toks[j][1]].strip(_PUNT)):
                nombre.append(raw[a:b].strip(_PUNT))
                normas.append(t)
                continue
            break
        if not _es_token_nombre(t):
            break
        if sum(1 for x in normas if x not in _PARTICULAS) >= max_tokens:
            break
        nombre.append(raw[a:b].strip(_PUNT))
        normas.append(t)
        if n[a:b][-1] in ",.;:":
            break
    while normas and normas[-1] in _PARTICULAS:
        normas.pop()
        nombre.pop()
    return nombre


def _nombre_valido(norm):
    """norm: lista de palabras normalizadas. Valida que parezcan un nombre de persona."""
    if not 1 <= len(norm) <= 5:
        return False
    nucleo = [t for t in norm if t not in _PARTICULAS]
    if not nucleo or norm[0] in _PARTICULAS or norm[-1] in _PARTICULAS:
        return False
    return all(_es_token_nombre(t) for t in nucleo)


def _sujeto_persona(suj_r, suj_n):
    """Analiza lo que va antes del verbo. Devuelve dict con el nombre o None si no parece persona."""
    toks = [(suj_r[m.start():m.end()], m.group()) for m in re.finditer(r"\S+", suj_n)]
    if not toks or len(toks) > 6:
        return None
    relacion = titulo = False
    if len(toks) >= 3 and toks[0][1] in ("mi", "mis") and toks[1][1] in _RELACIONES:
        toks, relacion = toks[2:], True                   # "mi amigo Pedro"
    elif len(toks) >= 2 and toks[0][1] in ("el", "la") and toks[1][1] in _TITULOS:
        toks, titulo = toks[1:], True                     # "el doctor Perez"
    elif len(toks) >= 2 and toks[0][1] in _TITULOS:
        titulo = True                                     # "doña Rosa"
    raw = [t[0].strip(_PUNT) for t in toks]
    norm = [t[1].strip(_PUNT) for t in toks]
    if not _nombre_valido(norm):
        return None
    return {"raw": raw, "norm": norm, "relacion": relacion, "titulo": titulo}


def _parsear_pregunta_persona(r, n, es_conocida, no_personas):
    for rx, atributo, fuerte in _PREGUNTAS:
        m = rx.match(n)
        if not m:
            continue
        nombre = _extraer_nombre(r, n, m.start("n"))
        if not nombre:
            continue
        norm = " ".join(normalizar(t) for t in nombre)
        conocida = es_conocida(norm)
        if (norm in no_personas or norm.split()[0] in no_personas) and not conocida:
            continue
        mayuscula = nombre[0][:1].isupper() and not nombre[0].isupper()
        titulo = norm.split()[0] in _TITULOS
        if not (fuerte or conocida or mayuscula or titulo):
            continue
        return {"tipo": "pregunta_persona", "persona": _nombre_bonito(nombre), "atributo": atributo,
                "patron": "fuerte" if fuerte else "debil"}
    return None


def _armar_afirmacion(nombre_raw, hecho, oracion_completa, forzar_oracion, patron, n_oracion):
    primera = bool(_RE_PRIMERA.search(n_oracion))
    usar_oracion = primera or forzar_oracion
    return {"tipo": "afirmacion_persona", "persona": _nombre_bonito(nombre_raw),
            "hecho": (oracion_completa if usar_oracion else hecho).strip(),
            "forma": "oracion" if usar_oracion else "predicado",
            "primera_persona": primera, "patron": patron}


def _afirmacion_con_verbo(r2, n2, inicio, es_conocida, no_personas):
    """'<sujeto> <verbo> <resto>' donde el sujeto parezca una persona. None si no lo parece."""
    m = _RE_VERBO.match(n2)
    if not m:
        return None
    info = _sujeto_persona(r2[:m.end("suj")], m.group("suj"))
    if not info:
        return None
    norm = " ".join(info["norm"])
    conocida = es_conocida(norm)
    if (norm in no_personas or info["norm"][0] in no_personas) and not conocida:
        return None
    if info["raw"][0].isupper() and len(info["raw"][0]) > 1 and not conocida:
        return None                                        # siglas: LPP, SAT...
    verbo = re.sub(r"\s+", " ", m.group("v"))
    copula = verbo in _COPULAS_SET
    animado = verbo in _ANIMADOS_SET or verbo == "tiene"
    pred = m.group("resto")
    cue_rol = copula and bool(_RE_ROL_PRED.match(pred))
    entidad = copula and bool(_RE_NO_PERSONA.match(pred))
    capital_medio = (not inicio) and info["raw"][0][:1].isupper()
    if conocida:
        patron = "conocida"
    elif info["relacion"]:
        patron = "relacion"
    elif info["titulo"]:
        patron = "titulo"
    elif animado:
        patron = "verbo_de_persona"
    elif cue_rol:
        patron = "rol"
    elif capital_medio and copula and not entidad:
        patron = "mayuscula"
    else:
        return None
    return _armar_afirmacion(info["raw"], r2[m.start("v"):], r2, info["relacion"], patron, n2)


def _parsear_afirmacion(r2, n2, inicio, es_conocida, no_personas):
    if not n2:
        return None

    # (a) "mi mama se llama Rosa", "el jefe se llama Luis", "mi jefe es Pedro"
    m = _RE_SE_LLAMA.match(n2)
    if m:
        nombre = _extraer_nombre(r2, n2, m.start("resto"))
        if nombre and (m.group("v").startswith("se") or nombre[0][:1].isupper()):
            norm = " ".join(normalizar(t) for t in nombre)
            if norm not in no_personas or es_conocida(norm):
                return _armar_afirmacion(nombre, r2, r2, True, "se_llama", n2)

    # (b) "<sujeto> <verbo> <resto>" con un verbo de la lista (se prueba primero porque lee el
    #     nombre completo: asi "Garli Soto trabaja..." no se confunde con "Garli")
    res = _afirmacion_con_verbo(r2, n2, inicio, es_conocida, no_personas)
    if res:
        return res

    # (c) el mensaje empieza con una persona que ya conozco y el verbo no esta en la lista:
    #     lo que siga es un dato suyo ("rosa compro un carro"). Si despues del nombre viene otra
    #     palabra en mayuscula, probablemente es un apellido distinto y NO se acepta.
    toks = [(m2.start(), m2.end()) for m2 in re.finditer(r"\S+", n2)]
    for k in (3, 2, 1):
        if len(toks) > k and n2[toks[0][0]:toks[0][1]].strip(_PUNT) not in _NO_NOMBRE:
            cand = clave(n2[:toks[k - 1][1]])
            if cand and es_conocida(cand) and not r2[toks[k][0]:][:1].isupper():
                return _armar_afirmacion(r2[:toks[k - 1][1]].split(), r2[toks[k][0]:], r2, False, "conocida", n2)
    return None


def clasificar(texto, es_conocida=None, no_personas=frozenset()):
    """
    Decide que tipo de mensaje es. Devuelve un dict con "tipo":
      - "afirmacion_persona": se dice algo de una persona  -> persona, hecho, forma, primera_persona
      - "pregunta_persona":   se pregunta por una persona   -> persona, atributo
      - "pregunta_general":   pregunta o peticion normal    (no es sobre una persona)
      - "otro":               cualquier otra cosa
    es_conocida(nombre_normalizado) -> bool avisa si ya existe una ficha con ese nombre.
    no_personas: palabras que nunca son nombres de persona (ej. conceptos clave como 'mexico').
    """
    es_conocida = es_conocida or (lambda nombre: False)
    raw = (texto or "").strip()
    if not raw:
        return {"tipo": "otro"}
    n = normalizar(raw)
    m = _RE_PREFIJO.match(n)
    off = m.end() if m else 0
    r2, n2 = _recortar(raw[off:], n[off:])
    n2q = re.sub(r"[¿?¡!]", " ", n2)
    r2q, n2q = _recortar(r2, n2q)

    res = _parsear_pregunta_persona(r2q, n2q, es_conocida, no_personas)
    if res:
        return res
    if "?" in raw or "¿" in raw or _RE_INTERROG.match(n2q):
        return {"tipo": "pregunta_general"}
    res = _parsear_afirmacion(r2, n2, off == 0, es_conocida, no_personas)
    return res or {"tipo": "otro"}


# =============================================================================
# RESPUESTAS
# =============================================================================
def _frase(h, nombre, usuario):
    texto = h.get("texto", "").strip().rstrip(" .")
    if h.get("primera_persona"):
        quien = h.get("dijo") or "alguien"
        if usuario and clave(quien) == clave(usuario):
            return f"Me contaste: «{texto}»."
        return f"{quien.capitalize()} comentó: «{texto}»."
    if h.get("forma") == "oracion":
        return texto[:1].upper() + texto[1:] + "."
    return f"{nombre} {texto}."


def redactar_respuesta(ficha, atributo=None, usuario=None, max_hechos=MAX_HECHOS_RESPUESTA):
    """Arma la respuesta con los datos guardados, tal cual se dijeron."""
    nombre, hechos = ficha["nombre"], ficha["hechos"]
    elegidos, aviso = hechos, ""
    if atributo in ATRIBUTOS:
        filtrados = [h for h in hechos if re.search(ATRIBUTOS[atributo], normalizar(h.get("texto", "")))]
        if filtrados:
            elegidos = filtrados
        else:
            return f"No tengo ese dato específico de {nombre}."
    mostrados = elegidos[-max_hechos:]
    texto = " ".join(_frase(h, nombre, usuario) for h in mostrados)
    faltan = len(elegidos) - len(mostrados)
    if faltan > 0:
        texto += f" (y {faltan} dato{'s' if faltan > 1 else ''} más)"
    return aviso + texto
