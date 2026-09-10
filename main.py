"""Entry point for py-template-personalizer."""

import sys
from pathlib import Path

# Add src to sys.path so the package can be imported without installation
sys.path.insert(0, str(Path(__file__).parent / "src"))

from template_personalizer.cli import main

if __name__ == "__main__":
    sys.exit(main())
