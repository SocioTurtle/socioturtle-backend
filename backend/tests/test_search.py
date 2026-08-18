import pytest


@pytest.fixture
def token(client, solved_captcha):
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "ada@example.com",
            "username": "ada",
            "password": "correct-horse-1",
            "role": "student",
            "captcha": solved_captcha(),
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.fixture
def seeded(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    for title, url, description, tags in [
        ("FastAPI docs", "https://fastapi.tiangolo.com", "Python web framework", ["python", "api"]),
        ("React docs", "https://react.dev", "UI library", ["javascript", "frontend"]),
        ("SQLAlchemy ORM", "https://docs.sqlalchemy.org", "Python ORM", ["python", "database"]),
    ]:
        response = client.post(
            "/api/resources",
            json={"title": title, "url": url, "description": description, "tags": tags},
            headers=headers,
        )
        assert response.status_code == 201
    return headers


def test_search_by_title(client, seeded):
    body = client.get("/api/resources/search", params={"q": "react"}).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "React docs"


def test_search_by_description(client, seeded):
    body = client.get("/api/resources/search", params={"q": "python"}).json()
    assert body["total"] == 2


def test_search_by_tag_filter(client, seeded):
    body = client.get("/api/resources/search", params={"tag": "database"}).json()
    assert body["total"] == 1
    assert body["items"][0]["tags"] == ["database", "python"]


def test_empty_query_returns_all_paginated(client, seeded):
    body = client.get("/api/resources/search", params={"limit": 2}).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_search_is_public_but_create_is_not(client):
    assert client.get("/api/resources/search").status_code == 200
    assert client.post("/api/resources", json={"title": "x", "url": "https://x.com"}).status_code == 401
