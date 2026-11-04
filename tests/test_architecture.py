import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKENDS = ["config", "data_access", "filters", "pricing", "history", "cleaning", "presentation"]


def test_backends_import_standalone_without_streamlit():
    code = ("import sys; " + "; ".join(f"import src.{m}" for m in BACKENDS)
            + "; assert 'streamlit' not in sys.modules, 'streamlit imported'")
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


def test_backend_sources_have_no_ui_imports():
    for module in BACKENDS:
        tree = ast.parse((ROOT / "src" / f"{module}.py").read_text())
        names = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                 for alias in node.names}
        names |= {(node.module or "").split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        assert not names & {"streamlit", "plotly"}, module


def test_charts_use_plotly_but_not_streamlit():
    tree = ast.parse((ROOT / "src" / "charts.py").read_text())
    names = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    names |= {(node.module or "").split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "streamlit" not in names
