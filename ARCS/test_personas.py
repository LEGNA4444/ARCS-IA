import json
import os
import pytest

import ARCS as modulo_arcs
from ARCS import ARCS
from personas import FichasPersonas, clasificar, clave, normalizar, redactar_respuesta
from seguridad import hash_clave

NO = {"mexico", "amor", "patria", "bandera", "poder", "ley", "niña", "arcs", "lealtad", "respeto", "hombre", "mujer"}
FRASE_GARLI = ("sabias que Garli es la encargada economica y legal de LPP y Srangel esto significa que se "
               "encarga de el ambito financiero y orden general")
RESPUESTA_GARLI = ("Garli es la encargada economica y legal de LPP y Srangel esto significa que se encarga "
                   "de el ambito financiero y orden general.")


# ----------------------------------------------------------------------------
# Clasificador
# ----------------------------------------------------------------------------
CASOS = [
    # (texto, tipo, persona)  -- afirmaciones sobre personas
    (FRASE_GARLI, "afirmacion_persona", "Garli"),
    ("legnar es el jefe", "afirmacion_persona", "Legnar"),
    ("Garli trabaja en LPP", "afirmacion_persona", "Garli"),
    ("Pedro Pérez vive en Guadalajara", "afirmacion_persona", "Pedro Pérez"),
    ("Luis tiene 25 años", "afirmacion_persona", "Luis"),
    ("mi mamá se llama Rosa", "afirmacion_persona", "Rosa"),
    ("mi jefe es Pedro", "afirmacion_persona", "Pedro"),
    ("mi amigo Pedro trabaja en una escuela", "afirmacion_persona", "Pedro"),
    ("Rosa es mi mamá", "afirmacion_persona", "Rosa"),
    ("doña Lupe es muy amable", "afirmacion_persona", "doña Lupe"),
    ("Juan de la Cruz trabaja en el SAT", "afirmacion_persona", "Juan de la Cruz"),
    ("sabias que Pedro es alto", "afirmacion_persona", "Pedro"),
    # preguntas sobre personas
    ("quien es Garli?", "pregunta_persona", "Garli"),
    ("¿Quién es garli?", "pregunta_persona", "Garli"),
    ("hola arcs quien es Garli en la empresa", "pregunta_persona", "Garli"),
    ("conoces a Garli", "pregunta_persona", "Garli"),
    ("que sabes de Garli?", "pregunta_persona", "Garli"),
    ("hablame de Garli", "pregunta_persona", "Garli"),
    ("donde vive Pedro Pérez?", "pregunta_persona", "Pedro Pérez"),
    ("a que se dedica garli", "pregunta_persona", "Garli"),
    ("cuantos años tiene Luis", "pregunta_persona", "Luis"),
    # preguntas normales
    ("que es el amor?", "pregunta_general", None),
    ("hola como estas?", "pregunta_general", None),
    ("quien es el presidente de mexico", "pregunta_general", None),
    ("que sabes de mexico?", "pregunta_general", None),
    ("que sabes de la ley", "pregunta_general", None),
    ("hablame de python", "pregunta_general", None),
    ("quien eres", "pregunta_general", None),
    ("¿Cómo está el clima en Guadalajara?", "pregunta_general", None),
    ("quien es", "pregunta_general", None),
    # texto normal: NO debe detectarse como persona
    ("el amor es lealtad", "otro", None),
    ("mexico es un pais con historia", "otro", None),
    ("Mexico es un pais muy grande", "otro", None),
    ("sabias que Mexico es un pais muy grande", "otro", None),
    ("sabias que LPP es una empresa", "otro", None),
    ("arcs es una ia", "otro", None),
    ("la niña juega", "otro", None),
    ("hola arcs sabias que la niña juega juegos mexicanos es una cancha", "otro", None),
    ("estoy bien gracias me interesa saber", "otro", None),
    ("la patria es primero", "otro", None),
    ("esto es una prueba", "otro", None),
    ("5 mas 3", "otro", None),
    ("10**10**10", "otro", None),
    ("juega ruleta rusa", "otro", None),
    ("Todo es posible", "otro", None),
    ("Ella es mi mamá", "otro", None),
    ("El jefe es muy amable", "otro", None),
    ("Mexico tiene mucha historia", "otro", None),
    ("Garli y Pedro son amigos", "otro", None),
    ("Pedro", "otro", None),
    ("hola", "otro", None),
    ("", "otro", None),
]


@pytest.mark.parametrize("texto,tipo,persona", CASOS)
def test_clasificar(texto, tipo, persona):
    r = clasificar(texto, None, NO)
    assert r["tipo"] == tipo, r
    if persona:
        assert r["persona"] == persona


def test_hecho_de_garli_se_guarda_completo():
    r = clasificar(FRASE_GARLI, None, NO)
    assert r["hecho"] == ("es la encargada economica y legal de LPP y Srangel esto significa que se encarga "
                          "de el ambito financiero y orden general")
    assert r["forma"] == "predicado" and r["primera_persona"] is False


def test_persona_conocida_acepta_verbos_no_listados():
    conocidas = {"rosa"}
    r = clasificar("rosa compro un carro nuevo", lambda n: n in conocidas, NO)
    assert r["tipo"] == "afirmacion_persona" and r["hecho"] == "compro un carro nuevo"


def test_primera_persona_guarda_la_oracion_entera():
    r = clasificar("Rosa es mi mamá", None, NO)
    assert r["primera_persona"] is True and r["forma"] == "oracion" and r["hecho"] == "Rosa es mi mamá"


def test_que_sabes_de_minuscula_desconocida_es_general():
    assert clasificar("que sabes de pedro", None, NO)["tipo"] == "pregunta_general"
    assert clasificar("que sabes de pedro", lambda n: n == "pedro", NO)["tipo"] == "pregunta_persona"


def test_normalizar_conserva_largo_y_enie():
    for t in ["Ñandú", "Pérez", "İstanbul", "mañana", "😀 hola"]:
        assert len(normalizar(t)) == len(t)
    assert normalizar("Niña Pérez") == "niña perez"
    assert clave("  Pedro   PÉREZ! ") == "pedro perez"


def test_robustez_texto_basura():
    import random
    random.seed(3)
    alfabeto = "abcdeñ áéíó¿?¡!.,;:'-\t0123😀İ"
    palabras = ["es", "se llama", "quien", "Garli", "mi", "mama", "que", "sabes", "de", "conoces", "a", "tiene", "25", "años"]
    for _ in range(3000):
        t = ("".join(random.choice(alfabeto) for _ in range(random.randint(0, 50))) if random.random() < .5
             else " ".join(random.choice(palabras) for _ in range(random.randint(0, 10))))
        clasificar(t, None, NO)


# ----------------------------------------------------------------------------
# Fichas (archivo JSON)
# ----------------------------------------------------------------------------
def test_ficha_guarda_y_recarga(tmp_path):
    ruta = str(tmp_path / "p.json")
    f = FichasPersonas(ruta)
    assert f.agregar_hecho("Garli", "es la encargada", "x", "legnar")["estado"] == "persona_nueva"
    assert f.agregar_hecho("Garli", "trabaja en LPP", "x", "legnar")["estado"] == "dato_nuevo"
    assert f.agregar_hecho("garli", "Trabaja en LPP.", "x", "legnar")["estado"] == "repetido"
    g = FichasPersonas(ruta)
    assert len(g.personas["garli"]["hechos"]) == 2 and g.personas["garli"]["nombre"] == "Garli"


def test_ficha_recupera_desde_respaldo_si_el_principal_se_dana(tmp_path):
    ruta = str(tmp_path / "p.json")
    f = FichasPersonas(ruta)
    f.agregar_hecho("Garli", "es la encargada", "x", "legnar")
    f.agregar_hecho("Garli", "trabaja en LPP", "x", "legnar")   # aqui se crea el .bak
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("{ esto no es json")
    g = FichasPersonas(ruta)
    assert "garli" in g.personas
    # un guardado posterior no debe pisar el respaldo bueno con el archivo danado
    g.agregar_hecho("Pedro", "vive en Tampico", "x", "legnar")
    assert json.load(open(ruta, encoding="utf-8")).keys() >= {"garli", "pedro"}


def test_ficha_sin_archivos_temporales(tmp_path):
    ruta = str(tmp_path / "p.json")
    FichasPersonas(ruta).agregar_hecho("Garli", "es la encargada", "x", "legnar")
    assert not os.path.exists(ruta + ".tmp")


def test_ficha_limites(tmp_path):
    f = FichasPersonas(str(tmp_path / "p.json"), max_hechos=3, max_chars=20)
    for i in range(6):
        f.agregar_hecho("Garli", f"dato numero {i} " + "x" * 50, "x", "legnar")
    hechos = f.personas["garli"]["hechos"]
    assert len(hechos) == 3 and all(len(h["texto"]) <= 20 for h in hechos)


def test_olvidar_borra_tambien_el_respaldo(tmp_path):
    ruta = str(tmp_path / "p.json")
    f = FichasPersonas(ruta)
    f.agregar_hecho("Garli", "es la encargada", "x", "legnar")
    f.agregar_hecho("Garli", "trabaja en LPP", "x", "legnar")
    f.agregar_hecho("Pedro", "vive en Tampico", "x", "legnar")
    assert os.path.exists(ruta + ".bak")
    assert f.olvidar("garli") is True
    assert not os.path.exists(ruta + ".bak")
    assert "garli" not in open(ruta, encoding="utf-8").read().lower()
    assert FichasPersonas(ruta).resolver("garli") == (None, [])


def test_resolver_por_nombre_de_pila(tmp_path):
    f = FichasPersonas(str(tmp_path / "p.json"))
    f.agregar_hecho("Garli Pérez", "trabaja en LPP", "x", "legnar")
    assert f.resolver("garli")[0] == "garli perez"
    f.agregar_hecho("Garli Soto", "trabaja en el SAT", "x", "legnar")
    k, cands = f.resolver("garli")
    assert k is None and len(cands) == 2


# ----------------------------------------------------------------------------
# Integracion con ARCS
# ----------------------------------------------------------------------------
def _creador(tmp_path):
    (tmp_path / "clave_creador.txt").write_text(hash_clave("secreto123") + "\n", encoding="utf-8")
    a = ARCS(ruta_base=str(tmp_path))
    a.establecer_usuario("legnar", "secreto123")
    assert a.nivel_usuario == 2
    return a


def _usuario(tmp_path, nombre):
    a = ARCS(ruta_base=str(tmp_path))
    a.establecer_usuario(nombre)
    assert a.nivel_usuario == 1
    return a


def test_creador_guarda_sin_fragmentar_y_responde_completo(tmp_path):
    a = _creador(tmp_path)
    palabras_antes, dirty_antes = len(a.memoria), a.dirty
    r = a.procesar_personas(FRASE_GARLI)
    assert r == "Listo, guardé eso sobre Garli."
    # NO se metio en la memoria Markov
    assert len(a.memoria) == palabras_antes and a.dirty == dirty_antes
    # La respuesta es la frase entera, sin mezclar
    assert a.procesar_personas("quien es garli?") == RESPUESTA_GARLI
    # Y sobrevive a reiniciar
    b = ARCS(ruta_base=str(tmp_path))
    b.establecer_usuario("legnar", "secreto123")
    assert b.procesar_personas("¿Quién es Garli?") == RESPUESTA_GARLI


def test_dato_repetido_y_datos_acumulados(tmp_path):
    a = _creador(tmp_path)
    a.procesar_personas("Garli trabaja en LPP")
    assert a.procesar_personas("Garli trabaja en LPP") == "Eso ya lo sabía de Garli."
    a.procesar_personas("garli vive en Tampico")
    r = a.procesar_personas("que sabes de garli")
    assert "Garli trabaja en LPP." in r and "Garli vive en Tampico." in r


def test_pregunta_por_desconocido(tmp_path):
    a = _creador(tmp_path)
    assert a.procesar_personas("quien es Pedro?") == "No tengo información sobre Pedro. Si quieres, cuéntame algo y lo guardo."


def test_quien_es_arcs_sigue_el_flujo_normal(tmp_path):
    # 'arcs' es un concepto clave, no una persona: no se contesta "no tengo informacion sobre arcs"
    a = _creador(tmp_path)
    assert a.procesar_personas("quien es ARCS?") is None


def test_preguntas_normales_y_calculos_siguen_el_flujo_normal(tmp_path):
    a = _creador(tmp_path)
    traza = {}
    assert a.procesar_personas("que es el amor?", traza) is None
    assert traza["intencion"]["tipo"] == "pregunta_general"
    assert a.procesar_personas("5 mas 3") is None
    assert a.procesar_personas("el amor es lealtad") is None
    # y el flujo normal sigue aprendiendo como siempre
    a.aprender("el amor y la lealtad son importantes")
    assert "lealtad" in a.memoria["amor"] or a.memoria["amor"]


def test_invitado_no_guarda_nada(tmp_path):
    a = ARCS(ruta_base=str(tmp_path))
    a.establecer_usuario("invitado")
    r = a.procesar_personas("Garli trabaja en LPP")
    assert "como invitado no guardo" in r
    assert not os.path.exists(str(tmp_path / "personas_global.json"))
    assert a.listar_personas() == "Todavía no conozco a nadie."


def test_usuario_normal_guarda_en_privado(tmp_path):
    ana = _usuario(tmp_path, "ana")
    assert ana.procesar_personas("Pedro Pérez trabaja en una escuela") == "Listo, guardé eso sobre Pedro Pérez."
    assert not os.path.exists(str(tmp_path / "personas_global.json"))
    assert os.path.exists(os.path.join(os.path.dirname(ana.archivo_memoria_usuario), "personas.json"))
    # otro usuario no ve lo de ana
    beto = _usuario(tmp_path, "beto")
    assert "No tengo información" in beto.procesar_personas("quien es Pedro Pérez?")
    # ana lo recuerda tras reiniciar
    ana2 = _usuario(tmp_path, "ana")
    assert ana2.procesar_personas("donde trabaja Pedro Pérez?") == "Pedro Pérez trabaja en una escuela."


def test_lo_del_creador_lo_ven_todos_y_se_puede_cerrar(tmp_path):
    _creador(tmp_path).procesar_personas(FRASE_GARLI)
    ana = _usuario(tmp_path, "ana")
    assert ana.procesar_personas("quien es Garli") == RESPUESTA_GARLI
    ana.lectura_global_para_todos = False
    assert "No tengo información" in ana.procesar_personas("quien es Garli")


def test_datos_del_creador_y_del_usuario_se_combinan(tmp_path):
    _creador(tmp_path).procesar_personas(FRASE_GARLI)
    ana = _usuario(tmp_path, "ana")
    ana.procesar_personas("Garli es mi vecina")
    r = ana.procesar_personas("quien es garli")
    assert r.startswith(RESPUESTA_GARLI) and r.endswith("Me contaste: «Garli es mi vecina».")


def test_primera_persona_se_atribuye_a_quien_lo_dijo(tmp_path):
    _creador(tmp_path).procesar_personas("Rosa es mi mamá")
    ana = _usuario(tmp_path, "ana")
    assert ana.procesar_personas("quien es rosa") == "Legnar comentó: «Rosa es mi mamá»."


def test_pregunta_puntual_filtra_datos(tmp_path):
    a = _creador(tmp_path)
    a.procesar_personas("Pedro trabaja en una escuela")
    a.procesar_personas("Pedro vive en Tampico")
    assert a.procesar_personas("donde vive Pedro?") == "Pedro vive en Tampico."
    assert a.procesar_personas("en que trabaja Pedro?") == "Pedro trabaja en una escuela."
    # Sin dato de edad: solo lo dice, sin volcar las demas frases
    assert a.procesar_personas("cuantos años tiene Pedro?") == "No tengo ese dato específico de Pedro."


def test_nombre_ambiguo_pide_aclaracion(tmp_path):
    a = _creador(tmp_path)
    a.procesar_personas("Garli Pérez trabaja en LPP")
    a.procesar_personas("Garli Soto trabaja en el SAT")
    r = a.procesar_personas("quien es garli?")
    assert "Garli Pérez" in r and "Garli Soto" in r and "¿A cuál te refieres?" in r
    assert a.procesar_personas("quien es garli soto") == "Garli Soto trabaja en el SAT."


def test_olvidar_y_listar(tmp_path):
    a = _creador(tmp_path)
    a.procesar_personas("Garli trabaja en LPP")
    a.procesar_personas("Pedro vive en Tampico")
    assert a.listar_personas() == "Personas que conozco: Garli, Pedro"
    assert a.olvidar_persona("garli") == "Listo, olvidé todo lo que sabía de Garli."
    assert a.listar_personas() == "Personas que conozco: Pedro"
    assert "No tengo información" in a.procesar_personas("quien es garli")
    assert a.olvidar_persona("nadie") == "No tengo a nadie llamado nadie en tu memoria."
    assert a.olvidar_persona("").startswith("Dime a quién")


def test_usuario_no_puede_borrar_lo_global(tmp_path):
    _creador(tmp_path).procesar_personas("Garli trabaja en LPP")
    ana = _usuario(tmp_path, "ana")
    assert "No tengo a nadie" in ana.olvidar_persona("garli")
    assert "Garli trabaja en LPP." == ana.procesar_personas("quien es garli")


def test_cambiar_de_usuario_no_arrastra_fichas(tmp_path):
    a = _usuario(tmp_path, "ana")
    a.procesar_personas("Pedro trabaja en una escuela")
    a.establecer_usuario("invitado")
    assert a.personas_usuario is None
    assert "invitado" in a.procesar_personas("Luis vive en Tampico")


def test_la_traza_registra_la_intencion(tmp_path):
    a = _creador(tmp_path)
    traza = {}
    a.procesar_personas(FRASE_GARLI, traza)
    assert traza["intencion"]["tipo"] == "afirmacion_persona"
    assert traza["personas"]["accion"] == "persona_nueva"
    assert traza["respuesta"]["ruta"] == "personas"


# ----------------------------------------------------------------------------
# Sesion completa por el ciclo principal (main), con entradas simuladas
# ----------------------------------------------------------------------------
def test_ciclo_principal_completo(tmp_path, monkeypatch, capsys):
    import asyncio
    monkeypatch.setattr(modulo_arcs, "RUTA_BASE_DEFAULT", str(tmp_path) + "/")
    guion = iter(["ana",
                  "sabias que Garli es la encargada economica y legal de LPP",
                  "quien es Garli?",
                  "/personas",
                  "que es el amor?",
                  "/olvidar garli",
                  "quien es garli",
                  "/ayuda",
                  "salir"])

    def entrada(prompt=""):
        if "Continuar" in prompt:
            return "n"
        return next(guion)

    monkeypatch.setattr("builtins.input", entrada)
    asyncio.run(modulo_arcs.main())
    salida = capsys.readouterr().out
    assert "[ARCS]: Listo, guardé eso sobre Garli." in salida
    assert "[ARCS]: Garli es la encargada economica y legal de LPP." in salida
    assert "Personas que conozco: Garli" in salida
    assert "Listo, olvidé todo lo que sabía de Garli." in salida
    assert "[ARCS]: No tengo información sobre Garli." in salida
    assert "/personas" in salida and "/olvidar <nombre>" in salida
    # la pregunta normal siguio el flujo de siempre (hay respuesta y quedo en el log)
    log = (tmp_path / "logr.txt").read_text(encoding="utf-8")
    assert log.count("\n") == 4   # 4 mensajes con respuesta; los comandos (/personas, /olvidar, /ayuda) no se registran


# ----------------------------------------------------------------------------
# Regresiones: nombres parecidos no deben mezclarse
# ----------------------------------------------------------------------------
def test_apellido_distinto_no_se_pega_a_otra_persona(tmp_path):
    a = _creador(tmp_path)
    a.procesar_personas("Garli Pérez trabaja en LPP")
    assert a.procesar_personas("Garli Soto trabaja en el SAT") == "Listo, guardé eso sobre Garli Soto."
    assert a.procesar_personas("quien es garli perez") == "Garli Pérez trabaja en LPP."
    assert a.procesar_personas("quien es garli soto") == "Garli Soto trabaja en el SAT."


def test_apellido_en_mayuscula_con_verbo_no_listado_no_se_acepta():
    conocidas = {"garli perez"}
    r = clasificar("Garli Soto compró un carro", lambda n: n == "garli" or n in conocidas, NO)
    assert r["tipo"] == "otro"


def test_guardar_con_nombre_ambiguo_pregunta_en_vez_de_crear_otra_persona(tmp_path):
    a = _creador(tmp_path)
    a.procesar_personas("Garli Pérez trabaja en LPP")
    a.procesar_personas("Garli Soto trabaja en el SAT")
    r = a.procesar_personas("Garli vive en Tampico")
    assert "Garli Pérez" in r and "Garli Soto" in r and "nombre completo" in r
    assert a.listar_personas() == "Personas que conozco: Garli Pérez, Garli Soto"
