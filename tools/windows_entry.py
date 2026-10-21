"""PyInstaller entry point for the portable Windows console application."""

from xmltopdf.launcher import main


if __name__ == "__main__":
    raise SystemExit(main())
