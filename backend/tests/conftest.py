import sys
from pathlib import Path

# Add the src directory to the path so tests can import backend modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
