"""
Allow running as ``python -m fantasy_simulator``.
"""

from .main import main

if __name__ == "__main__":
    import sys

    try:
        main()
    except KeyboardInterrupt:
        from .i18n import tr

        print(f"\n  {tr('interrupted')}")
        sys.exit(130)
