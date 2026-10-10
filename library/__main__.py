"""Allow ``python -m library`` to run the CLI."""

import sys

from library.cli import main

sys.exit(main())
