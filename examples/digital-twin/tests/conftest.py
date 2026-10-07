import sys
from pathlib import Path

# The example is a directory of modules, not a package: import them as the agent does.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
