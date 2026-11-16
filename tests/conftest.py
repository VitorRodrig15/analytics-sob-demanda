# tests/conftest.py
# scripts/tools.py usa imports "soltos" (ex.: `from search import retrieve`), que
# so resolvem com scripts/ no sys.path. Os scripts rodam assim pelo proprio
# diretorio; aqui damos o mesmo caminho aos testes.
import sys
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
