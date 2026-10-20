"""Aplicația web locală XmlToPdf."""

from flask import Flask, render_template


def create_app() -> Flask:
    """Construiește aplicația Flask."""
    app = Flask(__name__)

    @app.get("/")
    def home() -> str:
        return render_template("index.html")

    return app
