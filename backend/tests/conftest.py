import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["LOG_FILE"] = ""
os.environ["CAPTCHA_PROVIDER"] = "local"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def solved_captcha(client, monkeypatch):
    """Issue a real challenge and recover its answer via the hash of the plaintext."""
    from app.core import captcha as captcha_module

    captured: dict[str, str] = {}
    original = captcha_module._render_svg

    def spy(text: str) -> str:
        captured["answer"] = text
        return original(text)

    monkeypatch.setattr(captcha_module, "_render_svg", spy)

    def _issue() -> dict[str, str]:
        response = client.get("/api/auth/captcha")
        assert response.status_code == 200
        return {"challenge_id": response.json()["challenge_id"], "answer": captured["answer"]}

    return _issue


@pytest.fixture
def verified_email(client, monkeypatch):
    """Send and verify a real OTP end-to-end, returning a live verify_token."""
    from app.core import otp as otp_module

    captured: dict[str, str] = {}
    original = otp_module._generate_code

    def spy() -> str:
        code = original()
        captured["code"] = code
        return code

    monkeypatch.setattr(otp_module, "_generate_code", spy)

    def _verify(email: str) -> str:
        sent = client.post("/api/leads/otp/send", json={"email": email})
        assert sent.status_code == 200, sent.text
        verified = client.post("/api/leads/otp/verify", json={"email": email, "code": captured["code"]})
        assert verified.status_code == 200, verified.text
        return verified.json()["verify_token"]

    return _verify
