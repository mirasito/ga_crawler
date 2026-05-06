"""Allow `python -m ga_crawler ...` invocation."""

from __future__ import annotations

import sys

from ga_crawler.cli import main

if __name__ == "__main__":
    sys.exit(main())
