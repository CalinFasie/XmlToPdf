"""PyInstaller entry point for the windowed Windows system-tray application."""

from xmltopdf.launcher import main


if __name__ == "__main__":
    raise SystemExit(main())
