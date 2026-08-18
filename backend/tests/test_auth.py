def signup(client, solved_captcha, **overrides):
    payload = {
        "email": "ada@example.com",
        "username": "ada",
        "password": "correct-horse-1",
        "role": "student",
        "captcha": solved_captcha(),
    }
    payload.update(overrides)
    return client.post("/api/auth/signup", json=payload)


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_signup_returns_tokens(client, solved_captcha):
    response = signup(client, solved_captcha)
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["username"] == "ada"
    assert body["access_token"] and body["refresh_token"]


def test_signup_rejects_bad_captcha(client, solved_captcha):
    challenge = solved_captcha()
    challenge["answer"] = "WRONG"
    response = signup(client, solved_captcha, captcha=challenge)
    assert response.status_code == 400


def test_captcha_is_single_use(client, solved_captcha):
    challenge = solved_captcha()
    assert signup(client, solved_captcha, captcha=challenge).status_code == 201
    replay = signup(
        client, solved_captcha, captcha=challenge, email="b@example.com", username="bob"
    )
    assert replay.status_code == 400


def test_duplicate_email_conflicts(client, solved_captcha):
    signup(client, solved_captcha)
    response = signup(client, solved_captcha, username="ada2")
    assert response.status_code == 409


def test_login_and_me(client, solved_captcha):
    signup(client, solved_captcha)
    response = client.post(
        "/api/auth/login",
        json={
            "identifier": "ada",
            "password": "correct-horse-1",
            "captcha": solved_captcha(),
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"


def test_login_wrong_password(client, solved_captcha):
    signup(client, solved_captcha)
    response = client.post(
        "/api/auth/login",
        json={"identifier": "ada", "password": "nope-nope-nope", "captcha": solved_captcha()},
    )
    assert response.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_signup_stores_role(client, solved_captcha):
    body = signup(client, solved_captcha, role="mentor").json()
    assert body["user"]["role"] == "mentor"

    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    ).json()
    assert me["role"] == "mentor"


def test_signup_rejects_unknown_role(client, solved_captcha):
    assert signup(client, solved_captcha, role="admin").status_code == 422


def test_signup_requires_role(client, solved_captcha):
    payload = {
        "email": "no.role@example.com",
        "username": "norole",
        "password": "correct-horse-1",
        "captcha": solved_captcha(),
    }
    assert client.post("/api/auth/signup", json=payload).status_code == 422


def test_login_returns_role_from_account(client, solved_captcha):
    """Role comes from the stored account, never from the login request body."""
    signup(client, solved_captcha, role="mentor")
    response = client.post(
        "/api/auth/login",
        json={
            "identifier": "ada",
            "password": "correct-horse-1",
            "role": "student",  # ignored — cannot be used to claim a different role
            "captcha": solved_captcha(),
        },
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "mentor"
