"""Aplicația web locală XmlToPdf."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask


def create_app() -> Flask:
    """Construiește aplicația Flask."""
    from flask import Flask, render_template

    app = Flask(__name__)

    @app.get("/")
    def home() -> str:
        return render_template("index.html")

    return app
