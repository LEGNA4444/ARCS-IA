import sys, os, types

# Permite ejecutar las pruebas sin aiohttp ni bs4 y sin acceder al almacenamiento del teléfono.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    import modulo_cerebro  # noqa: F401
except ImportError:
    sys.modules["modulo_cerebro"] = types.SimpleNamespace(ModuloCerebro=lambda ruta: None)
