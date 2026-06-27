"""Make the repo root importable during pytest.

The tool ships as a single top-level module (stellaris_ironman.py), so this
puts the repo root on sys.path -- tests then `import stellaris_ironman` without
requiring an editable install (CI installs the package; this keeps a bare
`pytest` working from a fresh clone and in the pre-push hook).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
