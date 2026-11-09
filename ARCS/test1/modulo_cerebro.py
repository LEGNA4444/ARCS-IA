import os  # Manejo de rutas de archivos y carpetas.
import json  # Lectura y escritura de la memoria en formato JSON.
import asyncio  # Operaciones asíncronas sin bloquear el programa.
import aiohttp  # Cliente HTTP asíncrono.
from bs4 import BeautifulSoup  # Extracción de texto desde HTML.

# =================================================================
# Clase principal: ModuloCerebro.
# Guarda los conocimientos en JSON y puede consultar páginas web.
# =================================================================
class ModuloCerebro:
    def __init__(self, ruta_base):
        """
        Inicializa el módulo y carga su memoria.
        :param ruta_base: Carpeta donde se almacena hechos.json.
        """
        # Armamos la ruta completa del archivo de memoria. ej: /mi/proyecto/hechos.json
        # Usamos os.path.join para que no falle con las / o \ del sistema operativo
        self.ruta_hechos = os.path.join(ruta_base, "hechos.json")

        # Carga los conocimientos existentes.
        self.hechos = self.cargar_hechos()

    def cargar_hechos(self):
        """
        Carga la memoria del disco o devuelve un diccionario vacío si no existe.
        """
        # Comprueba primero si el archivo existe.
        if os.path.exists(self.ruta_hechos):
            try:
                # UTF-8 conserva correctamente los acentos y la eñe.
                with open(self.ruta_hechos, "r", encoding="utf-8") as f:
                    # json.load convierte el contenido en objetos de Python.
                    return json.load(f)
            except:
                # Si el archivo está dañado o vacío, inicia con una memoria vacía.
                return {}
        # No hay datos que cargar.
        return {}

    def guardar_hecho(self, sujeto, predicado, objeto):
        """
        Guarda un conocimiento con la estructura sujeto -> predicado -> objeto.
        Ejemplo: guardar_hecho("Juan", "edad", "25").
        """
        # Crea el diccionario del sujeto cuando es necesario.
        if sujeto not in self.hechos:
            self.hechos[sujeto] = {}

        # Guarda el valor asociado al predicado.
        self.hechos[sujeto][predicado] = objeto

        # Escribe el diccionario actualizado con formato legible.
        with open(self.ruta_hechos, "w", encoding="utf-8") as f:
            json.dump(self.hechos, f, indent=4)

    async def buscar_web(self, url):
        """
        Consulta una página web y extrae texto de sus primeros párrafos.
        :param url: Dirección de la página que se va a consultar.
        :return: Hasta 500 caracteres de texto extraído.
        """
        try:
            # Abre una sesión HTTP para realizar la solicitud.
            async with aiohttp.ClientSession() as session:
                # Limita la espera para evitar solicitudes bloqueadas.
                async with session.get(url, timeout=5) as response:
                    # Lee el HTML de la respuesta.
                    html = await response.text()

                    # Analiza el HTML para extraer su contenido.
                    soup = BeautifulSoup(html, 'html.parser')

                    # Extrae el texto de los primeros cinco párrafos.
                    texto = " ".join([p.get_text() for p in soup.find_all('p')[:5]])

                    # Limita el texto para no saturar la memoria ni el contexto.
                    return texto[:500]
        except Exception as e:
                    # Devuelve el error como texto sin interrumpir el programa.
            return f"Error al leer web: {str(e)}"