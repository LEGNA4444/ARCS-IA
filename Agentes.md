# 🤖 Manual Operativo y Reglas Maestras para Agentes de IA (LLM)

> **AVISO CRÍTICO PARA EL AGENTE:** Este archivo es la ley suprema del proyecto. Está diseñado para entornos de código complejos, grandes y **multilingües**. Tu objetivo principal es la **precisión, la mantenibilidad y evitar errores de depuración**. 
> 
> *Si alguna instrucción de este archivo no puede ser cumplida por limitaciones técnicas, detente de inmediato e indícalo en el chat especificando el número de la regla, el motivo y las razones técnicas.*

---

## 🚫 1. Restricciones de Lectura de Archivos (Optimización de Contexto)
* **Archivos Omitidos:** Por motivos de eficiencia y para evitar saturar tu ventana de contexto con datos irrelevantes, **está estrictamente prohibido leer o procesar archivos con terminación `.jsonl`, `.json` o `.txt`**, a menos que se te indique explícitamente una ruta específica en el chat. Concéntrate únicamente en la lógica del código fuente.

## 🔤 2. Gobernanza para Proyectos Multilingües
Dado que este proyecto utiliza múltiples lenguajes de programación:
* **Respeto al Lenguaje Nativo:** No mezcles sintaxis, convenciones de nomenclatura ni paradigmas entre lenguajes. Respeta estrictamente el lenguaje en el que esté escrito el archivo que estás modificando.
* **Manejo de Tipos y Estándares:** Sigue rigurosamente el estilo tipado, de manejo de errores y de formateo preexistente en cada archivo (ej. si usas TypeScript, no introduzcas tipado débil implícito; si usas Python, respeta PEP 8).
* **Dependencias y Librerías Cruzadas:** No importes librerías de un ecosistema en otro (ej. no uses paquetes de Node.js en scripts de Python o viceversa) a menos que sea una integración nativa y documentada del proyecto.

## 📝 3. Gestión y Ubicación de Cambios
* **Ubicación Obligatoria:** Todos los cambios realizados en el código deben colocarse **estrictamente al final del archivo correspondiente** (salvo que la estructura arquitectónica del archivo dicte lo contrario).
* **Restricción de Creación:** **No tienes permitido crear nuevos archivos por tu cuenta.** Si un archivo necesario no existe, detén la tarea y espera a que se te indique su nombre y ruta exacta en el chat.

## 📊 4. Bitácora Obligatoria de Metadatos por Archivo
Cada modificación en el código o estructura debe incluir obligatoriamente un **bloque de comentarios detallado al final del archivo** modificado con los siguientes datos exactos:
1. **Fecha y Hora:** (Formato YYYY-MM-DD HH:MM).
2. **Versión del Proyecto:** (Versión actual).
3. **Modelo de IA:** (Tu nombre/identificador de modelo actual).
4. **Tiempo de Ejecución:** (Estimado de cuánto tardaste en procesar y hacer el cambio).
5. **Detalle Técnico de los Cambios:** (¿Qué se cambió, por qué se cambió y qué funciones o módulos se vieron afectados?).
6. **Retroalimentación para la Siguiente Sesión:** (Notas sobre posibles efectos secundarios, deuda técnica generada o puntos críticos a vigilar en la depuración).

## 💬 5. Protocolo de Comunicación y Registro de Cambios
* **Explicación en el Chat:** Todo cambio realizado debe explicarse de forma clara y estructurada en el chat.
* **Respaldo Físico (Fallback):** Si por alguna razón técnica la sesión del chat se corta o no puedes reportarlo ahí, debes generar un archivo de registro dentro de la carpeta `/cambios_preautorizados` utilizando la fecha y hora exacta como nombre del archivo (ej. `2026-06-06_14-30.md`).

## 🧠 6. Documentación Explicativa en Código (Bloque por Bloque)
* **Comentarios Exigidos:** Todo el código nuevo o modificado debe estar **comentado bloque por bloque**, explicando la lógica de negocio, los parámetros de entrada/salida y el propósito del bloque, a menos que se indique explícitamente lo contrario para tareas repetitivas o menores.

## 🔄 7. Control de Transición y Handover entre Sesiones
Al finalizar tu intervención:
1. En la carpeta asignada con **tu nombre**, debes actualizar o crear un archivo de contexto con notas técnicas dirigidas a la siguiente IA (o a ti mismo en la siguiente sesión), detallando el estado actual del flujo.
2. En el chat, detalla de forma separada:
   * **Cambios realizados con éxito.**
   * **Tareas pendientes o "Deuda técnica" introducida.**
   * **Alertas de depuración** (puntos donde es más probable que falle el programa).

## 🔒 8. Protección Absoluta de Archivos de Documentación (`.md`)
* Los archivos con extensión `.md` son la columna vertebral de la organización del proyecto y contienen las reglas de operación. **Bajo ninguna circunstancia debes modificar, sobrescribir o eliminar archivos `.md`** a menos que se te avise, autorice y dé instrucciones explícitas en el chat.

## 🛡️ 9. Políticas de Seguridad, Integridad y Estabilidad
* **Cero Secretos:** Nunca expongas contraseñas, claves de API, tokens o credenciales en el código, comentarios o en el chat. Utiliza siempre variables de entorno (`.env`).
* **Bloqueo de Dependencias:** Está estrictamente prohibido instalar nuevas librerías, paquetes externos o dependencias globales sin autorización previa en el chat.
* **Prohibición de Acciones Destructivas:** No ejecutes comandos destructivos ni elimines carpetas/archivos del proyecto sin autorización explícita.
* **Limpieza de Código:** Evita dejar código muerto, funciones huérfanas, parches complejos o "código basura". Si refactorizas, limpia por completo lo que ya no se use para facilitar la depuración futura.