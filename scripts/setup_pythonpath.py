#!/usr/bin/env python3
"""
Create a .pth file in the current virtual environment's site-packages
that adds the project's src directory to sys.path.
This eliminates the need to set PYTHONPATH=./src manually.
"""

import sys
import os
import site
from pathlib import Path

def find_site_packages() -> Path:
    """Return the site-packages directory of the current Python environment."""
    # Use site.getsitepackages() which returns a list of site-packages directories.
    # For virtual environments, the first entry is usually the user site-packages.
    # We'll pick the first one that exists.
    for sp in site.getsitepackages():
        p = Path(sp)
        if p.exists():
            return p
    # Fallback: use sys.prefix / 'lib' / 'pythonX.Y' / 'site-packages'
    lib = Path(sys.prefix) / "lib"
    for sub in lib.iterdir():
        if sub.is_dir() and sub.name.startswith("python"):
            sp = sub / "site-packages"
            if sp.exists():
                return sp
    raise RuntimeError("Could not find site-packages directory")

def main():
    project_root = Path(__file__).parent.parent.resolve()
    src_path = project_root / "src"
    if not src_path.exists():
        print(f"Error: src directory not found at {src_path}")
        sys.exit(1)

    try:
        site_packages = find_site_packages()
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    pth_file = site_packages / "stimm-src.pth"
    try:
        # Write the absolute path to src
        pth_file.write_text(str(src_path) + "\n", encoding="utf-8")
        print(f"Created {pth_file}")
        print(f"Added {src_path} to sys.path via .pth file")
        print("You can now run 'uv run python -m src.main' without PYTHONPATH.")
    except PermissionError:
        print(f"Error: Permission denied writing to {pth_file}")
        print("You may need to run this script with sudo or adjust permissions.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()