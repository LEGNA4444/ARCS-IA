import os # Para manejar rutas de archivos y carpetas, para que funcione en Windows, Linux y Mac sin pedos
import json # Para leer y guardar archivos.json, que es donde vamos a guardar la memoria
import asyncio # Para que podamos hacer cosas asincronas, osea que no se trabe esperando internet
import aiohttp # Cliente para hacer peticiones web rapidas y asincronas, mejor que requests para esto
from bs4 import BeautifulSoup # BeautifulSoup es para raspar HTML y sacar solo el texto limpio, sin etiquetas

# =================================================================
# CLASE PRINCIPAL: ModuloCerebro
# Este wey es literal el cerebro. Guarda lo que aprende en un JSON
# y tambien puede salir a buscar info a internet si no la sabe.
# =================================================================
class ModuloCerebro:
    def __init__(self, ruta_base):
        """
        Constructor - Se ejecuta en cuanto creas el cerebro.
        :param ruta_base: La carpeta donde queremos que viva el archivo de memoria hechos.json
        """
        # Armamos la ruta completa del archivo de memoria. ej: /mi/proyecto/hechos.json
        # Usamos os.path.join para que no falle con las / o \ del sistema operativo
        self.ruta_hechos = os.path.join(ruta_base, "hechos.json")

        # En cuanto nace el cerebro, carga todo lo que ya sabia de antes
        self.hechos = self.cargar_hechos()

    def cargar_hechos(self):
        """
        Carga la memoria del disco.
        Si ya existe el hechos.json lo lee, si no, empieza con la mente en blanco {}.
        """
        # Primero checamos si el archivo siquiera existe para no crashear
        if os.path.exists(self.ruta_hechos):
            try:
                # Lo abrimos en modo lectura "r" y con utf-8 para que agarre acentos y ñ
                with open(self.ruta_hechos, "r", encoding="utf-8") as f:
                    # json.load convierte el texto del archivo en un diccionario de Python
                    return json.load(f)
            except:
                # Si el archivo esta corrupto, vacio o mal escrito, no nos morimos, solo regresamos diccionario vacio
                # Aqui podrias poner un print para debuggear
                return {}
        # Si no existe el archivo, pues no hay nada que cargar, regresamos cerebro vacio
        return {}

    def guardar_hecho(self, sujeto, predicado, objeto):
        """
        Guarda un nuevo conocimiento con la estructura: Sujeto -> Predicado -> Objeto
        Ejemplo: guardar_hecho("Juan", "edad", "25") -> {"Juan": {"edad": "25"}}
        """
        # Si es la primera vez que vemos a este sujeto, le creamos su diccionarito
        if sujeto not in self.hechos:
            self.hechos[sujeto] = {}

        # Guardamos el dato: dentro del sujeto, guardamos su predicado con su valor
        self.hechos[sujeto][predicado] = objeto

        # Ahora si, escribimos TODO el diccionario actualizado de vuelta al archivo.json
        # "w" es de escritura, va a sobreescribir el archivo anterior
        # indent=4 es para que el JSON se vea bonito y legible, no todo amontonado
        with open(self.ruta_hechos, "w", encoding="utf-8") as f:
            json.dump(self.hechos, f, indent=4)

    async def buscar_web(self, url):
        """
        Esta es la parte asincrona. Va a una pagina web y raspa los primeros parrafos.
        :param url: La pagina que quieres leer
        :return: Un string con los primeros 500 caracteres de texto limpio
        """
        try:
            # Creamos una sesion de cliente. Es como abrir el navegador
            async with aiohttp.ClientSession() as session:
                # Hacemos el GET a la URL, con timeout de 5 segundos por si la pagina esta muerta y no se cuelgue infinito
                async with session.get(url, timeout=5) as response:
                    # Sacamos el HTML crudo de la respuesta
                    html = await response.text()

                    # Aqui entra BeautifulSoup a hacer magia: parsea el HTML
                    soup = BeautifulSoup(html, 'html.parser')

                    # Buscamos todas las etiquetas <p> (parrafos), agarramos solo las primeras 5 para no traer basura
                    # y de cada una sacamos solo el texto con get_text()
                    # Luego las unimos todas con un espacio " ".join(...)
                    texto = " ".join([p.get_text() for p in soup.find_all('p')[:5]])

                    # Regresamos solo los primeros 500 caracteres para no saturar la memoria / el prompt
                    return texto[:50000]
        except Exception as e:
            # Si algo falla (no hay internet, la url no existe, timeout, etc) no crasheamos
            # Regresamos el error como texto para que el cerebro sepa que fallo
            return f"Error al leer web: {str(e)}"