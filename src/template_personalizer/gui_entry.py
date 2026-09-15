import sys
from pathlib import Path

root = Path(__file__).parent.parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))


def main() -> None:
    from gui import main as gui_main
    gui_main()