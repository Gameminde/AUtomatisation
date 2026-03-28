from flask import render_template, session

from app import create_app


def test_dashboard_template_renders_french_labels():
    app = create_app()

    with app.test_request_context("/app/dashboard"):
        session["ui_language"] = "FR"
        html = render_template("dashboard.html", active_page="dashboard")

    assert "Tableau de bord" in html
    assert "Poste de pilotage quotidien" in html


def test_page_select_template_renders_arabic_direction_and_copy():
    app = create_app()

    with app.test_request_context("/oauth/facebook/select-page"):
        session["ui_language"] = "AR"
        html = render_template("page_select.html", active_page="channels", oauth_pages=[{"id": "p1", "name": "Main Page"}])

    assert 'dir="rtl"' in html
    assert "اختر الصفحة التي تريد ربطها" in html
    assert "ربط الصفحة" in html
