import os # Para crear carpetas y manejar rutas, el plomero del sistema
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

# =============================================================================
# CLASE ARCS - El cerebro principal chido
# =============================================================================
class ARCS:
    def __init__(self):
        # --- RUTAS DONDE VIVE TODO ---
        self.ruta_base = "/storage/emulated/0/urc/urc/"
        self.archivo_memoria = self.ruta_base + "arcs_v2_core.txt" # Guarda: palabra > siguiente1,siguiente2
        self.archivo_dicc = self.ruta_base + "arcs_v2_dict.txt" # Guarda: palabra :: significado
        self.archivo_pesos = self.ruta_base + "arcs_pesos.txt" # Guarda: palabra :: peso

        self.cerebro = ModuloCerebro(self.ruta_base)

        # --- CONFIGURACION ---
        self.capas = 50000 # Cuantas palabras maximo intenta generar
        self.max_memoria_por_key = 20000000 # Para que no se haga una lista infinita
        self.memoria = defaultdict(list)
        self.diccionario = {}
        self.prioridades = defaultdict(float)

        # --- MEMORIA POR USUARIO ---
        self.memoria_usuario = defaultdict(list)
        self.prioridades_usuario = defaultdict(float)
        self.dirty = False # Bandera: "la memoria global cambio, hay que guardar"
        self.dirty_usuario = False

        # --- CONTEXTO Y PERSONALIDAD ---
        self.contexto = []
        self.max_contexto = 3000000
        self.personalidad = "femenina"
        self.temperatura = 0.85 # 0.0 aburrido, 1.0 bien loco
        self.silent_mode = False

        # --- SIGLAS Y CONCEPTOS EN MAYUSCULAS ---
        self.siglas_mayus = {"sat", "profeco", "arcs", "faa", "otan", "urss", "lpp"}

        # --- MAPPING MATEMATICO EN TEXTO ---
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

        # --- FILTROS ---
        self.conceptos_clave = {"lealtad", "clika", "respeto", "gringos", "codigo", "fuerza", "amor", "legnar", "amigos", "sexo", "seguridad", "mexico", "himmno", "poder", "niña", "arcs", "propiedad", "privado", "derechos", "onu", "otan", "urss", "mexicas", "mexica", "mexicanos", "mexicanas", "niños", "niñas", "hombre", "mujer", "faa", "profeco", "sat", "ley", "respeto", "ganar", "ia", "ias", "idioma", "diferente", "gustar", "cambiar", "error", "juramento", "patria", "lealtad", "bandera", "mexicana"}
        self.stopwords = {"el", "la", "de", "que", "y", "a", "en", "un", "es", "por", "con", "para", "los", "las", "del", "se", "no", "te"}

        # --- USUARIOS ---
        self.usuario_actual = "invitado"
        self.es_creador = False
        self.nivel_usuario = 0 # 0 invitado, 1 normal, 2 creador
        self.archivo_memoria_usuario = ""
        self.archivo_pesos_usuario = ""

        # --- BOOT INICIAL EN ORDEN CORRECTO ---
        os.makedirs(self.ruta_base, exist_ok=True)
        self.restaurar_si_esta_roto()
        self.crear_respaldo_preventivo()
        self.boot_permanente()

    def restaurar_si_esta_roto(self):
        for f in [self.archivo_dicc, self.archivo_memoria, self.archivo_pesos]:
            bak = f + ".bak"
            if (not os.path.exists(f) or os.path.getsize(f) == 0) and os.path.exists(bak):
                shutil.copy(bak, f)

    def crear_respaldo_preventivo(self):
        for f in [self.archivo_dicc, self.archivo_memoria, self.archivo_pesos]:
            try:
                if os.path.exists(f) and os.path.getsize(f) > 0:
                    bak = f + ".bak"
                    shutil.copy(f, bak)
            except:
                pass

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

    def establecer_usuario(self, nombre):
        self.usuario_actual = nombre.lower().strip()
        if self.usuario_actual == "legnar":
            self.es_creador = True
            self.nivel_usuario = 2
        elif self.usuario_actual == "invitado":
            self.nivel_usuario = 0
        else:
            self.nivel_usuario = 1
            self.iniciar_archivos_usuario()

    def iniciar_archivos_usuario(self):
        self.archivo_memoria_usuario = self.ruta_base + f"arcs_user_{self.usuario_actual}_core.txt"
        self.archivo_pesos_usuario = self.ruta_base + f"arcs_user_{self.usuario_actual}_pesos.txt"
        if not os.path.exists(self.archivo_memoria_usuario):
            self.generar_memoria_limpia_usuario()
        self.cargar_archivo(self.archivo_memoria_usuario, self.memoria_usuario, 2)
        self.cargar_archivo(self.archivo_pesos_usuario, self.prioridades_usuario, 3)

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
        t = ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c)!= 'Mn' or c == 'ñ')
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
        t = texto.lower()
        # Remueve acentos basicos para normalizar palabras clave como "más"
        t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c)!= 'Mn' or c == 'ñ')

        # Reemplaza palabras de numeros y operadores por sus simbolos
        for txt_num, num in self.numeros_texto.items():
            t = re.sub(rf"\b{txt_num}\b", num, t)
        for txt_op, op in self.operadores_texto.items():
            t = re.sub(rf"\b{re.escape(txt_op)}\b", op, t)

        # Regex para capturar secuencias de operandos incluyendo potencias (**)
        expresion = re.search(r"(\d+(?:\s*(?:\*\*|[\+\-\*/])\s*\d+)+)", t)
        if expresion:
            expr_str = expresion.group(1).replace(" ", "")
            try:
                # Evaluacion con funciones matematicas seguras si se requieren
                res = eval(expr_str, {"__builtins__": None, "math": math}, {})
                if isinstance(res, float) and res.is_integer():
                    res = int(res)
                
                # Revisa si la entrada del usuario era solo el problema matematico
                texto_sin_expr = re.sub(r"(\d+(?:\s*(?:\*\*|[\+\-\*/])\s*\d+)+)", "", t).strip()
                es_puro = len(texto_sin_expr) < 3 # Si casi no quedan palabras, es un calculo puro
                
                return f"El resultado de {expr_str} es {res}", es_puro
            except ZeroDivisionError:
                return "Error: no se puede dividir entre cero", True
            except OverflowError:
                return "Error: resultado demasiado grande para procesar", True
            except:
                pass
        return None, False

    def aprender(self, t):
        # Si la entrada es un calculo matematico puro, no ensucia la memoria Markov
        res_calc, es_puro = self.procesar_calculo(t)
        if es_puro:
            return

        palabras = self.limpiar(t).split()
        if len(palabras) < 2: return
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
            if a == s or not a or not s or a in self.stopwords: continue
            
            a_min = a.lower()
            s_min = s.lower()
            es_clave = (a_min in self.conceptos_clave or s_min in self.conceptos_clave)
            peso_incremental = (1.0 + (12.0 if es_clave else 0.0))
            if factor_base > 0:
                if s not in self.memoria[a]:
                    self.memoria[a].append(s)
                    cambios_base = True
                self.prioridades[a] += (peso_incremental * factor_base)
                cambios_base = True
                if a not in self.diccionario:
                    self.diccionario[a] = s
                    cambios_base = True
            if factor_usuario > 0:
                if s not in self.memoria_usuario[a]:
                    self.memoria_usuario[a].append(s)
                    cambios_usuario = True
                self.prioridades_usuario[a] += (peso_incremental * factor_usuario)
                cambios_usuario = True
        if cambios_base: self.dirty = True
        if cambios_usuario: self.dirty_usuario = True

    def aplicar_personalidad(self, texto):
        if self.personalidad == "femenina":
            reemplazos = {r"\bentiendo\b": "literal te entiendo", r"\bonline\b": "arcs activa tipo bien", r"\bhola\b": "holaaa qué onda"}
            for k, v in reemplazos.items():
                texto = re.sub(k, v, texto, flags=re.IGNORECASE)
            if self.es_creador: texto = texto.replace("wey", "jefe")
            if "quien eres" in texto.lower(): texto = "Soy ARCS, propiedad de LPP y el grupo Srangel y asociados externos"
        return texto

    def responder(self, t):
        # Primero revisa si la entrada requiere calculo directo
        calculo, es_puro = self.procesar_calculo(t)
        
        # Si fue un problema matematico puro, solo entrega el resultado numérico
        if calculo is not None and es_puro:
            return self.aplicar_personalidad(calculo)

        # Si habia texto conversacional junto con la operacion, arma la respuesta de Markov
        palabras = self.limpiar(t).split()
        if not palabras: return self.aplicar_personalidad("online")
        if "quien eres" in " ".join(palabras).lower(): return self.aplicar_personalidad("quien eres")
        mem_activa = self.memoria_usuario if self.nivel_usuario == 1 else self.memoria
        prio_activa = self.prioridades_usuario if self.nivel_usuario == 1 else self.prioridades
        candidatos = [p for p in palabras if p in mem_activa]
        if not candidatos and self.nivel_usuario == 1:
            candidatos = [p for p in palabras if p in self.memoria]
            mem_activa = self.memoria
            prio_activa = self.prioridades
        if not candidatos: 
            resp_markov = self.diccionario.get(palabras[0], "sistema analizando")
        else:
            enfoque = max(candidatos, key=lambda p: prio_activa.get(p, 0))
            res, actual = [], enfoque
            usados = {actual}
            for _ in range(self.capas):
                if actual not in mem_activa: break
                opciones = [o for o in mem_activa[actual] if o not in usados and o]
                if not opciones: break
                proximo = max(opciones, key=lambda o: prio_activa.get(o, 0)) if random.random() < self.temperatura else random.choice(opciones)
                res.append(proximo)
                usados.add(proximo)
                actual = proximo
                if actual.lower() in self.conceptos_clave and len(res) >= 3: break
            resp_markov = " ".join(res) if res else self.diccionario.get(enfoque, "sistema analizando")

        # Si habia una operacion dentro de un texto mas largo, adjunta ambos resultados
        if calculo is not None and not es_puro:
            return f"{calculo} | {self.aplicar_personalidad(resp_markov)}"

        return self.aplicar_personalidad(resp_markov)

    def guardar_indestructible(self):
        if self.dirty:
            try:
                with open(self.archivo_dicc, "w", encoding="utf-8") as f:
                    for k, v in self.diccionario.items(): f.write(f"{k} :: {v}\n")
                with open(self.archivo_memoria, "w", encoding="utf-8") as f:
                    for k, v in self.memoria.items(): f.write(f"{k}>{','.join(v)}\n")
                with open(self.archivo_pesos, "w", encoding="utf-8") as f:
                    for k, v in self.prioridades.items(): f.write(f"{k} :: {v}\n")
                self.dirty = False
                for fp in [self.archivo_dicc, self.archivo_memoria, self.archivo_pesos]:
                    if os.path.exists(fp) and os.path.getsize(fp) > 0:
                        shutil.copy(fp, fp + ".bak")
            except: pass
        if self.dirty_usuario and self.nivel_usuario == 1:
            try:
                with open(self.archivo_memoria_usuario, "w", encoding="utf-8") as f:
                    for k, v in self.memoria_usuario.items(): f.write(f"{k}>{','.join(v)}\n")
                with open(self.archivo_pesos_usuario, "w", encoding="utf-8") as f:
                    for k, v in self.prioridades_usuario.items(): f.write(f"{k} :: {v}\n")
                self.dirty_usuario = False
            except: pass

async def main():
    arcs = ARCS()
    usuario_input = input("Identidad del usuario: ")
    arcs.establecer_usuario(usuario_input)
    print(f"Sesión iniciada como: {arcs.usuario_actual} (Nivel {arcs.nivel_usuario}) estas en la version {controls.version}/{controls.versiont} interfaz {controls.interfaz}/{controls.interfazt}")
    print("Advertencia: ARCS es una ia no LLM en estatus de pruebas ARCS es una ia estadistica por mas humana o real que se sienta no deja de ser solo una tabla de valores dinamica no tiene conocimiento real de nada ni experiencias la ejecucion de ARCS es bajo responsabilidad de el usario LPP no se ase responsable de daños por mal funcionamiento")
    an = "-" * 32
    anin = "_" * 32
    anb = "-" * 8
    ancxb = "-" * 4
    while True:
        try:
            u = await asyncio.to_thread(input, f"[{arcs.usuario_actual}]: ")
            if u.lower() in ["exit", "salir", "off=modelo"]: 
                break
                
            if u.lower() == "/estoy perdido":
                print(anin)
                print(f"ARCS creada por: _LegNar.4.4.4.4// de Srangel el uso de esta ia (no LLM) es bajo responsabilidad de:  {arcs.usuario_actual} o el responsable legal/tutor ARCS puede fallar tenga en cuenta que puede equivocarse ser mal hablada insultar ect. LPP y Srangel no se asen responsables de nada usted accepto las condiciones, politicas, seguridad y privacidad al descargar y ejecutar sigiendo las intrucciones oficiales si deja de estar de acuerdo borre  la ruta que corresponde a /arcs y siga las instrucciones de eliminacion que se le dieron con el ejecutable/s")
                print(an)
                continue
                    

            if u.lower() == "/status":
                
                
                print(anin)
                print("")
                print(ancxb + "----" + "estado de usuario" + ancxb + "---")
                print(anin)
                print(f"Usuario: {arcs.usuario_actual}")
                print(f"Nivel: {arcs.nivel_usuario}")
                
                print(an)
                print(anin)
                print(anb + "estado de ARCS" + anb)
                print(an)
                print(f"probabilidad matematica de cuerencia (tem): {arcs.temperatura}")
                print(f"sexo: {arcs.personalidad}")
                print(an)
                print(f"Capas: {arcs.capas}")
                print(f"Palabras en memoria: {len(arcs.memoria)}")
                print(anin)
                continue

            arcs.aprender(u)
            respuesta= arcs.responder(u)
            print(f"[ARCS]: {respuesta}")
            from logslpp import inflog
            tiempo = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            rtir= "sys: tiempo en que arcs respondio: "+tiempo + " total time:  ==>"
            
            
            rco= inflog(arcs.ruta_base+"logr.txt")
            rco.write(rtir+respuesta)
            rco.close()
            print(rtir+respuesta)
        except KeyboardInterrupt: 
            break

    arcs.guardar_indestructible()

if __name__ == "__main__":
    asyncio.run(main())
