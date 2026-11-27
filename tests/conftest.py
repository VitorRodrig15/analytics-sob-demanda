# tests/conftest.py
# Configura o sys.path para que os scripts usem a convencao de import "solta" do
# projeto (ex.: `from tools import ...`, `from search import retrieve`) tambem
# sob pytest. Em producao, um script executado direto (python scripts/x.py)
# ja poe o diretorio do proprio script no sys.path; aqui fazemos o mesmo para
# os testes - uma entrada por subpasta de scripts/ (agents, tools, interface,
# ingestao, legado, testes_manuais), mesma lista do PYTHONPATH do
# docker-compose.yml.
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
for subpasta in ("agents", "tools", "interface", "ingestao", "legado", "testes_manuais"):
    caminho = str(SCRIPTS_DIR / subpasta)
    if caminho not in sys.path:
        sys.path.insert(0, caminho)
