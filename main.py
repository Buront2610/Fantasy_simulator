"""
main.py - Compatibility wrapper for the Fantasy Simulator CLI.

Preferred invocation: python -m fantasy_simulator
Legacy invocation:   python main.py
"""

from __future__ import annotations

import sys

from fantasy_simulator.main import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        from fantasy_simulator.i18n import tr

        print(f"\n  {tr('interrupted')}")
        sys.exit(130)
