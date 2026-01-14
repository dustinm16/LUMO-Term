"""Allow running as `python -m lumo_term`."""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
