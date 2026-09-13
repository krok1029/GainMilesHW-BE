from flask import Flask

from app import create_app


def test_health_reports_unavailable_when_postgres_cannot_be_reached() -> None:
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": (
                "postgresql+psycopg://unused:unused@127.0.0.1:1/unavailable"
            ),
        }
    )

    response = app.test_client().get("/health")

    assert response.status_code == 503
    assert response.get_json() == {"status": "unavailable"}


def test_empty_migrated_catalog_is_healthy_without_seed(app: Flask) -> None:
    response = app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
