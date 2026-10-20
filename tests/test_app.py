from xmltopdf import create_app


def test_homepage_returns_foundation_page() -> None:
    app = create_app()
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"<title>XmlToPdf</title>" in response.data
    assert "Fundația aplicației web locale este pornită.".encode() in response.data
