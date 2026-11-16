# tests/conftest.py
# Configura o sys.path para que os scripts usem a convencao de import "solta" do
# projeto (ex.: `from tools import ...`, `from search import retrieve`) tambem
# sob pytest. Em producao, um script executado direto (python scripts/x.py)
# ja poe scripts/ no sys.path; aqui fazemos o mesmo para os testes.
import sys
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
