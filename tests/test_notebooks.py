"""Structural checks; behavioral checkpoints run live inside each notebook."""

import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = sorted((ROOT / "agent_memory").glob("*.ipynb"))


class NotebookStructureTests(unittest.TestCase):
    def test_all_three_standalone_notebooks_are_present(self):
        self.assertEqual(
            {path.name for path in NOTEBOOKS},
            {
                "agent_memory_from_scratch.ipynb",
                "persistent_notes_filesystem.ipynb",
                "persistent_notes_oracle.ipynb",
            },
        )

    def test_cells_are_short_valid_and_independent(self):
        for path in NOTEBOOKS:
            notebook = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(notebook["nbformat"], 4)
            code = []
            markdown = []
            for index, cell in enumerate(notebook["cells"]):
                source = "".join(cell["source"])
                with self.subTest(notebook=path.name, cell=index):
                    if cell["cell_type"] == "code":
                        self.assertLessEqual(len(source.splitlines()), 25)
                        python = "\n".join(
                            line for line in source.splitlines()
                            if not line.lstrip().startswith("%")
                        )
                        ast.parse(python)
                        self.assertFalse(any(
                            output["output_type"] == "error"
                            for output in cell.get("outputs", [])
                        ))
                        code.append(source)
                    else:
                        markdown.append(source)
            joined = "\n".join(code)
            self.assertIn("%pip install", joined)
            self.assertNotRegex(joined, r"sys\.path|PYTHONPATH|from src\b")
            self.assertNotIn("memory_lab", joined)
            self.assertNotIn("unittest.mock", joined)
            self.assertNotIn("fixtures/", joined)
            self.assertIn("```mermaid", "\n".join(markdown))

    def test_published_package_installations(self):
        for path in NOTEBOOKS:
            if path.name.startswith("persistent_notes_"):
                cells = json.loads(path.read_text())["cells"]
                installation = "\n".join(
                    "".join(cell["source"]) for cell in cells
                    if cell["cell_type"] == "code"
                    and "%pip" in "".join(cell["source"])
                )
                self.assertRegex(installation, r"memorizz(?:\[oracle\])?==0\.11\.0")
                self.assertNotIn("-e ", installation)

    def test_no_credentials_in_notebook_sources_or_outputs(self):
        secret = re.compile(r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}")
        for path in NOTEBOOKS:
            with self.subTest(notebook=path.name):
                self.assertIsNone(secret.search(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
