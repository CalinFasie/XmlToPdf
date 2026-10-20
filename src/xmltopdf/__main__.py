"""Punct de pornire local: ``python -m xmltopdf``."""

from . import create_app


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
