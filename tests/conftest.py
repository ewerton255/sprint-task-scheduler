import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao PYTHONPATH
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root)) 