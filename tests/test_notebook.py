import ast
import json
from pathlib import Path


def test_colab_notebook_has_valid_python_and_no_saved_outputs():
    notebook = json.loads(
        (Path(__file__).parents[1] / "notebooks/01_train_colab.ipynb").read_text()
    )
    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["accelerator"] == "GPU"
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert len(code_cells) >= 7
    for cell in code_cells:
        ast.parse("".join(cell["source"]))
        assert cell["execution_count"] is None
        assert cell["outputs"] == []
