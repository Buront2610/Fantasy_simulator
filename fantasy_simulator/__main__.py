"""
Allow running as ``python -m fantasy_simulator``.
"""

from .main import main as _main


def main() -> None:
    """Run the CLI through the same wrapper used by ``python -m`` and scripts."""
    import sys

    try:
        _main()
    except KeyboardInterrupt:
        from .i18n import tr

        print(f"\n  {tr('interrupted')}")
        sys.exit(130)


if __name__ == "__main__":
    main()
