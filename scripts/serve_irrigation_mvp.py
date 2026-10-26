"""Run from any directory, using the existing project environment."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agro_route.irrigation_web import main

if __name__ == "__main__":
    main()
