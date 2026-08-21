import logging
import re

import pytest

from app.database import SessionLocal
from app.models import Lead, User


def register(client, verified_email, **overrides):
    email = overrides.get("email", "asha@example.com")
    payload = {
        "name": "Asha Rao",
        "email": email,
        "role": "student",
        "phone": "9999999999",
        "organisation": "IIT Delhi",
        "newsletter_opt_in": True,
        "email_verify_token": verified_email(email),
    }
    payload.update(overrides)
    return client.post("/api/leads", json=payload)


@pytest.fixture
def admin_token(client, solved_captcha):
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "boss@example.com",
            "username": "boss",
            "password": "admin-password-1",
            "role": "mentor",
            "captcha": solved_captcha(),
        },
    )
    assert response.status_code == 201
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "boss").first()
        user.is_admin = True
        db.commit()
    finally:
        db.close()
    return response.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def test_register_lead(client, solved_captcha, verified_email):
    response = register(client, verified_email)
    assert response.status_code == 201
    assert response.json()["status"] == "registered"


def test_register_rejects_bad_role(client, solved_captcha, verified_email):
    assert register(client, verified_email, role="teacher").status_code == 422


def test_register_email_only(client, verified_email):
    """The website's floating Register button sends nothing but email + otp."""
    email = "waitlist@example.com"
    response = client.post(
        "/api/leads",
        json={
            "email": email,
            "email_verify_token": verified_email(email),
        },
    )
    assert response.status_code == 201

    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.email == email).first()
        assert lead.name == ""
        assert lead.role == "unspecified"
    finally:
        db.close()


def test_email_only_reregister_preserves_existing_name_and_role(client, verified_email):
    """Re-registering through the email-only flow must not clobber fuller data on file."""
    register(client, verified_email)  # name="Asha Rao", role="student"

    email = "asha@example.com"
    response = client.post(
        "/api/leads",
        json={
            "email": email,
            "email_verify_token": verified_email(email),
        },
    )
    assert response.status_code == 201

    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.email == email).first()
        assert lead.name == "Asha Rao"
        assert lead.role == "student"
    finally:
        db.close()


def test_reregistering_updates_instead_of_failing(client, solved_captcha, verified_email):
    register(client, verified_email)
    again = register(client, verified_email, name="Asha R.", role="mentor")
    assert again.status_code == 201

    db = SessionLocal()
    try:
        leads = db.query(Lead).filter(Lead.email == "asha@example.com").all()
        assert len(leads) == 1
        assert leads[0].name == "Asha R."
        assert leads[0].role == "mentor"
    finally:
        db.close()


def test_lead_list_requires_admin(client, solved_captcha, verified_email):
    register(client, verified_email)
    assert client.get("/api/leads").status_code == 401

    response = client.post(
        "/api/auth/signup",
        json={
            "email": "plain@example.com",
            "username": "plain",
            "password": "plain-password-1",
            "role": "student",
            "captcha": solved_captcha(),
        },
    )
    token = response.json()["access_token"]
    assert client.get("/api/leads", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_admin_can_list_and_export(client, solved_captcha, verified_email, admin_headers):
    register(client, verified_email)
    register(client, verified_email, email="ben@example.com", role="mentor", name="Ben")

    body = client.get("/api/leads", headers=admin_headers).json()
    assert body["total"] == 2
    assert body["counts"]["student"] == 1
    assert body["counts"]["mentor"] == 1
    assert body["counts"]["newsletter"] == 2

    csv_response = client.get("/api/leads/export.csv", headers=admin_headers)
    assert csv_response.status_code == 200
    assert "asha@example.com" in csv_response.text
    assert "attachment" in csv_response.headers["content-disposition"]


def test_invite_flow_end_to_end(client, solved_captcha, verified_email, admin_headers, caplog):
    register(client, verified_email)

    with caplog.at_level(logging.INFO, logger="app.email"):
        result = client.post("/api/leads/invite", json={"all_new": True}, headers=admin_headers)
    assert result.status_code == 200
    assert result.json()["sent"] == 1

    # The console backend logs the body; recover the activation link from it.
    # (Registration already logged one email_console record for the OTP code,
    # so match on subject rather than taking the first record.)
    preview = next(
        r.__dict__["body_preview"]
        for r in caplog.records
        if r.msg == "email_console" and r.__dict__.get("subject") == "Set up your SocioTurtle account"
    )
    token = re.search(r"invite=([A-Za-z0-9_-]+)", preview).group(1)

    check = client.get(f"/api/invites/{token}").json()
    assert check["valid"] is True
    assert check["email"] == "asha@example.com"

    activated = client.post(
        "/api/invites/activate",
        json={"token": token, "username": "asha", "password": "her-own-password-1"},
    )
    assert activated.status_code == 201
    assert activated.json()["user"]["role"] == "student"

    # Token is single use.
    assert client.get(f"/api/invites/{token}").json()["valid"] is False

    login = client.post(
        "/api/auth/login",
        json={
            "identifier": "asha",
            "password": "her-own-password-1",
            "captcha": solved_captcha(),
        },
    )
    assert login.status_code == 200


def test_invite_skips_already_invited(client, solved_captcha, verified_email, admin_headers):
    register(client, verified_email)
    client.post("/api/leads/invite", json={"all_new": True}, headers=admin_headers)
    again = client.post(
        "/api/leads/invite", json={"lead_ids": [1]}, headers=admin_headers
    ).json()
    assert again["sent"] == 0
    assert again["skipped"] == 1


def test_invite_never_carries_a_password(client, solved_captcha, verified_email, admin_headers, caplog):
    """The invite must ship a link only; no credential is generated or stored."""
    register(client, verified_email)
    with caplog.at_level(logging.INFO, logger="app.email"):
        client.post("/api/leads/invite", json={"all_new": True}, headers=admin_headers)

    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.email == "asha@example.com").first()
        # A hash of the invite token is stored, never a password, and no User
        # exists until the invitee activates and picks one.
        assert lead.invite_token_hash is not None
        assert lead.user_id is None
        assert db.query(User).filter(User.email == "asha@example.com").first() is None
    finally:
        db.close()


def test_activate_rejects_bad_token(client):
    response = client.post(
        "/api/invites/activate",
        json={"token": "totally-made-up-token", "username": "nope", "password": "whatever-1234"},
    )
    assert response.status_code == 400


def test_newsletter_requires_admin(client):
    response = client.post(
        "/api/newsletter/send", json={"subject": "Hi", "body_markdown": "Hello"}
    )
    assert response.status_code == 401


def test_newsletter_send_and_unsubscribe(client, solved_captcha, verified_email, admin_headers):
    register(client, verified_email)
    register(client, verified_email, email="ben@example.com", role="mentor", name="Ben")

    result = client.post(
        "/api/newsletter/send",
        json={"subject": "Week 1", "body_markdown": "# Hello\n\nSome **news**."},
        headers=admin_headers,
    )
    assert result.status_code == 200
    assert result.json()["recipient_count"] == 2

    db = SessionLocal()
    try:
        token = db.query(Lead).filter(Lead.email == "asha@example.com").first().unsubscribe_token
    finally:
        db.close()

    page = client.get("/api/newsletter/unsubscribe", params={"token": token})
    assert page.status_code == 200
    assert "unsubscribed" in page.text.lower()

    after = client.post(
        "/api/newsletter/send",
        json={"subject": "Week 2", "body_markdown": "More news."},
        headers=admin_headers,
    )
    assert after.json()["recipient_count"] == 1


def test_new_registrant_gets_the_latest_newsletter_issue(
    client, solved_captcha, verified_email, admin_headers, caplog
):
    """A brand-new, opted-in lead should be caught up automatically."""
    register(client, verified_email)
    client.post(
        "/api/newsletter/send",
        json={"subject": "Week 1", "body_markdown": "Hello there."},
        headers=admin_headers,
    )

    email = "newcomer@example.com"
    token = verified_email(email)  # sends its own OTP email — capture that separately from below
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.email"):
        response = client.post(
            "/api/leads",
            json={
                "email": email,
                "newsletter_opt_in": True,
                "email_verify_token": token,
            },
        )
    assert response.status_code == 201

    sent_to_newcomer = [
        r for r in caplog.records if r.msg == "email_console" and r.__dict__.get("to") == email
    ]
    assert len(sent_to_newcomer) == 1
    assert sent_to_newcomer[0].__dict__["subject"] == "Week 1"


def test_registrant_without_newsletter_opt_in_gets_no_issue_email(
    client, solved_captcha, verified_email, admin_headers, caplog
):
    register(client, verified_email)
    client.post(
        "/api/newsletter/send",
        json={"subject": "Week 1", "body_markdown": "Hello there."},
        headers=admin_headers,
    )

    email = "no-thanks@example.com"
    token = verified_email(email)
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.email"):
        response = client.post(
            "/api/leads",
            json={
                "email": email,
                "newsletter_opt_in": False,
                "email_verify_token": token,
            },
        )
    assert response.status_code == 201

    assert not any(
        r.msg == "email_console" and r.__dict__.get("to") == email for r in caplog.records
    )


def test_newsletter_audience_filter(client, solved_captcha, verified_email, admin_headers):
    register(client, verified_email)
    register(client, verified_email, email="ben@example.com", role="mentor", name="Ben")

    result = client.post(
        "/api/newsletter/send",
        json={"subject": "Mentors only", "body_markdown": "Hi mentors", "audience": "mentor"},
        headers=admin_headers,
    )
    assert result.json()["recipient_count"] == 1


def test_newsletter_skips_non_opted_in(client, solved_captcha, verified_email, admin_headers):
    register(client, verified_email, newsletter_opt_in=False)
    response = client.post(
        "/api/newsletter/send",
        json={"subject": "Nobody", "body_markdown": "Hi"},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_unsubscribe_with_unknown_token_does_not_leak(client):
    response = client.get("/api/newsletter/unsubscribe", params={"token": "not-a-real-token"})
    assert response.status_code == 200
    assert "unsubscribed" in response.text.lower()
