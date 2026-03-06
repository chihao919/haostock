import importlib.util, os

_spec = importlib.util.spec_from_file_location(
    "quote_ticker",
    os.path.join(os.path.dirname(__file__), "[ticker].py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
app = _mod.app
