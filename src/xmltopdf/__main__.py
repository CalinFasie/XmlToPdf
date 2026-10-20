"""Punct de pornire local: ``python -m xmltopdf``."""

from . import LOCAL_HOST, LOCAL_PORT, create_app


def main() -> None:
    app = create_app()
    app.run(host=LOCAL_HOST, port=LOCAL_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
