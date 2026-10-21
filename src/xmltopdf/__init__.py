"""Aplicația web locală XmlToPdf."""

from __future__ import annotations

import hmac
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 5000


def create_app() -> Flask:
    """Construiește aplicația Flask."""
    from flask import Flask, jsonify, render_template, request, session
    from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

    from . import ubl

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_bytes(32),
        MAX_CONTENT_LENGTH=ubl.MAX_XML_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=False,
    )

    expected_host = f"{LOCAL_HOST}:{LOCAL_PORT}"
    expected_origin = f"http://{expected_host}"

    @app.before_request
    def validate_local_request():
        if request.host.lower() != expected_host:
            return jsonify(ok=False, message="Cererea trebuie trimisă către adresa locală permisă."), 400

        origin = request.headers.get("Origin")
        if origin is not None and origin != expected_origin:
            return jsonify(ok=False, message="Originea cererii nu este permisă."), 403

        return None

    @app.after_request
    def prevent_response_caching(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_error):
        return jsonify(ok=False, message="XML-ul depășește limita de 10 MiB."), 413

    @app.errorhandler(BadRequest)
    def handle_bad_request(_error):
        return jsonify(ok=False, message="Cererea nu a putut fi procesată."), 400

    @app.get("/")
    def home() -> str:
        csrf_token = session.get("csrf_token")
        if csrf_token is None:
            csrf_token = secrets.token_urlsafe(32)
            session["csrf_token"] = csrf_token
        return render_template("index.html", csrf_token=csrf_token)

    @app.post("/upload")
    def upload_xml():
        if request.mimetype not in {"application/xml", "text/xml", "application/octet-stream"}:
            return jsonify(ok=False, message="Trimite conținut XML pentru procesare."), 415

        expected_token = session.get("csrf_token")
        supplied_token = request.headers.get("X-CSRF-Token", "")
        if not isinstance(expected_token, str) or not hmac.compare_digest(expected_token, supplied_token):
            return jsonify(ok=False, message="Cererea nu are un token CSRF valid."), 403

        content_length = request.content_length
        if content_length is not None and content_length > ubl.MAX_XML_BYTES:
            raise RequestEntityTooLarge()

        # WSGI marks terminated streams (for example, chunked requests) as safe
        # to read to EOF. Read at most one byte beyond the accepted limit so a
        # missing or inaccurate Content-Length cannot bypass the byte cap.
        if "wsgi.input_terminated" in request.environ:
            stream = request.environ["wsgi.input"]
            chunks: list[bytes] = []
            remaining = ubl.MAX_XML_BYTES + 1
            while remaining:
                chunk = stream.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            xml_content = b"".join(chunks)
        else:
            if content_length is None:
                return jsonify(ok=False, message="Lungimea corpului XML nu poate fi verificată în siguranță."), 411
            xml_content = request.get_data(cache=False, parse_form_data=False)
            if len(xml_content) != content_length:
                raise BadRequest()

        if len(xml_content) > ubl.MAX_XML_BYTES:
            raise RequestEntityTooLarge()
        if content_length is not None and len(xml_content) != content_length:
            raise BadRequest()
        if not xml_content:
            return jsonify(ok=False, message="Fișierul XML este gol sau lipsește."), 400

        try:
            invoice = ubl.parse_invoice(xml_content)
        except ubl.UnsupportedDocumentError:
            return jsonify(ok=False, message="Tipul documentului XML nu este suportat."), 422
        except ubl.InvoiceParseError as error:
            return jsonify(ok=False, message=str(error)), 400

        invoice_html = render_template("invoice_bundle.html", invoice=invoice)
        return jsonify(
            ok=True,
            message="Factura a fost încărcată.",
            invoice_html=invoice_html,
        ), 200

    return app
