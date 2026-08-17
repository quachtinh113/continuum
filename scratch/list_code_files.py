import os
import re
from pathlib import Path

root = Path(".")
py_files = list(root.glob("src/**/*.py")) + list(root.glob("v9_continuum/**/*.py")) + list(root.glob("config/**/*.py")) + list(root.glob("*.py"))

print(f"Found {len(py_files)} Python files:")
for f in py_files:
    print(f" - {f}")
